"""Recursos de cómputo de F2 (ADR-019): límites de hilos, medición por etapa (tiempo, RAM pico, CPU %) y señales.

Pensado para una laptop (i7-1165G7: 4 núcleos físicos / 8 hilos, 32 GB) que debe quedar usable mientras corre F2:
  - `n_jobs` por defecto 3 (nunca -1), BLAS a 1 hilo dentro de cada worker (`config_paralelo`), hasta 4 hilos en el
    proceso principal (`limitar_principal`);
  - `medir_arbol` muestrea el árbol de procesos (incluidos los workers de loky) con psutil;
  - `matar_hijos` / `instalar_senales` terminan los workers si el usuario interrumpe (SIGINT/SIGTERM);
  - `python -m pitcheo.recursos --etapa X -- <cmd...>` ejecuta una etapa, la mide y escribe `reports/f02_recursos.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

import psutil

RAIZ = Path(__file__).resolve().parents[2]
HILOS_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
_limite_principal = None


def n_jobs_seguro(cfg: dict | None, pedido: int | None = None) -> int:
    """n_jobs efectivo: `pedido` o `recursos.n_jobs` de la config (default 3), acotado a [1, núcleos físicos]. Nunca -1."""
    n = pedido if pedido is not None else ((cfg or {}).get("recursos") or {}).get("n_jobs", 3)
    n = 3 if n is None or int(n) < 1 else int(n)
    fisicos = psutil.cpu_count(logical=False) or os.cpu_count() or 1
    return max(1, min(n, fisicos))


def limitar_principal(hilos: int = 4):
    """BLAS del proceso principal (LSMR/CR2) a lo más `hilos` hilos. Devuelve el objeto de threadpoolctl."""
    global _limite_principal
    from threadpoolctl import threadpool_limits
    _limite_principal = threadpool_limits(limits=hilos)
    return _limite_principal


def config_paralelo(n_jobs: int):
    """Contexto de joblib: loky con `n_jobs` workers y BLAS/OpenMP a 1 hilo dentro de cada uno."""
    from joblib import parallel_config
    return parallel_config(backend="loky", n_jobs=n_jobs, inner_max_num_threads=1)


def en_worker_un_hilo() -> None:
    """Llamar al inicio de funciones que corren en workers: refuerza BLAS=1 aunque el entorno no lo traiga."""
    from threadpoolctl import threadpool_limits
    threadpool_limits(limits=1)


def _es_tracker(p: psutil.Process) -> bool:
    """El resource_tracker de loky/multiprocessing debe sobrevivir: si lo matamos imprime KeyError al limpiar /dev/shm."""
    try:
        return any("resource_tracker" in a for a in p.cmdline())
    except psutil.Error:
        return False


def matar_hijos(incluir_loky: bool = True) -> int:
    """Termina (y si hace falta mata) todos los procesos hijos del actual, incluidos los workers de loky."""
    if incluir_loky:
        with suppress(Exception):                                # mejor esfuerzo al apagar
            from joblib.externals.loky import get_reusable_executor
            get_reusable_executor().shutdown(wait=False, kill_workers=True)
    hijos = [h for h in psutil.Process().children(recursive=True) if not _es_tracker(h)]
    for h in hijos:
        try:
            h.terminate()
        except psutil.Error:
            pass
    _, vivos = psutil.wait_procs(hijos, timeout=3)
    for h in vivos:
        try:
            h.kill()
        except psutil.Error:
            pass
    return len(hijos)


def instalar_senales() -> None:
    """SIGINT/SIGTERM: matar los workers de loky y salir con 130/143 (la etapa queda marcada como interrumpida)."""
    def manejador(signum, _frame):
        matar_hijos()
        sys.stderr.write(f"\n[interrumpido] señal {signum}: workers terminados\n")
        os._exit(128 + signum)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, manejador)


def hash_codigo(archivos=("sintetico.py", "fisica.py")) -> str:
    """SHA-256 (16 hex) del contenido de los archivos de código que definen la sintética (llave de caché y de escala)."""
    h = hashlib.sha256()
    for a in archivos:
        h.update((Path(__file__).parent / a).read_bytes())
    return h.hexdigest()[:16]


def _arbol(proc: psutil.Process):
    try:
        return [proc, *proc.children(recursive=True)]
    except psutil.Error:
        return [proc]


class MedidorArbol:
    """Muestrea tiempo de CPU y RSS del árbol de procesos de `proc` (por defecto, el actual) cada `dt` segundos."""

    def __init__(self, proc: psutil.Process | None = None, dt: float = 0.5):
        self.proc = proc or psutil.Process()
        self.dt = dt
        self.ncpu = psutil.cpu_count(logical=True) or 1
        self.ram_pico = 0
        self._cpu_vistos: dict[int, float] = {}
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self.t0 = self.t1 = 0.0
        self.cpu_sistema: list[float] = []

    def _muestra(self) -> None:
        rss = 0
        for p in _arbol(self.proc):
            try:
                rss += p.memory_info().rss
                t = p.cpu_times()
                self._cpu_vistos[p.pid] = max(self._cpu_vistos.get(p.pid, 0.0), t.user + t.system)
            except psutil.Error:
                continue
        self.ram_pico = max(self.ram_pico, rss)

    def _bucle(self) -> None:
        psutil.cpu_percent(None)
        while not self._parar.wait(self.dt):
            self._muestra()
            self.cpu_sistema.append(psutil.cpu_percent(None))

    def __enter__(self):
        self.t0 = time.time()
        self._muestra()
        self._hilo.start()
        return self

    def __exit__(self, *exc):
        self._parar.set()
        self._hilo.join(timeout=2)
        self._muestra()
        self.t1 = time.time()

    def resultado(self) -> dict:
        seg = max(self.t1 - self.t0, 1e-9)
        cpu = sum(self._cpu_vistos.values())
        return {"segundos": round(seg, 1), "ram_pico_mb": round(self.ram_pico / 2**20),
                "cpu_pct_equipo": round(100.0 * cpu / (seg * self.ncpu), 1),
                "cpu_pct_sistema": round(sum(self.cpu_sistema) / len(self.cpu_sistema), 1) if self.cpu_sistema else None,
                "cpu_segundos": round(cpu, 1), "nucleos_logicos": self.ncpu}


@contextmanager
def medir_arbol(dt: float = 0.5):
    """Mide el árbol del proceso actual: `with medir_arbol() as m: ...; m.resultado()`."""
    m = MedidorArbol(dt=dt)
    with m:
        yield m


def escribir_recursos(ruta: Path, etapa: str, datos: dict) -> None:
    """Fusiona `datos` en `ruta` bajo `etapas[etapa]` (conserva las demás etapas)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    actual = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {"etapas": {}}
    actual.setdefault("etapas", {})[etapa] = {**datos, "fecha": datetime.now(UTC).isoformat(timespec="seconds")}
    ruta.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")


def _estado(codigo: int, interrumpida: bool) -> str:
    if interrumpida or codigo in (130, 143) or codigo < 0:
        return "interrumpida"
    return {0: "ok", 2: "compuerta_fallida"}.get(codigo, "error")


def correr_etapa(etapa: str, cmd: list[str], ruta_json: Path) -> int:
    """Ejecuta `cmd` como una etapa: mide su árbol, traduce señales a 'interrumpida' y escribe el JSON de recursos."""
    interrumpida = {"v": False}
    proc_ref: dict = {}

    def propagar(signum, _f):
        interrumpida["v"] = True
        p = proc_ref.get("p")
        if p is not None:
            for h in reversed(_arbol(psutil.Process(p.pid))):
                try:
                    h.terminate()
                except psutil.Error:
                    pass

    viejos = {s: signal.signal(s, propagar) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        p = subprocess.Popen(cmd, cwd=RAIZ)
        proc_ref["p"] = p
        with MedidorArbol(psutil.Process(p.pid)) as m:
            codigo = p.wait()
    finally:
        for s, h in viejos.items():
            signal.signal(s, h)
    estado = _estado(codigo, interrumpida["v"])
    datos = {**m.resultado(), "estado": estado, "codigo_salida": codigo, "comando": " ".join(cmd),
             "hash_codigo": hash_codigo()}
    escribir_recursos(ruta_json, etapa, datos)
    meta = 75.0
    aviso = "" if datos["cpu_pct_equipo"] <= meta else f" ⚠ CPU promedio {datos['cpu_pct_equipo']} % > {meta} %"
    print(f"[recursos] {etapa}: {datos['segundos']} s · RAM pico {datos['ram_pico_mb']} MB · CPU {datos['cpu_pct_equipo']} % "
          f"del equipo ({datos['estado']}){aviso}", flush=True)
    return 130 if estado == "interrumpida" else codigo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pitcheo.recursos")
    ap.add_argument("--etapa", required=True)
    ap.add_argument("--json", default=str(RAIZ / "reports" / "f02_recursos.json"))
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        ap.error("falta el comando tras --")
    return correr_etapa(a.etapa, cmd, Path(a.json))


if __name__ == "__main__":
    sys.exit(main())
