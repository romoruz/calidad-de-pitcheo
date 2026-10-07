"""Recursos de cómputo (ADR-019): n_jobs, caché de la sintética, medición, señales y f02.sh."""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import psutil
import pytest

from pitcheo import cache_sint, recursos
from pitcheo import sintetico as N

RAIZ = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# n_jobs y BLAS
# --------------------------------------------------------------------------
def test_n_jobs_nunca_es_menos_uno_ni_supera_los_nucleos_fisicos():
    fis = psutil.cpu_count(logical=False) or 1
    assert recursos.n_jobs_seguro({"recursos": {"n_jobs": -1}}) == min(3, fis)       # -1 → default 3 (acotado)
    assert recursos.n_jobs_seguro({"recursos": {"n_jobs": 0}}) == min(3, fis)
    assert recursos.n_jobs_seguro({}) == min(3, fis)
    assert recursos.n_jobs_seguro({"recursos": {"n_jobs": 64}}) == fis
    assert recursos.n_jobs_seguro({"recursos": {"n_jobs": 1}}) == 1
    assert recursos.n_jobs_seguro(None, 2) == min(2, fis)


def test_config_por_defecto_usa_n_jobs_3_y_nunca_menos_uno():
    from pitcheo.config import Config
    cfg = Config.load()
    assert cfg["recursos"]["n_jobs"] == 3 and cfg["recursos"]["blas_hilos_worker"] == 1
    assert cfg["recursos"]["blas_hilos_principal"] == 4 and cfg["recursos"]["cache"] is True
    assert "n_jobs" not in cfg["f02"]["sintetica"]                                    # ya no hay -1 escondido


def _hilos_blas_en_worker(_):
    from threadpoolctl import threadpool_info
    return [i["num_threads"] for i in threadpool_info()]


def test_workers_de_loky_corren_con_blas_a_un_hilo():
    from joblib import Parallel, delayed
    with recursos.config_paralelo(2):
        salidas = Parallel()(delayed(_hilos_blas_en_worker)(i) for i in range(2))
    assert all(n == 1 for hilos in salidas for n in hilos)


def test_limitar_principal_acota_los_hilos_de_blas():
    from threadpoolctl import threadpool_info
    recursos.limitar_principal(2)
    assert all(i["num_threads"] <= 2 for i in threadpool_info())
    recursos.limitar_principal(4)


# --------------------------------------------------------------------------
# Caché de la sintética
# --------------------------------------------------------------------------
KW = {"n_juegos": 6, "lanzamientos_por_juego": 60, "beta_D": -0.3}


def test_cache_acierta_la_segunda_vez_y_devuelve_lo_mismo(tmp_path):
    df1, v1, hit1 = cache_sint.generar_con_cache("t", 5, KW, True, tmp_path)
    df2, v2, hit2 = cache_sint.generar_con_cache("t", 5, KW, True, tmp_path)
    assert (hit1, hit2) == (False, True)
    assert df1.equals(df2) and np.array_equal(v1["delta_verdad"], v2["delta_verdad"]) and set(v1) == set(v2)
    df3, _ = N.generar_fisica(semilla=5, **KW)
    assert df3.equals(df2)                                                           # idéntica a generar sin caché


def test_cache_conserva_tipos_de_la_verdad_con_calibracion_por_parque(tmp_path):
    esq = N.esquema_calibracion_parques(N.CUBETAS_G23B, 5)
    kw = {**KW, "cubetas": N.CUBETAS_G23B, "calibracion_parques": esq}
    _, v1, _ = cache_sint.generar_con_cache("t", 5, kw, True, tmp_path)
    _, v2, hit = cache_sint.generar_con_cache("t", 5, kw, True, tmp_path)
    assert hit and v2["calibracion_parques"] == v1["calibracion_parques"]
    assert all(isinstance(k, int) for k in v2["calibracion_parques"])
    assert v2["juegos"] == v1["juegos"] and v2["parques"] == v1["parques"]


def test_llave_cambia_con_semilla_config_y_hash_de_codigo(tmp_path):
    base = cache_sint.llave("t", KW, 5, "aaaa")
    assert base == cache_sint.llave("t", dict(KW), 5, "aaaa")
    assert base != cache_sint.llave("t", KW, 6, "aaaa")                              # semilla
    assert base != cache_sint.llave("t", {**KW, "beta_D": -0.2}, 5, "aaaa")          # config
    assert base != cache_sint.llave("t", KW, 5, "bbbb")                              # código del generador
    assert base != cache_sint.llave("u", KW, 5, "aaaa")                              # escenario


def test_cache_se_invalida_si_cambia_el_codigo(tmp_path, monkeypatch):
    cache_sint.generar_con_cache("t", 5, KW, True, tmp_path)
    monkeypatch.setattr(recursos, "hash_codigo", lambda *a, **k: "otro-codigo")
    _, _, hit = cache_sint.generar_con_cache("t", 5, KW, True, tmp_path)
    assert hit is False                                                              # otro hash ⇒ otra llave ⇒ se regenera


def test_sin_cache_no_lee_ni_escribe(tmp_path):
    _, _, hit = cache_sint.generar_con_cache("t", 5, KW, False, tmp_path)
    assert hit is False and not list(tmp_path.glob("*.npz"))


def test_cache_corrupta_se_ignora_y_se_regenera(tmp_path):
    cache_sint.generar_con_cache("t", 5, KW, True, tmp_path)
    arch = next(tmp_path.glob("*.npz"))
    arch.write_bytes(b"no es un npz")
    _, _, hit = cache_sint.generar_con_cache("t", 5, KW, True, tmp_path)
    assert hit is False


def test_cache_esta_fuera_de_git():
    assert "reports/cache/" in (RAIZ / ".gitignore").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Medición de recursos
# --------------------------------------------------------------------------
def test_medir_arbol_reporta_segundos_ram_y_cpu():
    with recursos.medir_arbol(dt=0.05) as m:
        x = np.random.default_rng(0).normal(size=(1500, 1500))
        _ = x @ x
        time.sleep(0.2)
    r = m.resultado()
    assert r["segundos"] > 0.1 and r["ram_pico_mb"] > 10 and r["cpu_pct_equipo"] > 0 and r["nucleos_logicos"] >= 1


def test_escribir_recursos_fusiona_etapas(tmp_path):
    ruta = tmp_path / "r.json"
    recursos.escribir_recursos(ruta, "pruebas", {"segundos": 1.0})
    recursos.escribir_recursos(ruta, "real", {"segundos": 2.0})
    d = json.loads(ruta.read_text(encoding="utf-8"))
    assert set(d["etapas"]) == {"pruebas", "real"} and d["etapas"]["real"]["segundos"] == 2.0 and "fecha" in d["etapas"]["real"]


def test_correr_etapa_mide_y_marca_estado(tmp_path):
    ruta = tmp_path / "r.json"
    assert recursos.correr_etapa("ok", [sys.executable, "-c", "pass"], ruta) == 0
    assert recursos.correr_etapa("gate", [sys.executable, "-c", "import sys; sys.exit(2)"], ruta) == 2
    assert recursos.correr_etapa("mal", [sys.executable, "-c", "import sys; sys.exit(5)"], ruta) == 5
    est = {k: v["estado"] for k, v in json.loads(ruta.read_text(encoding="utf-8"))["etapas"].items()}
    assert est == {"ok": "ok", "gate": "compuerta_fallida", "mal": "error"}
    assert "hash_codigo" in json.loads(ruta.read_text(encoding="utf-8"))["etapas"]["ok"]


# --------------------------------------------------------------------------
# Señales: nada de workers huérfanos y la etapa queda «interrumpida»
# --------------------------------------------------------------------------
def _vivo(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


@pytest.mark.parametrize("senal", [signal.SIGTERM, signal.SIGINT])
def test_senal_termina_el_arbol_y_marca_interrumpida(tmp_path, senal):
    ruta = tmp_path / "r.json"
    pidfile = tmp_path / "nieto.pid"
    nieto = f"import os,time; open(r'{pidfile}','w').write(str(os.getpid())); time.sleep(120)"
    cmd = [sys.executable, "-c",
           f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{nieto!r}]); time.sleep(120)"]
    p = subprocess.Popen([sys.executable, "-m", "pitcheo.recursos", "--etapa", "t", "--json", str(ruta), "--", *cmd], cwd=RAIZ)
    for _ in range(100):                                                             # espera a que exista el nieto
        if pidfile.exists() and pidfile.read_text():
            break
        time.sleep(0.1)
    nieto_pid = int(pidfile.read_text())
    assert _vivo(nieto_pid)
    p.send_signal(senal)
    assert p.wait(timeout=30) == 130
    time.sleep(0.5)
    assert not _vivo(nieto_pid)                                                      # el nieto (≈ worker de loky) murió
    assert json.loads(ruta.read_text(encoding="utf-8"))["etapas"]["t"]["estado"] == "interrumpida"


def test_matar_hijos_termina_los_workers_de_loky():
    from joblib import Parallel, delayed
    with recursos.config_paralelo(2):
        Parallel()(delayed(time.sleep)(0.01) for _ in range(4))                      # arranca los workers y los deja vivos
    def workers():
        return [h for h in psutil.Process().children(recursive=True) if _vivo(h.pid) and not recursos._es_tracker(h)]
    assert workers()
    recursos.matar_hijos()
    time.sleep(0.5)
    assert not workers()                                                             # el resource_tracker sobrevive a propósito


def test_instalar_senales_registra_los_manejadores():
    previos = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        recursos.instalar_senales()
        assert signal.getsignal(signal.SIGINT) is not previos[signal.SIGINT]
        assert signal.getsignal(signal.SIGTERM) is not previos[signal.SIGTERM]
    finally:
        for s, h in previos.items():
            signal.signal(s, h)


# --------------------------------------------------------------------------
# f02.sh
# --------------------------------------------------------------------------
def test_f02_sh_sintaxis_y_etapa_invalida():
    sh = RAIZ / "scripts" / "fases" / "f02.sh"
    assert subprocess.run(["bash", "-n", str(sh)], capture_output=True, check=False).returncode == 0
    r = subprocess.run(["bash", str(sh), "--etapa", "magia"], capture_output=True, text=True, check=False)
    assert r.returncode == 64 and "inválida" in r.stderr


def test_f02_sh_contiene_las_protecciones_pedidas():
    t = (RAIZ / "scripts" / "fases" / "f02.sh").read_text(encoding="utf-8")
    for pieza in ("OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1",
                  "nice -n 10", "ionice -c3", "CPUQuota", "trap limpiar INT TERM", "--etapa", "pruebas|escala|sintetica|real|todo",
                  "--reusar", "NO se commitea"):
        assert pieza in t, pieza
    assert "n_jobs=-1" not in t and "--n-jobs -1" not in t
