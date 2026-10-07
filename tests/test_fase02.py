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
            "sigma_eta": 0.05, "metodo_se": "CR2", "segundos": 1.0, "deming_pendiente": 1.0, "deming_se": 0.02,
            "cache": False}


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
    lo, hi = r["limpio"]["ic_clopper_pearson"]
    assert lo < 0.25 < hi and 0 <= lo and hi <= 1                           # IC exacto contiene la tasa observada
    assert r["fpr_cota"] == pytest.approx(F2.cota_fpr(8))


def test_cota_fpr_de_morris_white_crowther_con_180_limpios_es_0_082():
    assert F2.cota_fpr(180) == pytest.approx(0.05 + 1.96 * np.sqrt(0.05 * 0.95 / 180))
    assert round(F2.cota_fpr(180), 3) == 0.082
    assert F2.cota_fpr(60) > F2.cota_fpr(180) > 0.05                         # con menos parques limpios la tolerancia crece


def test_clopper_pearson_valores_conocidos():
    lo, hi = F2.clopper_pearson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.3085, abs=2e-4)
    lo, hi = F2.clopper_pearson(5, 10)
    assert (lo, hi) == pytest.approx((0.1871, 0.8129), abs=2e-4)
    assert F2.clopper_pearson(10, 10)[1] == 1.0


def _agregados(spinaxis_medido=True, se=0.009, pendiente=1.0, adoptado=True):
    medias = {c: {"n": 20, "delta_D": v, "se_D": 0.005, "delta_L": v, "se_L": 0.01}
              for c, v in zip(F2.CUBETAS, (0.0, -0.2, -0.28), strict=True)}
    return {"medias_por_cubeta": medias, "mezcla_extreme": {"componentes": [{"media": -0.28}]},
            "deming": {"pendiente": pendiente, "se_pendiente": 0.02, "intercepto": 0.0},
            "calibracion": {"spinaxis": {"medido": spinaxis_medido}},
            "se": {"se_cr2_D_mediana": se, "sigma_eta_D": 0.05, "sigma_eta_L": 0.09, "se_ingenuo_D_mediana": 0.003,
                   "efecto_diseno_D": 2.5, "metodo": "CR2"},
            "juegos": {"confirmatorios": 100},
            "prop2pp": ({"activada": True, "adoptado": True, "se_corregido_D_mediana": se, "medias_corregidas": medias,
                         "mezcla_extreme_corregida": {"componentes": [{"media": -0.28}]},
                         "deming_corregido": {"pendiente": pendiente, "se_pendiente": 0.02, "intercepto": 0.0}}
                        if adoptado else {"activada": True, "adoptado": False})}


GATES = Config.load()["f02"]["gates"]


def _sint(potencia=0.95, fpr=0.03, cobertura=0.94, sesgo=0.002, spinaxis_medido=True):
    cota = sesgo + 0.00196
    niveles = {c: {"sesgo_rel": sesgo, "mcse": 0.001, "cota": cota, "ok": cota < GATES["g21_error_max"]} for c in CUB}
    n_lim = 180
    g = {"R": 30, "q": 0.05, "potencia": potencia, "fpr": fpr, "spinaxis_medido": spinaxis_medido,
         "potencia_ic_clopper_pearson": [0.9, 0.99], "fpr_cota": F2.cota_fpr(n_lim),
         "lambda": {"tasa": potencia, "rechazos": 19, "n": 20, "ic_clopper_pearson": [0.7, 0.99]},
         "tau": {"tasa": potencia, "rechazos": 19, "n": 20, "ic_clopper_pearson": [0.7, 0.99]},
         "limpio": {"tasa": fpr, "rechazos": round(fpr * n_lim), "n": n_lim, "ic_clopper_pearson": [0.0, 0.1]}}
    return {"g21": {"R": 30, "semillas": list(range(211, 241)), "niveles": niveles, "cobertura": cobertura,
                    "primario": "corregido"},
            "g23b": {"con_calibracion": g}}


def test_gates_todo_bien_pasa():
    g = F2.evaluar_gates(_agregados(), _sint(), GATES)
    assert list(g) == ["G2.1", "G2.2", "G2.3a", "G2.3b", "G2.4"] and all(x["ok"] for x in g.values())


@pytest.mark.parametrize(("agr", "sint", "falla"), [
    ({}, {"sesgo": 0.0095}, "G2.1"),
    ({"pendiente": 1.2}, {}, "G2.3a"),
    ({}, {"potencia": 0.7}, "G2.3b"),
    ({}, {"fpr": 0.09}, "G2.3b"),
    ({"se": 0.035}, {}, "G2.4"),
    ({}, {"cobertura": 0.85}, "G2.4"),
])
def test_cada_compuerta_falla_cuando_corresponde(agr, sint, falla):
    g = F2.evaluar_gates(_agregados(**agr), _sint(**sint), GATES)
    assert [k for k, v in g.items() if not v["ok"]] == [falla]


def test_g23b_fpr_usa_la_cota_de_morris_white_crowther_y_no_0_05_a_secas():
    """ADR-019 D3: con 180 limpios la cota es 0.0818: FPR 0.07 pasa (con 0.05 a secas fallaría), 0.09 no."""
    assert F2.evaluar_gates(_agregados(), _sint(fpr=0.07), GATES)["G2.3b"]["ok"]
    assert not F2.evaluar_gates(_agregados(), _sint(fpr=0.09), GATES)["G2.3b"]["ok"]


def test_si_la_equivalencia_no_pasa_g22_g24_son_provisionales_en_bruto():
    """ADR-019 E: sin adopción de Prop. 2″, G2.2/G2.3a/G2.4 llevan 🔎 y `provisional`; G2.1/G2.3b siguen siendo compuertas."""
    g = F2.evaluar_gates(_agregados(adoptado=False), _sint(), GATES)
    for k in ("G2.2", "G2.3a", "G2.4"):
        assert g[k]["provisional"] and "🔎" in g[k]["detalle"]
    assert not g["G2.1"].get("provisional") and not g["G2.3b"].get("provisional")
    ok = F2.evaluar_gates(_agregados(adoptado=True), _sint(), GATES)
    assert not any(v.get("provisional") for v in ok.values())


def test_g23b_real_inferido_no_hace_fallar_la_compuerta():
    """ADR-018: G2.3b en real = n/e; la compuerta vive en la sintética y SOLO depende del chk sintético."""
    g = F2.evaluar_gates(_agregados(spinaxis_medido=False), _sint(), GATES)
    assert g["G2.3b"]["ok"] and "no_evaluable" not in g["G2.3b"]            # SpinAxis real inferido no tumba la compuerta
    g2 = F2.evaluar_gates(_agregados(), _sint(spinaxis_medido=False, potencia=0.1, fpr=0.9), GATES)
    assert g2["G2.3b"]["ok"] and g2["G2.3b"]["no_evaluable"] and "SINTÉTICA" in g2["G2.3b"]["detalle"]


def _cfg_chico():
    cfg = Config(copy.deepcopy(dict(Config.load())))
    cfg["f02"]["sintetica"].update({"semillas": [901, 902], "n_juegos": 30, "n_juegos_g23b": 45})
    cfg["recursos"] = {"n_jobs": 2, "cache": False}
    return cfg


def _df_chico():
    from pitcheo.config import Config as C
    from pitcheo.sintetico import generar_fisica
    sc = C.load()["f02"]["sintetica"]
    df, _ = generar_fisica(40, 120, 3, beta_D=sc["beta_D"], beta_L=sc["beta_L"])
    return df


def test_escala_vigente_solo_con_el_mismo_hash_de_codigo(tmp_path):
    """`--etapa todo` salta la escala si reports/f02_escala.json tiene el mismo hash de código (ADR-019 R4)."""
    from pitcheo import recursos
    ruta = tmp_path / "f02_escala.json"
    assert not F2.escala_vigente(ruta)                                        # no existe
    ruta.write_text(json.dumps({"hash_codigo": recursos.hash_codigo()}), encoding="utf-8")
    assert F2.escala_vigente(ruta)
    ruta.write_text(json.dumps({"hash_codigo": "otro"}), encoding="utf-8")
    assert not F2.escala_vigente(ruta)                                        # cambió el código del generador/física
    ruta.write_text("no es json", encoding="utf-8")
    assert not F2.escala_vigente(ruta)


def test_etapas_sintetica_y_real_por_separado_y_firma_vieja(tmp_path):
    cfg = _cfg_chico()
    rep, logs = tmp_path / "rep", tmp_path / "logs"
    s = F2.correr_sintetica(cfg, rep, logs, usar_cache=False)
    assert set(s["gates"]) == {"G2.1", "G2.3b", "G2.4_cobertura"}
    assert (rep / "f02_sintetica.json").exists() and (rep / "FASE_02_sintetica.md").exists()
    assert not (rep / "FASE_02.md").exists()                                # la real aún no corre
    sint = F2.cargar_sintetica(cfg["f02"], rep)
    res = F2.correr_real(cfg, _df_chico(), sint, tmp_path / "d.parquet", rep, logs, tmp_path / "fig")
    assert (rep / "FASE_02.md").exists() and set(res["gates"]) == {"G2.1", "G2.2", "G2.3a", "G2.3b", "G2.4"}
    # Si cambia la config de la sintética (o el código), `real` exige volver a correr `sintetica`.
    cfg2 = _cfg_chico()
    cfg2["f02"]["sintetica"]["n_juegos"] = 31
    with pytest.raises(RuntimeError, match="desactualizada"):
        F2.cargar_sintetica(cfg2["f02"], rep)
    with pytest.raises(FileNotFoundError):
        F2.cargar_sintetica(cfg["f02"], tmp_path / "otra")


def test_correr_detiene_la_fase_si_la_equivalencia_no_pasa(tmp_path):
    """ADR-019 E: con tolerancia imposible Prop. 2″ no se adopta → detenido, ok=False, G2.2–G2.4 en bruto con 🔎."""
    cfg = _cfg_chico()
    cfg["f02"]["prop2pp"]["tolerancia_equivalencia"] = 1e-9
    res = F2.correr(cfg, _df_chico(), tmp_path / "d.parquet", tmp_path / "rep", tmp_path / "logs", tmp_path / "fig")
    assert res["detenido"] and not res["ok"]
    assert all(res["gates"][k]["provisional"] for k in ("G2.2", "G2.3a", "G2.4"))
    md = (tmp_path / "rep" / "FASE_02.md").read_text(encoding="utf-8")
    assert "FASE DETENIDA" in md and "🔎" in md


def test_correr_de_punta_a_punta_en_chico(tmp_path):
    cfg = _cfg_chico()
    df = _df_chico()
    res = F2.correr(cfg, df, tmp_path / "densidad.parquet", tmp_path / "rep", tmp_path / "logs", tmp_path / "fig")
    assert set(res["gates"]) == {"G2.1", "G2.2", "G2.3a", "G2.3b", "G2.4"}
    md = (tmp_path / "rep" / "FASE_02.md").read_text(encoding="utf-8")
    assert "Bloque para el orquestador — F02" in md and "G2.3b" in md
    js = json.loads((tmp_path / "rep" / "fase_02.json").read_text(encoding="utf-8"))
    assert "g21" in js["sintetica"] and "g23b" in js["sintetica"]
    assert (tmp_path / "densidad.parquet").exists() and len(list((tmp_path / "logs").glob("f02_*.log"))) >= 1
    # Privacidad: nada por lanzamiento ni por lanzador en reportes/logs/figuras; sin arrays por juego en el JSON.
    assert "pitcher_" not in md and "pitcher_" not in json.dumps(js)
    assert "delta_corregido_D" not in json.dumps(js)
    assert sorted(p.name for p in (tmp_path / "fig").iterdir()) == ["c_g_por_cubeta.png", "delta_por_cubeta.png", "deming_delta_L_vs_D.png"]
