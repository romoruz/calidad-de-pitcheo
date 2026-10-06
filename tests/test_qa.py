"""Identidades I1-I5, I6′, I7-I10: con el sintético pasan; con violaciones sembradas, cada una se detecta."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from pitcheo import qa
from pitcheo.config import Config
from pitcheo.io import leer_diccionario
from pitcheo.limpieza import cargar_categorias, limpiar
from pitcheo.sintetico import generar

CFG = Config.load()
CAT = cargar_categorias(CFG.ruta("categorias"))
Q = CFG["qa"]


@pytest.fixture(scope="module")
def df() -> pl.DataFrame:
    d, rep = limpiar(generar(10, 5), leer_diccionario(CFG.ruta("diccionario")), CAT, CFG["f00"])
    assert d is not None and rep["sin_regla"] == []
    return d


def _con(df: pl.DataFrame, **exprs) -> pl.DataFrame:
    return df.with_columns(**exprs)


def _en_filas(df: pl.DataFrame, k: int, col: str, valor) -> pl.DataFrame:
    """Pone `valor` en las primeras `k` filas de `col`."""
    return df.with_columns(pl.when(pl.int_range(pl.len()) < k).then(pl.lit(valor)).otherwise(pl.col(col)).alias(col))


# --------------------------------------------------------------------------
# Con el sintético pasan todas
# --------------------------------------------------------------------------
def test_todas_pasan_con_el_sintetico(df):
    r = qa.correr_qa(df, CAT, Q)
    for k in ("I1", "I2", "I4", "I5", "I8", "I9"):
        assert r[k]["cumplimiento"] == 1.0, (k, r[k])
    # I3 literal (2·c2 = a0 en el MISMO eje) falla a propósito, como en el dato real: los polinomios están permutados.
    assert r["I3"]["cumplimiento"] < 0.5
    # v2.4: el dato real no es perfecto y el sintético lo reproduce a propósito.
    assert 0.995 <= r["I6p"]["cumplimiento"] < 1.0           # ADR-011: is_* no son partición exacta de PitchCall
    assert r["I6p"]["whiff_implica_strike_swinging"] == 1.0
    assert r["I7"]["cumplimiento"] < 0.95                    # A estricto: hay medias entradas de 2 outs (ADR-012)
    # B amplio: pide estado previo Outs = 2. Una media entrada que perdió su último turno ya no tiene esas filas, así
    # que B cae justo por ellas (en el dato real, 91.98 %): ya no es la compuerta, solo se reporta (v2.5).
    assert 0.85 <= r["I7"]["B_no_finales"] < 0.97
    assert r["I7"]["inconsistentes"] >= 1                    # medias entradas con >= 4 outs
    assert r["I10"]["violaciones"] == 3                      # las filas sembradas con Outs = 3
    assert r["I4"]["pendiente_origen"] == pytest.approx(1.0)


def test_los_nulos_no_son_violaciones(df):
    """SpinAxis/Tilt/Extension nulos reales no bajan el cumplimiento: no se evalúan."""
    assert df["SpinAxis"].null_count() > 0
    assert qa.i5_tilt_spinaxis(df)["n"] == df.select("Tilt", "SpinAxis").drop_nulls().height


# --------------------------------------------------------------------------
# Violaciones sembradas
# --------------------------------------------------------------------------
def test_i1_detecta_speeddrop_alterado(df):
    r = qa.i1_speeddrop(_en_filas(df, 50, "SpeedDrop", 99.0))
    assert r["cumplimiento"] < 1.0 and r["cumplimiento"] == pytest.approx(1 - 50 / r["n"], abs=1e-3)


def test_i2_detecta_conteo_incoherente(df):
    r = qa.i2_conteo(_en_filas(df, 7, "count", "9-9"))
    assert r["cumplimiento"] == pytest.approx(1 - 7 / r["n"])


_IDENT = {"X": ("x", 1), "Y": ("y", 1), "Z": ("z", 1)}


def test_i3_detecta_polinomio_y_reporta_la_razon():
    ok = generar(6, 7, sucio=False, convencion_polinomio=_IDENT)         # polinomios = 9P en el mismo eje
    assert qa.i3_polinomio(ok)["cumplimiento"] == 1.0
    mal = ok.with_columns(PitchTrajectoryZc2=pl.col("PitchTrajectoryZc2") * 2)
    r = qa.i3_polinomio(mal)
    assert r["cumplimiento"] < 0.01
    assert r["por_eje"]["Z"]["razon_mediana_2c2_sobre_a0"] == pytest.approx(2.0)
    assert r["por_eje"]["X"]["cumplimiento"] == 1.0


def test_i3_literal_falla_con_la_convencion_real_y_no_es_un_error_de_codigo(df):
    """El dato real dio I3 = 0 %: los ejes del polinomio están permutados (ADR-010 enmendado)."""
    r = qa.i3_polinomio(df)
    assert r["cumplimiento"] < 0.01 and r["por_eje"]["Y"]["razon_mediana_2c2_sobre_a0"] != pytest.approx(1.0, abs=0.1)


def test_i4_detecta_pendiente_fuera_de_rango(df):
    mal = _con(df, InducedVertBreak=pl.col("VertBreak") + (pl.col("InducedVertBreak") - pl.col("VertBreak")) * 1.3)
    r = qa.i4_gravedad(mal)
    assert r["cumplimiento"] == 0.0 and r["pendiente_origen"] == pytest.approx(1.3, rel=1e-3)


def test_i5_detecta_tilt_sin_relacion_y_acepta_desfase_y_espejo(df):
    azar = _con(df, SpinAxis=((pl.int_range(pl.len()) * 137) % 360).cast(pl.Float64))
    assert qa.i5_tilt_spinaxis(azar)["cumplimiento"] == 0.0
    # El desfase y el espejo no son violaciones: se aprenden.
    desfasado = _con(df, SpinAxis=(pl.col("SpinAxis") + 180) % 360)
    espejo = _con(df, SpinAxis=(360 - pl.col("SpinAxis")) % 360)
    assert qa.i5_tilt_spinaxis(desfasado)["cumplimiento"] == 1.0
    r = qa.i5_tilt_spinaxis(espejo)
    assert r["cumplimiento"] == 1.0 and r["espejo"] is True


def test_i6p_detecta_flags_y_foul_mal_marcado(df):
    mal_suma = qa.i6p_flags(_en_filas(df, 10, "is_swing", False), CAT["pitch_call_h"]["contacto"])
    assert mal_suma["cumplimiento"] < 1.0
    foul = df.filter(pl.col("pitch_call_h") == "Foul").head(5)["PitchUID"].to_list()
    mal_cont = df.with_columns(pl.when(pl.col("PitchUID").is_in(foul)).then(False)
                               .otherwise(pl.col("is_contact")).alias("is_contact"))
    r = qa.i6p_flags(mal_cont, CAT["pitch_call_h"]["contacto"])
    assert r["contacto_equivale_a_foul_o_inplay"] < 1.0


def test_i6p_excluye_las_filas_undefined(df):
    n_und = df.filter(pl.col("pitch_call_h") == "Undefined").height
    assert n_und > 0
    assert qa.i6p_flags(df, CAT["pitch_call_h"]["contacto"])["n"] <= df.height - n_und


def test_i7_detecta_media_entrada_incompleta(df):
    from pitcheo.limpieza import tabla_medias_entradas
    h = tabla_medias_entradas(df).filter(pl.col("A") & ~pl.col("final")).head(1)   # una que SÍ cumple A y B
    g, i, m = h["game_anon_id"][0], h["Inning"][0], h["mitad"][0]
    mal = df.with_columns(pl.when((pl.col("game_anon_id") == g) & (pl.col("Inning") == i)
                                  & (pl.col("Top/Bottom") == m)).then(0).otherwise(pl.col("OutsOnPlay"))
                          .alias("OutsOnPlay"))
    antes, despues = qa.i7_outs_media_entrada(df), qa.i7_outs_media_entrada(mal)
    assert despues["cumplimiento"] < antes["cumplimiento"]          # A cae: ahora suma 0 outs
    assert despues["B_no_finales"] == antes["B_no_finales"]         # B no mira la suma: sigue habiendo estado 2


def test_i8_detecta_signo_de_horzbreak_sin_invertir(df):
    mal = _con(df, HorzBreak=pl.col("HorzBreak").abs())
    r = qa.i8_signo_horzbreak(mal, Q["i8_min_filas"])
    assert r["cumplimiento"] < 1.0 and r["n"] > 0


def test_i9_detecta_juego_con_dos_cubetas(df):
    g = df["game_anon_id"][0]
    en_g = pl.col("game_anon_id") == g
    mitad = pl.int_range(pl.len()).over("game_anon_id") % 2 == 0
    mal = df.with_columns(pl.when(en_g & mitad).then(pl.lit("Medium Altitude"))
                          .when(en_g).then(pl.lit("No Altitude"))
                          .otherwise(pl.col("altitude_category").cast(pl.Utf8)).alias("altitude_category"))
    r = qa.i9_altitud_constante(mal)
    assert r["cumplimiento"] < 1.0 and r["juegos_incoherentes"] == 1


def test_i10_cuenta_violaciones_de_outs(df):
    r = qa.i10_outs_validos(_en_filas(df, 4, "Outs", 3))
    assert r["violaciones"] >= 4 and "3" in " ".join(r["valores_invalidos"])


# --------------------------------------------------------------------------
# ADR-010 (enmienda v2.5) — los polinomios son los 9P en ejes permutados, con origen de tiempo en la liberación
# --------------------------------------------------------------------------
def _sintetico(**kw) -> pl.DataFrame:
    return generar(8, 21, sucio=False, **kw)


def test_adr010_convencion_real_se_reconoce_como_equivalente():
    d, v = generar(8, 21, sucio=False, con_verdad=True)
    r = qa.matriz_polinomios(d)
    assert r["existe"] and r["decision"] == "equivalentes"
    assert r["permutacion"] == {"X": "y", "Y": "z", "Z": "x"} and set(r["signos"].values()) == {1}
    assert r["r2_c2_pares_min"] > 0.999999 and r["r2_c2_conjunta_min"] > 0.999999
    assert r["r2_c1_con_ts_min"] > 0.999999
    assert r["escala_2c2_sobre_a0"]["Y"] == pytest.approx(1.0)
    assert r["t_s"]["mediana_s"] == pytest.approx(float(np.median(v["t_s"])), abs=1e-9)
    assert r["t_s"]["mediana_s"] < 0 and r["t_s"]["p99_s"] < 0          # el polinomio arranca ANTES de y = 50 ft


def test_adr010_por_que_v24_los_rechazo_c1_no_encaja_con_v0_a_secas():
    r = qa.matriz_polinomios(_sintetico())
    sin_ts = {p: v["r2"] for p, v in r["c1_sin_ts"].items()}
    assert min(sin_ts.values()) < 0.999                      # igual que en el dato real (0.9889 en el eje vertical)
    assert min(v["r2"] for v in r["c1_con_ts"].values()) > 0.999999
    assert r["c1_con_ts"]["X"]["referencia"] and not r["c1_con_ts"]["Y"]["referencia"]


def test_adr010_t_s_por_lanzamiento_recupera_la_verdad():
    d, v = generar(8, 21, sucio=False, con_verdad=True)
    ts = qa.t_s_por_lanzamiento(d, qa.matriz_polinomios(d))
    assert np.nanmax(np.abs(ts - v["t_s"])) < 1e-9
    sucio, vs = generar(6, 22, con_verdad=True)                              # con nulos reales: NaN donde falta c1
    ts2 = qa.t_s_por_lanzamiento(sucio, qa.matriz_polinomios(sucio))
    ok = np.isfinite(ts2)
    assert ok.mean() > 0.95 and np.max(np.abs(ts2[ok] - vs["t_s"][ok])) < 1e-9


def test_adr010_matriz_tiene_las_tres_familias_y_nueve_celdas():
    r = qa.matriz_polinomios(_sintetico())
    assert set(r["matriz"]) == {"c0", "c1", "c2"}
    for fam in r["matriz"].values():
        assert {(p, q) for p in fam for q in fam[p]} == {(p, q) for p in "XYZ" for q in "xyz"}
        assert all(set(c) == {"pendiente", "intercepto", "r2"} for p in fam.values() for c in p.values())
    assert r["matriz"]["c2"]["X"]["y"]["pendiente"] == pytest.approx(0.5)      # X→y: c2 = a0 / 2
    assert r["matriz"]["c2"]["X"]["x"]["r2"] < 0.5                            # y las demás celdas no encajan


def test_adr010_permutacion_con_signo_sin_desfase_tambien_es_equivalente():
    """Un eje con razón ≈ -1 y otros permutados, pero con el origen de tiempo en y = 50 ft (t_s = 0)."""
    conv = {"X": ("z", -1), "Y": ("y", -1), "Z": ("x", 1)}
    d = _sintetico(convencion_polinomio=conv)
    r = qa.matriz_polinomios(d)
    assert r["existe"] and r["permutacion"] == {"X": "z", "Y": "y", "Z": "x"}
    assert r["signos"] == {"X": -1, "Y": -1, "Z": 1}
    assert abs(r["t_s"]["mediana_s"]) < 1e-9
    assert qa.i3_polinomio(d)["cumplimiento"] < 0.5          # I3 literal falla pero el mapeo la explica


def test_adr010_polinomios_sin_relacion_se_declaran_no_canonicos():
    r = qa.matriz_polinomios(_sintetico(convencion_polinomio="ruido"))
    assert not r["existe"] and r["decision"] == "no_canonicos"
    assert r["r2_c2_pares_min"] < 0.5


def test_adr010_estima_el_desplazamiento_de_tiempo():
    d = _sintetico(convencion_polinomio=_IDENT)
    ts = 0.03
    for p, (r0, v0, a0) in {"X": ("x0", "vx0", "ax0"), "Y": ("y0", "vy0", "ay0"), "Z": ("z0", "vz0", "az0")}.items():
        d = d.with_columns(
            (pl.col(v0) + pl.col(a0) * ts).alias(f"PitchTrajectory{p}c1"),                       # c1 = v(ts)
            (pl.col(r0) + pl.col(v0) * ts + 0.5 * pl.col(a0) * ts**2).alias(f"PitchTrajectory{p}c0"))
    r = qa.matriz_polinomios(d)
    assert r["existe"]
    assert r["t_s"]["mediana_s"] == pytest.approx(ts, abs=1e-6) and r["t_s"]["rango_intercuartil_s"] < 1e-6
    assert all(v == pytest.approx(ts, abs=1e-6) for v in r["t_s_mediana_por_eje"].values())


def test_adr010_marco_rotado_no_es_permutacion_pero_la_regresion_conjunta_lo_ve():
    """c2 en un marco rotado (mezcla de x y z): ninguna permutación con signo sirve; la conjunta, sí."""
    d = _sintetico(convencion_polinomio=_IDENT).with_columns(
        (0.5 * (0.8 * pl.col("ax0") + 0.6 * pl.col("az0"))).alias("PitchTrajectoryXc2"),
        (0.5 * (-0.6 * pl.col("ax0") + 0.8 * pl.col("az0"))).alias("PitchTrajectoryZc2"))
    r = qa.matriz_polinomios(d)
    assert not r["existe"] and r["decision"] == "no_canonicos"
    rot = r["rotacion"]["c2"]["X"]
    assert rot["r2"] > 0.999999 and rot["coef_xyz"] == pytest.approx([0.4, 0.0, 0.3], abs=1e-6)


def test_adr010_pocos_datos_no_revienta():
    assert qa.matriz_polinomios(_sintetico().head(20))["decision"] == "sin_datos_suficientes"


# --------------------------------------------------------------------------
# ADR-011 — discrepancias is_* × pitch_call_h
# --------------------------------------------------------------------------
def test_adr011_tabla_de_discrepancias(df):
    t = qa.discrepancias_flags(df, CAT)
    assert set(t) == {"es_swing", "es_whiff", "es_contacto", "es_bip", "es_hbp"}
    assert t["es_whiff"]["discrepantes"] == 0 and t["es_bip"]["discrepantes"] == 0
    assert 0.1 < t["es_contacto"]["pct_discrepantes"] < 0.6          # ~0.25 %, como en el dato real
    mal = [f for f in t["es_contacto"]["tabla"] if f["derivada_valor"] != f["bandera_valor"]]
    assert mal and {f["pitch_call_h"] for f in mal} == {"Foul"}      # solo los fouls marcan distinto
    assert sum(f["n"] for f in t["es_contacto"]["tabla"]) == t["es_contacto"]["n"]   # cada combinación con su n


def test_adr011_is_hit_by_pitch_siempre_cero_se_ve_en_la_tabla(df):
    t = qa.discrepancias_flags(df, CAT)["es_hbp"]
    n_hbp = df.filter(pl.col("pitch_call_h") == "HitByPitch").height
    assert t["discrepantes"] == n_hbp > 0
    assert {f["bandera_valor"] for f in t["tabla"]} == {False}


def test_adr011_ignora_undefined(df):
    n_und = df.filter(pl.col("pitch_call_h") == "Undefined").height
    assert n_und > 0 and qa.discrepancias_flags(df, CAT)["es_swing"]["n"] == df.height - n_und


# --------------------------------------------------------------------------
# ADR-012 — diagnóstico de las medias entradas de 2 outs
# --------------------------------------------------------------------------
def test_adr012_dos_outs_son_sobre_todo_turno_final_perdido_y_una_minoria_turno_incompleto(df):
    r = qa.diagnostico_dos_outs(df)
    d2, d3, cla = r["dos_outs"], r["tres_outs"], r["clasificacion_no_finales"]
    assert d2["n"] > 0 and d3["n"] > d2["n"]
    assert 3 < cla["pct_turno_incompleto"] < 30 and cla["pct_turno_final_perdido"] > 70    # real: 9.5 % / 90 %
    assert cla["turno_incompleto"] + cla["turno_final_perdido"] == cla["n"]
    assert d3["pct_con_turno_incompleto"] < 15                        # solo ruido (ids nulos)
    assert set(d2["eventos_terminales_por_media_entrada"]) == {"K", "OUT_BIP", "SAC", "BB", "HBP", "ROE"}
    assert d2["outs_implicados_por_eventos_menos_OutsOnPlay"].get("0", 0) > 0.5 * d2["n"]
    assert d2["ponches_por_out_registrado"] is not None and d3["ponches_por_out_registrado"] is not None


def test_adr012_outs_on_play_por_evento_cuenta_el_out_de_los_ponches(df):
    t = qa.diagnostico_dos_outs(df)["outs_on_play_x_evento_terminal"]
    k = {f["OutsOnPlay"]: f["n"] for f in t if f["evento"] == "K"}
    assert set(k) <= {0, 1} and k.get(1, 0) > 0.95 * sum(k.values())
    assert {f["evento"] for f in t} >= {"K", "BB", "OUT_BIP", "NO_TERMINAL"}


def test_adr012_sin_dos_outs_no_revienta(df):
    solo3 = df.filter(pl.col("media_entrada_A"))
    assert qa.diagnostico_dos_outs(solo3)["dos_outs"] == {"n": 0}


# --------------------------------------------------------------------------
# ADR-014 — marco temporal de los 9P, vía correr_extras
# --------------------------------------------------------------------------
def test_adr014_correr_extras_recupera_t_s_plano_y_signo(df):
    ex = qa.correr_extras(df, CAT, Q, CFG["f00"]["gates"], CFG["fisica"], seed=1)
    cal = ex["calibracion_9p"]
    assert (cal["elegida"]["signo"], round(cal["elegida"]["y_plano_ft"], 6)) == (-1, round(17 / 12, 6))
    assert cal["zonetime"]["mediana"] < 1e-9 and cal["zonetime_cruda"]["mediana"] > 0.02     # ZoneTime ≠ t_p
    assert ex["polinomios"]["decision"] == "equivalentes"


def test_adr014_sin_equivalencia_no_hay_t_s_y_zonetime_no_se_verifica():
    from pitcheo.io import leer_diccionario
    from pitcheo.limpieza import limpiar
    d, _ = limpiar(generar(8, 21, convencion_polinomio="ruido"), leer_diccionario(CFG.ruta("diccionario")), CAT,
                   CFG["f00"])
    ex = qa.correr_extras(d, CAT, Q, CFG["f00"]["gates"], CFG["fisica"], seed=1)
    assert ex["polinomios"]["decision"] == "no_canonicos" and ex["calibracion_9p"]["zonetime"] is None


# --------------------------------------------------------------------------
# ADR-015 — clasificación de las medias entradas de 2 outs, tasa por cubeta y π̂_K
# --------------------------------------------------------------------------
def test_wilson_valores_conocidos():
    lo, hi = qa.wilson(50, 100)
    assert (lo, hi) == pytest.approx((0.4038, 0.5962), abs=1e-3)
    lo, hi = qa.wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = qa.wilson(10, 10)
    assert hi == 1.0 and lo == pytest.approx(0.7225, abs=1e-3)
    assert all(np.isnan(x) for x in qa.wilson(0, 0))


def _entrada(game, year, cub, inning, mitad, turnos, extra_incompleto=0):
    """Una media entrada: `turnos` = eventos terminales de cada bateador (un lanzamiento por turno).

    `extra_incompleto` agrega bateadores con lanzamientos pero SIN evento terminal (el 3er out sin lanzamiento).
    """
    filas, outs = [], 0
    for i, ev in enumerate(turnos):
        o = int(ev in ("K", "OUT_BIP", "SAC"))
        filas.append({"game_anon_id": game, "year": year, "altitude_category_h": cub, "Inning": inning,
                      "Top/Bottom": mitad, "batter_anon_id": f"{game}_{inning}{mitad}_b{i}", "Outs": outs,
                      "OutsOnPlay": o, "evento_terminal": ev})
        outs += o
    for j in range(extra_incompleto):
        filas.append({"game_anon_id": game, "year": year, "altitude_category_h": cub, "Inning": inning,
                      "Top/Bottom": mitad, "batter_anon_id": f"{game}_{inning}{mitad}_x{j}", "Outs": outs,
                      "OutsOnPlay": 0, "evento_terminal": None})
    return filas


@pytest.fixture(scope="module")
def mini():
    """Dos juegos (cubetas distintas), 4 medias entradas cada uno; la 4.ª es la final de cada juego."""
    f = []
    # g1 · No Altitude · 2024
    f += _entrada("g1", 2024, "No Altitude", 1, "Top", ["K", "K", "K"])                       # 3 outs
    f += _entrada("g1", 2024, "No Altitude", 1, "Bottom", ["K", "OUT_BIP"], extra_incompleto=1)   # 2 outs, turno incompleto
    f += _entrada("g1", 2024, "No Altitude", 2, "Top", ["K", "K"])                            # 2 outs, turno final perdido
    f += _entrada("g1", 2024, "No Altitude", 2, "Bottom", ["K", "K", "K"])                    # 3 outs (final)
    # g2 · Extreme Altitude · 2024
    f += _entrada("g2", 2024, "Extreme Altitude", 1, "Top", ["OUT_BIP", "OUT_BIP", "OUT_BIP"])
    f += _entrada("g2", 2024, "Extreme Altitude", 1, "Bottom", ["K", "K"])                    # perdido
    f += _entrada("g2", 2024, "Extreme Altitude", 2, "Top", ["OUT_BIP", "OUT_BIP"])           # perdido
    f += _entrada("g2", 2024, "Extreme Altitude", 2, "Bottom", ["OUT_BIP", "OUT_BIP", "OUT_BIP"])   # final
    return pl.DataFrame(f, schema_overrides={"evento_terminal": pl.Utf8})


def test_adr015_clasificacion_incompleto_vs_perdido_a_mano(mini):
    r = qa.diagnostico_dos_outs(mini)
    cla = r["clasificacion_no_finales"]
    assert cla == {"n": 4, "turno_incompleto": 1, "turno_final_perdido": 3,
                   "pct_turno_incompleto": 25.0, "pct_turno_final_perdido": 75.0}
    assert r["dos_outs"]["n"] == 4 and r["tres_outs"]["n"] == 4
    assert r["dos_outs"]["pct_con_turno_incompleto"] == 25.0


def test_adr015_tasas_por_cubeta_a_mano_con_wilson(mini):
    pt = qa.analisis_perdida_turnos(mini, 4, 20, 1)
    por = {r["cubeta"]: r for r in pt["por_cubeta"]}
    assert por["No Altitude"]["medias_entradas"] == 3 and por["No Altitude"]["turno_final_perdido"] == 1
    assert por["No Altitude"]["tasa_turno_final_perdido"] == pytest.approx(1 / 3)
    assert por["Extreme Altitude"]["tasa_turno_final_perdido"] == pytest.approx(2 / 3)
    assert por["Extreme Altitude"]["ic95_wilson"] == pytest.approx(list(qa.wilson(2, 3)))
    assert pt["rango_pp"] == pytest.approx(100 / 3)                       # 66.7 − 33.3
    assert pt["turnos_finales_perdidos_M"] == 3 and pt["medias_entradas_no_finales"] == 6
    ca = {(r["cubeta"], r["year"]): r["medias_entradas"] for r in pt["por_cubeta_anio"]}
    assert ca == {("No Altitude", 2024): 3, ("Extreme Altitude", 2024): 3}


def test_adr015_deficits_y_pi_k_a_mano(mini):
    """3 outs: K = (3+3+0+0)/4 = 1.5, OUT_BIP = 1.5.  2 outs: K = (1+2+2+0)/4 = 1.25, OUT_BIP = 0.75."""
    d = qa.analisis_perdida_turnos(mini, 4, 50, 1)["todas_las_de_2_outs"]
    assert d["deficit"]["K"]["estimado"] == pytest.approx(0.25)
    assert d["deficit"]["OUT_BIP"]["estimado"] == pytest.approx(0.75)
    assert d["deficit"]["SAC"]["estimado"] == pytest.approx(0.0)
    assert d["pi_k"]["estimado"] == pytest.approx(0.25)
    lo, hi = d["pi_k"]["ic95"]
    assert lo <= 0.25 <= hi and (d["n_dos"], d["n_tres"]) == (4, 4)


def test_adr015_el_bootstrap_es_reproducible_con_la_misma_semilla(mini):
    a = qa.analisis_perdida_turnos(mini, 4, 100, 7)["todas_las_de_2_outs"]["pi_k"]["ic95"]
    b = qa.analisis_perdida_turnos(mini, 4, 100, 7)["todas_las_de_2_outs"]["pi_k"]["ic95"]
    assert a == b


def test_adr015_los_finales_no_cuentan_en_las_tasas(mini):
    pt = qa.analisis_perdida_turnos(mini, 4, 20, 1)
    assert sum(r["medias_entradas"] for r in pt["por_cubeta"]) == 6      # 8 medias entradas − 2 finales


def test_adr015_dispersion_por_juego_a_mano(mini):
    pj = qa.analisis_perdida_turnos(mini, 4, 20, 1)["por_juego"]
    assert pj["juegos"] == 2 and pj["tasa_media"] == pytest.approx(0.5)          # 3 perdidas de 6
    assert pj["pct_juegos_con_al_menos_una"] == 100.0 and pj["pct_juegos_con_mas_de_dos"] == 0.0


@pytest.fixture(scope="module")
def regimenes():
    """Dos sintéticos con la MISMA mecánica de pérdida pero verdades de π_K muy distintas."""
    from pitcheo.io import leer_diccionario
    from pitcheo.limpieza import limpiar
    dic, out = leer_diccionario(CFG.ruta("diccionario")), {}
    for nombre, p in (("mcar", {"K": 0.12, "OUT_BIP": 0.12}), ("mnar", {"K": 0.30, "OUT_BIP": 0.015})):
        d0, v = generar(30, 8, con_verdad=True, p_perdida_tipo=p)
        d, _ = limpiar(d0, dic, CAT, CFG["f00"])
        out[nombre] = (qa.analisis_perdida_turnos(d, 4, 300, 1), v)
    return out


def test_adr015_pi_k_es_insensible_a_la_perdida_selectiva_de_ponches(regimenes):
    """Hallazgo (D01): el estimador de déficits de §1.3 mide los ponches entre los terceros outs REGISTRADOS."""
    (pt_a, v_a), (pt_b, v_b) = regimenes["mcar"], regimenes["mnar"]
    est_a = pt_a["todas_las_de_2_outs"]["pi_k"]["estimado"]
    est_b = pt_b["todas_las_de_2_outs"]["pi_k"]["estimado"]
    assert v_b["pi_k"] - v_a["pi_k"] > 0.35                    # las verdades sembradas difieren mucho...
    assert abs(est_b - est_a) < 0.2                            # ...y el estimador casi no se entera
    assert est_b < v_b["pi_k"] - 0.25                          # y subestima claramente cuando el ponche se pierde más
    assert 0.15 < est_a < 0.5 and 0.15 < est_b < 0.5           # ≈ fracción de ponches entre los outs


def test_adr015_g08_la_perdida_uniforme_pasa_y_una_diferencia_por_cubeta_se_detecta(regimenes):
    pt, _ = regimenes["mcar"]
    assert pt["rango_pp"] < CFG["f00"]["gates"]["g08_rango_pp"]
    from pitcheo.io import leer_diccionario
    from pitcheo.limpieza import limpiar
    d0, _ = generar(30, 8, con_verdad=True, p_perdida_cubeta={"Extreme Altitude": 2.0})
    d, _ = limpiar(d0, leer_diccionario(CFG.ruta("diccionario")), CAT, CFG["f00"])
    con = qa.analisis_perdida_turnos(d, 4, 20, 1)
    por = {r["cubeta"]: r["tasa_turno_final_perdido"] for r in con["por_cubeta"]}
    assert con["rango_pp"] > 3 and por["Extreme Altitude"] > 1.5 * por["No Altitude"]
