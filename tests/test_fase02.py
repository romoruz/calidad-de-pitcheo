"""F2 — orquestación: estudio de simulación de G2.1, escenario de G2.3b, compuertas y el flujo completo en chico."""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from pitcheo import fase02 as F2
from pitcheo.config import Config

CUB = ["Medium Altitude", "Extreme Altitude"]


def _rep(error_m, error_e, n=40, se=0.01, ruido=0.01, semilla=0):
    rng = np.random.default_rng(semilla)
    cubeta = np.array([CUB[i % 2] for i in range(n)])
    verdad = rng.normal(-0.2, 0.05, n)
    return {"semilla": semilla, "error": {CUB[0]: error_m, CUB[1]: error_e}, "n_lanzamientos": 100,
            "delta": verdad + rng.normal(0, ruido, n), "verdad": verdad, "se": np.full(n, se), "cubeta": cubeta,
            "sigma_eta": 0.05, "metodo_se": "CR2", "segundos": 1.0}


def test_resumen_g21_aprueba_con_sesgo_chico_y_mcse_chico_y_falla_con_dispersion():
    bien = [_rep(0.002 + 0.001 * k, -0.001, semilla=i) for i, k in enumerate((-1, 0, 1) * 3)]
    r = F2.resumen_g21(bien, 0.01)
    assert r["R"] == 9 and all(x["ok"] for x in r["niveles"].values())
    medium = r["niveles"][CUB[0]]
    assert medium["sesgo_rel"] == pytest.approx(0.002, abs=1e-12)
    assert medium["cota"] == pytest.approx(abs(medium["sesgo_rel"]) + 1.96 * medium["mcse"])
    # La corrida fallida de D02b (45 juegos): sesgo +0.2 % pero dispersión grande → |sesgo| + 1.96·MCSE > 1 %.
    mal = [_rep(e, 0.0, semilla=k) for k, e in enumerate([0.012, -0.008, 0.009])]
    assert not F2.resumen_g21(mal, 0.01)["niveles"][CUB[0]]["ok"]


def test_resumen_g21_mide_cobertura_y_se_empirico():
    reps = [_rep(0.0, 0.0, n=400, se=0.01, ruido=0.01, semilla=k) for k in range(5)]
    r = F2.resumen_g21(reps, 0.01)
    assert r["cobertura"] == pytest.approx(0.95, abs=0.02)
    assert r["niveles"][CUB[0]]["se_empirico"] == pytest.approx(0.01, rel=0.15)
    subestimado = [_rep(0.0, 0.0, n=400, se=0.005, ruido=0.01, semilla=k) for k in range(5)]
    assert F2.resumen_g21(subestimado, 0.01)["cobertura"] < 0.90


def test_resumen_g23b_potencia_y_fpr():
    def fila(tipo, rech, c=0.02):
        return {"parque": "p", "tipo": tipo, "evaluable": True, "rechaza_bh": rech, "c_centrado": c, "c_verdad": c, "se": 0.002}
    rep = {"parques": [fila("lambda", True), fila("lambda", True), fila("tau", True), fila("tau", False, -0.02),
                       fila("limpio", False, 0.0), fila("limpio", True, 0.0), fila("limpio", False, 0.0), fila("limpio", False, 0.0)],
           "deming": {"pendiente": 1.01}, "spinaxis_medido": True, "n_lanzamientos": 10, "q": 0.05}
    r = F2.resumen_g23b([rep, rep])
    assert r["potencia"] == pytest.approx(0.75) and r["lambda"]["tasa"] == 1.0 and r["tau"]["tasa"] == 0.5
    assert r["fpr"] == pytest.approx(0.25) and r["limpio"]["n"] == 8


def _agregados(spinaxis_medido=True, se=0.009, pendiente=1.0):
    medias = {c: {"n": 20, "delta_D": v, "se_D": 0.005, "delta_L": v, "se_L": 0.01}
              for c, v in zip(F2.CUBETAS, (0.0, -0.2, -0.28), strict=True)}
    return {"medias_por_cubeta": medias, "mezcla_extreme": {"componentes": [{"media": -0.28}]},
            "deming": {"pendiente": pendiente, "se_pendiente": 0.02, "intercepto": 0.0},
            "calibracion": {"spinaxis": {"medido": spinaxis_medido}},
            "se": {"se_cr2_D_mediana": se, "sigma_eta_D": 0.05, "sigma_eta_L": 0.09, "se_ingenuo_D_mediana": 0.003,
                   "efecto_diseno_D": 2.5, "metodo": "CR2"}}


GATES = Config.load()["f02"]["gates"]


def _sint(potencia=0.95, fpr=0.03, cobertura=0.94, sesgo=0.002):
    cota = sesgo + 0.00196
    niveles = {c: {"sesgo_rel": sesgo, "mcse": 0.001, "cota": cota, "ok": cota < GATES["g21_error_max"]} for c in CUB}
    g = {"R": 10, "q": 0.05, "potencia": potencia, "fpr": fpr, "lambda": {"tasa": potencia, "rechazos": 19, "n": 20},
         "tau": {"tasa": potencia, "rechazos": 19, "n": 20}, "limpio": {"tasa": fpr, "rechazos": 1, "n": 40}}
    return {"g21": {"R": 10, "semillas": list(range(101, 111)), "niveles": niveles, "cobertura": cobertura},
            "g23b": {"con_calibracion": g}}


def test_gates_todo_bien_pasa():
    g = F2.evaluar_gates(_agregados(), _sint(), GATES)
    assert list(g) == ["G2.1", "G2.2", "G2.3a", "G2.3b", "G2.4"] and all(x["ok"] for x in g.values())


@pytest.mark.parametrize(("agr", "sint", "falla"), [
    ({}, {"sesgo": 0.0095}, "G2.1"),
    ({"pendiente": 1.2}, {}, "G2.3a"),
    ({}, {"potencia": 0.7}, "G2.3b"),
    ({}, {"fpr": 0.08}, "G2.3b"),
    ({"se": 0.035}, {}, "G2.4"),
    ({}, {"cobertura": 0.85}, "G2.4"),
])
def test_cada_compuerta_falla_cuando_corresponde(agr, sint, falla):
    g = F2.evaluar_gates(_agregados(**agr), _sint(**sint), GATES)
    assert [k for k, v in g.items() if not v["ok"]] == [falla]


def test_g23b_no_evaluable_si_spinaxis_inferido_y_no_hace_fallar_el_resto():
    g = F2.evaluar_gates(_agregados(spinaxis_medido=False), _sint(potencia=0.1, fpr=0.9), GATES)
    assert g["G2.3b"]["ok"] and g["G2.3b"]["no_evaluable"] and "NO EVALUABLE" in g["G2.3b"]["detalle"]


def test_correr_de_punta_a_punta_en_chico(tmp_path):
    from pitcheo.sintetico import generar_fisica
    cfg = Config.load()
    cfg = Config(copy.deepcopy(dict(cfg)))
    cfg["f02"]["sintetica"].update({"semillas": [901, 902], "n_juegos": 30, "n_juegos_g23b": 45, "n_jobs": 2})
    df, _ = generar_fisica(40, 120, 3)
    res = F2.correr(cfg, df, tmp_path / "densidad.parquet", tmp_path / "rep", tmp_path / "logs", tmp_path / "fig")
    assert set(res["gates"]) == {"G2.1", "G2.2", "G2.3a", "G2.3b", "G2.4"}
    md = (tmp_path / "rep" / "FASE_02.md").read_text(encoding="utf-8")
    assert "Bloque para el orquestador — F02" in md and "G2.3b" in md
    js = json.loads((tmp_path / "rep" / "fase_02.json").read_text(encoding="utf-8"))
    assert "g21" in js["sintetica"] and "g23b" in js["sintetica"]
    assert (tmp_path / "densidad.parquet").exists() and len(list((tmp_path / "logs").glob("f02_*.log"))) == 1
    # Privacidad: nada por lanzamiento ni por lanzador en reportes/logs/figuras.
    assert "pitcher_" not in md and "pitcher_" not in json.dumps(js)
    assert sorted(p.name for p in (tmp_path / "fig").iterdir()) == ["c_g_por_cubeta.png", "delta_por_cubeta.png", "deming_delta_L_vs_D.png"]
