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


def test_i8_marca_no_informativa_la_falla_de_un_tipo_que_casi_no_rompe(df):
    """v2.6: para cada tipo que falla se reporta la mediana de |HorzBreak| por mano; si es < 2 in, no es informativo."""
    mal = _con(df, HorzBreak=pl.col("HorzBreak").abs())          # todos los tipos pierden el signo opuesto
    r = qa.i8_signo_horzbreak(mal, Q["i8_min_filas"], Q["i8_mediana_min_in"])
    falla = [t for t, v in r["tipos"].items() if v.get("evaluado") and not v["signo_opuesto"]]
    assert falla and set(r["fallas"]) == set(falla)
    for t in falla:
        v = r["tipos"][t]
        assert v["mediana_abs_derecho_in"] > 0 and v["mediana_abs_zurdo_in"] > 0
        assert v["no_informativo"] == (min(v["mediana_abs_derecho_in"], v["mediana_abs_zurdo_in"]) < 2.0)
    # Con el piso en 1000 in toda falla es no informativa; con 0 in, ninguna.
    assert set(qa.i8_signo_horzbreak(mal, Q["i8_min_filas"], 1000.0)["fallas_no_informativas"]) == set(falla)
    assert qa.i8_signo_horzbreak(mal, Q["i8_min_filas"], 0.0)["fallas_no_informativas"] == []
    ok = qa.i8_signo_horzbreak(df, Q["i8_min_filas"])               # sin fallas: nada que marcar
    assert ok["fallas"] == [] and ok["fallas_no_informativas"] == []


def test_i3_se_marca_sustituida_por_g02(df):
    assert "G0.2" in qa.i3_polinomio(df)["sustituida_por"]


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
def test_adr012_dos_outs_son_sobre_todo_out_faltante_y_una_minoria_turno_incompleto(sin_perdida):
    r = qa.diagnostico_dos_outs(sin_perdida[0])
    d2, d3, cla = r["dos_outs"], r["tres_outs"], r["clasificacion_no_finales"]
    assert d2["n"] > 0 and d3["n"] > d2["n"]
    assert 3 < cla["pct_turno_incompleto"] < 30 and cla["pct_out_faltante"] > 70    # real: 9.5 % / 90 %
    assert cla["turno_incompleto"] + cla["out_faltante"] == cla["n"]
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
# ADR-016 — conjunto T, Prop. 16 (r̂, θ̂), Prop. 17 (W, SE_ref) y las reglas G0.8′ / G0.9
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
                      "OutsOnPlay": o, "evento_terminal": ev, "hit_type": None, "Angle": None})
        outs += o
    for j in range(extra_incompleto):
        filas.append({"game_anon_id": game, "year": year, "altitude_category_h": cub, "Inning": inning,
                      "Top/Bottom": mitad, "batter_anon_id": f"{game}_{inning}{mitad}_x{j}", "Outs": outs,
                      "OutsOnPlay": 0, "evento_terminal": None, "hit_type": None, "Angle": None})
    return filas


@pytest.fixture(scope="module")
def mini():
    """Tres juegos hechos a mano. Cada media entrada se anota con su (P, Z): P = 2 outs registrados, Z = nadie en base.

    g1 No Altitude 2024:  1T 3K (no P, Z) · 1B 2K (P, Z) · 2T 1B+3K (no P, no Z) · 2B 1B+2K (P, no Z) · 3T 3K (no P, Z)
                          · 3B 3K = final del juego.
    g2 Extreme 2024:      1T 1B+3K (no P, no Z) · 1B 1B+2K (P, no Z) · 2T BB+2K (P, no Z) · 2B 3K (no P, Z)
                          · 3T 2K (P, Z) · 3B 3K = final.
    g3 No Altitude 2025:  1T 3K · 1B 1B+3K · 2T (con turno incompleto) · 10T 2K (extra inning, corredor colocado: no entra
                          en T) · 10B 3K = final.
    """
    f = []
    f += _entrada("g1", 2024, "No Altitude", 1, "Top", ["K", "K", "K"])
    f += _entrada("g1", 2024, "No Altitude", 1, "Bottom", ["K", "K"])
    f += _entrada("g1", 2024, "No Altitude", 2, "Top", ["1B", "K", "K", "K"])
    f += _entrada("g1", 2024, "No Altitude", 2, "Bottom", ["1B", "K", "K"])
    f += _entrada("g1", 2024, "No Altitude", 3, "Top", ["K", "K", "K"])
    f += _entrada("g1", 2024, "No Altitude", 3, "Bottom", ["K", "K", "K"])
    f += _entrada("g2", 2024, "Extreme Altitude", 1, "Top", ["1B", "K", "K", "K"])
    f += _entrada("g2", 2024, "Extreme Altitude", 1, "Bottom", ["1B", "K", "K"])
    f += _entrada("g2", 2024, "Extreme Altitude", 2, "Top", ["BB", "K", "K"])
    f += _entrada("g2", 2024, "Extreme Altitude", 2, "Bottom", ["K", "K", "K"])
    f += _entrada("g2", 2024, "Extreme Altitude", 3, "Top", ["K", "K"])
    f += _entrada("g2", 2024, "Extreme Altitude", 3, "Bottom", ["K", "K", "K"])
    f += _entrada("g3", 2025, "No Altitude", 1, "Top", ["K", "K", "K"])
    f += _entrada("g3", 2025, "No Altitude", 1, "Bottom", ["1B", "K", "K", "K"])
    f += _entrada("g3", 2025, "No Altitude", 2, "Top", ["K", "K"], extra_incompleto=1)
    f += _entrada("g3", 2025, "No Altitude", 10, "Top", ["K", "K"])
    f += _entrada("g3", 2025, "No Altitude", 10, "Bottom", ["K", "K", "K"])
    return pl.DataFrame(f, schema_overrides={"evento_terminal": pl.Utf8, "hit_type": pl.Utf8, "Angle": pl.Float64})


def test_adr012_clasificacion_incompleto_vs_out_faltante_a_mano(mini):
    r = qa.diagnostico_dos_outs(mini)
    # No finales de 2 outs: g1 1B, 2B · g2 1B, 2T, 3T · g3 2T (turno incompleto) · g3 10T.
    assert r["clasificacion_no_finales"] == {"n": 7, "turno_incompleto": 1, "out_faltante": 6,
                                             "pct_turno_incompleto": pytest.approx(100 / 7, abs=1e-2),
                                             "pct_out_faltante": pytest.approx(600 / 7, abs=1e-2)}


def test_adr016_conjunto_T_a_mano_con_lo_que_excluye_cada_filtro(mini):
    T, pasos = qa.conjunto_T(mini)
    por = {p["filtro"]: p for p in pasos}
    assert por["todas las medias entradas"]["quedan"] == 17
    assert por["no es la final del juego"]["excluye"] == 3                      # 3B de g1, 3B de g2, 10B de g3
    assert por["Inning ≤ 9"]["excluye"] == 1 and por["Inning ≤ 9"]["excluye_solo_este"] == 2   # 10T (y 10B, ya final)
    assert por["consistente (outs < 4)"]["excluye"] == 0
    assert por["sin turno incompleto"]["excluye"] == 1                          # g3 2T
    assert T.height == 12 and T["Inning"].max() <= 9
    assert int(T["P"].sum()) == 5 and int(T["Z"].sum()) == 6 and int(T["PZ"].sum()) == 2


def test_adr016_extra_innings_con_corredor_colocado_no_entran_en_T(mini):
    """El 10T de g3 tiene 2 outs y nadie en base (P y Z): si entrara, inflaría r̂. El filtro Inning ≤ 9 lo deja fuera."""
    t_todas = qa._medias_con_eventos(mini)
    extra = t_todas.filter((pl.col("Inning") == 10) & (pl.col("outs") == 2))
    assert extra.height == 1 and sum(int(extra[f"ev_{e}"].sum()) for e in qa._EV_BASE) == 0   # nadie llegó a base
    T, _ = qa.conjunto_T(mini)
    assert T.filter(pl.col("Inning") > 9).height == 0
    p16 = qa.prop16(T, 50, 1)
    assert p16["global"]["PZ"] == 2                                              # sin el 10T serían 3


def test_adr016_prop16_a_mano(mini):
    """No: nT 7, Z 4, P 2, PZ 1 → f 4/7, p⁰ 1/7, r̂ 1/4, θ̂ (1/4)/(2/7).  Extreme: nT 5, Z 2, P 3, PZ 1 → r̂ 1/2."""
    T, _ = qa.conjunto_T(mini)
    p = qa.prop16(T, 200, 3)
    por = {r["cubeta"]: r for r in p["por_cubeta"]}
    no, ex, gl = por["No Altitude"], por["Extreme Altitude"], p["global"]
    assert (no["medias_entradas"], no["Z"], no["P"], no["PZ"]) == (7, 4, 2, 1)
    assert no["f"] == pytest.approx(4 / 7) and no["p0"] == pytest.approx(1 / 7) and no["r_hat"] == pytest.approx(1 / 4)
    assert no["theta_hat"] == pytest.approx((1 / 4) / (2 / 7))
    assert ex["r_hat"] == pytest.approx(1 / 2) and ex["theta_hat"] == pytest.approx((1 / 2) / (3 / 5))
    assert gl["medias_entradas"] == 12 and gl["r_hat"] == pytest.approx(2 / 6)
    assert gl["theta_hat"] == pytest.approx((2 / 6) / (5 / 12))
    assert p["juegos"] == 3 and p["bootstrap"]["n"] == 200
    for r in p["por_cubeta"] + [gl]:
        assert set(r["ic95"]) == {"f", "tasa_P", "r_hat", "theta_hat"}


def test_adr016_el_bootstrap_de_juegos_es_reproducible_y_depende_de_la_semilla():
    d0, _v = generar(30, 4, con_verdad=True, perdida_cubeta={"No Altitude": 0.1, "Medium Altitude": 0.1,
                                                            "Extreme Altitude": 0.1})
    T, _ = qa.conjunto_T(_limpio(d0))
    a, b = qa.prop16(T, 300, 7)["global"]["ic95"], qa.prop16(T, 300, 7)["global"]["ic95"]
    assert a == b                                                # mismo dato y misma semilla: el mismo intervalo
    assert qa.prop16(T, 300, 8)["global"]["ic95"]["r_hat"] != a["r_hat"]
    lo, hi = a["r_hat"]
    assert 0 < lo <= hi < 1


def test_adr016_prop17_a_mano(mini):
    """m̃_No = 22/7, m̃_Ext = 3; κ̄ = K/turnos = 31/37; W(Γ) = Σ Γr̂/(m̃ + Γr̂); SE_ref = √(κ̄(1−κ̄)(1/n_Ext + 1/n_No))."""
    T, _ = qa.conjunto_T(mini)
    p16 = qa.prop16(T, 20, 1)
    por = {r["cubeta"]: r for r in p16["por_cubeta"]}
    assert por["No Altitude"]["turnos"] == 22 and por["Extreme Altitude"]["turnos"] == 15
    assert por["No Altitude"]["m_tilde"] == pytest.approx(22 / 7) and por["Extreme Altitude"]["m_tilde"] == pytest.approx(3)
    assert p16["global"]["turnos"] == 37 and p16["global"]["ponches"] == 31
    kappa = 31 / 37
    p = qa.prop17(p16["por_cubeta"], kappa, "Extreme Altitude", "No Altitude")
    for g in (1, 2):
        esperado = g * 0.5 / (3 + g * 0.5) + g * 0.25 / (22 / 7 + g * 0.25)
        assert p["W"][str(g)] == pytest.approx(esperado)
    assert p["SE_ref"] == pytest.approx(np.sqrt(kappa * (1 - kappa) * (1 / 15 + 1 / 22)))
    assert p["kappa_bar"] == pytest.approx(kappa)            # una sola cifra, global: no por cubeta
    assert p["W"]["2"] > p["W"]["1"] > 0                      # el parámetro de sensibilidad agranda el ancho


def test_adr016_prop17_sin_la_cubeta_del_contraste_no_es_evaluable(mini):
    T, _ = qa.conjunto_T(mini)
    p16 = qa.prop16(T, 20, 1)
    p = qa.prop17(p16["por_cubeta"], 0.2, "Extreme Altitude", "Otra Cubeta")
    assert p["evaluable"] is False
    assert qa.regla_g08p(p) == {"ok": False, "perdida_ignorable": False, "motivo": "contraste Extreme − No no evaluable"}


def _filas_con_w(w_obj: float, m: float = 4.0, n: int = 10_000) -> list[dict]:
    """Dos cubetas con la misma r̂ elegida para que W(Γ=2) valga `w_obj`: W = 2·2r/(m + 2r)  →  r = W·m / (4 − 2W)."""
    r = w_obj * m / (4 - 2 * w_obj)
    return [{"cubeta": c, "r_hat": r, "m_tilde": m, "turnos": n} for c in ("Extreme Altitude", "No Altitude")]


def test_adr016_g08p_a_ambos_lados_de_3_92_se_ref_y_de_se_ref():
    kappa = 0.2
    se = float(np.sqrt(kappa * (1 - kappa) * (2 / 10_000)))

    def regla(w):
        p = qa.prop17(_filas_con_w(w), kappa, "Extreme Altitude", "No Altitude")
        assert p["SE_ref"] == pytest.approx(se) and p["W"]["2"] == pytest.approx(w)
        return qa.regla_g08p(p)

    r = regla(0.99 * se)
    assert r["ok"] and r["perdida_ignorable"]                              # W ≤ SE_ref  → ignorable
    r = regla(1.01 * se)
    assert r["ok"] and not r["perdida_ignorable"]                          # pasa, pero hay que usar Imbens–Manski
    r = regla(0.99 * 3.92 * se)
    assert r["ok"] and not r["perdida_ignorable"]
    r = regla(1.01 * 3.92 * se)
    assert not r["ok"] and not r["perdida_ignorable"]                      # falla: discrepancia, no se sigue a F1
    assert r["umbral_ic"] == 3.92 and r["umbral_ignorable"] == 1.0


def test_adr016_g09_reglas_de_decision_con_los_umbrales_fijados():
    assert qa.regla_g09([0.0, 0.20]) == "U" and qa.regla_g09([0.10, 0.25]) == "U"       # sup ≤ 0.25 (incluido)
    assert qa.regla_g09([0.10, 0.2501]) == "mezcla"
    assert qa.regla_g09([0.50, 0.90]) == "L" and qa.regla_g09([0.4999, 0.90]) == "mezcla"   # inf ≥ 0.50 (incluido)
    assert qa.regla_g09([0.30, 0.45]) == "mezcla"
    assert qa.regla_g09(None) == "mezcla"                                    # sin dato no se asume U: ruta conservadora
    g = CFG["f00"]["gates"]
    assert (g["g08_k_ic"], g["g08_k_ignorable"], g["g09_u_max"], g["g09_l_min"]) == (3.92, 1.0, 0.25, 0.50)


def test_adr016_las_tasas_informativas_a_mano_con_wilson(mini):
    inf = qa.mecanismo_outs(mini, {"bootstrap_n": 20}, {}, 4, 1)["informativas"]
    por = {r["cubeta"]: r for r in inf["out_faltante_por_cubeta"]}
    # No finales (sin las 3 finales): No = g1 5 + g3 4 = 9 (out faltante: g1 1B, 2B, g3 10T = 3); Extreme = 5 (3).
    assert por["No Altitude"]["medias_entradas"] == 9 and por["No Altitude"]["out_faltante"] == 3
    assert por["Extreme Altitude"]["medias_entradas"] == 5 and por["Extreme Altitude"]["out_faltante"] == 3
    assert por["Extreme Altitude"]["ic95_wilson"] == pytest.approx(list(qa.wilson(3, 5)))
    assert inf["rango_pp"] == pytest.approx(100 * (3 / 5 - 3 / 9))


def test_adr016_no_hay_pi_k_ni_turno_final_perdido_en_los_resultados(mini):
    mo = qa.mecanismo_outs(mini, {"bootstrap_n": 20}, {}, 4, 1)
    txt = repr(mo) + repr(qa.diagnostico_dos_outs(mini))
    assert "pi_k" not in txt and "turno_final_perdido" not in txt
    assert set(mo["informativas"]["deficits_todas_las_de_2_outs"]["deficit"]) == {"K", "OUT_BIP", "SAC"}


def test_adr016_los_deficits_son_informativos_y_a_mano(mini):
    d = qa.mecanismo_outs(mini, {"bootstrap_n": 30}, {}, 4, 1)["informativas"]["deficits_todas_las_de_2_outs"]
    assert (d["n_dos"], d["n_tres"]) == (7, 10)
    # Mismo criterio que el reporte: media por media entrada de las de 3 outs − media de las de 2 outs.
    t = qa._medias_con_eventos(mini)
    for e in ("K", "OUT_BIP", "SAC"):
        esperado = t.filter(pl.col("outs") == 3)[f"ev_{e}"].mean() - t.filter(pl.col("outs") == 2)[f"ev_{e}"].mean()
        assert d["deficit"][e]["estimado"] == pytest.approx(esperado)


# --------------------------------------------------------------------------
# ADR-016 sobre el simulador base-out: (i) ℓ = 0, (ii) ℓ = (0, 3, 6) %, (iii) extra innings
# --------------------------------------------------------------------------
def _limpio(d0):
    d, rep = limpiar(d0, leer_diccionario(CFG.ruta("diccionario")), CAT, CFG["f00"])
    assert d is not None and rep["sin_regla"] == []
    return d


@pytest.fixture(scope="module")
def sin_perdida():
    """(i) Todo el out faltante es U (doble matanza no contada): ℓ = 0 en las tres cubetas."""
    d0, v = generar(300, 11, con_verdad=True)
    d = _limpio(d0)
    return d, v, qa.mecanismo_outs(d, Q, CFG["f00"]["gates"], 4, CFG["seed"])


def test_adr016_i_sin_perdida_theta_es_casi_cero_y_la_tasa_de_P_difiere_por_cubeta(sin_perdida):
    """Reproduce la falla real de v2.5: con ℓ = 0 la tasa de out faltante igual difiere > 3 pp entre cubetas."""
    _d, v, mo = sin_perdida
    assert mo["prop16"]["global"]["theta_hat"] <= 0.05
    assert mo["prop16"]["global"]["ic95"]["theta_hat"][1] <= 0.05
    assert mo["informativas"]["rango_pp"] > 3.0                                  # el antiguo G0.8 habría fallado
    assert mo["G09"]["mecanismo"] == "U" and mo["mecanismo_outs"] == "U"
    assert mo["G08p"]["ok"] and mo["perdida_ignorable"] is True                  # G0.8′ pasa: no falta ningún lanzamiento
    assert sum(v["perdidos"].values()) == 0
    por = {r["cubeta"]: r for r in mo["informativas"]["out_faltante_por_cubeta"]}
    assert por["Extreme Altitude"]["tasa_out_faltante"] > por["No Altitude"]["tasa_out_faltante"]   # más tráfico, más dobles matanzas


def test_adr016_simulador_dobles_matanzas_mal_contadas_calibradas(sin_perdida):
    d, v, _ = sin_perdida
    por_juego = v["dobles_matanzas"] / d["game_anon_id"].n_unique()
    assert 1.4 <= por_juego <= 2.4                                                # calibrado a ≈ 1.6–2.0 por juego
    assert 0.85 <= v["dobles_matanzas_como_1_out"] / v["dobles_matanzas"] <= 0.99   # OutsOnPlay = 1 en ~93 %
    k = d.filter(pl.col("evento_terminal") == "K")["OutsOnPlay"]
    assert (k == 1).all()                                                        # el out del ponche es siempre 1


def test_adr016_ii_la_perdida_sembrada_se_recupera_con_r_hat():
    """ℓ = (0, 3, 6) % por cubeta → r̂_b recupera ℓ_b con ±1 pp (300 juegos: sobran medias entradas con Z = 1)."""
    ell = {"No Altitude": 0.0, "Medium Altitude": 0.03, "Extreme Altitude": 0.06}
    d0, v = generar(300, 11, con_verdad=True, perdida_cubeta=ell)
    d = _limpio(d0)
    mo = qa.mecanismo_outs(d, Q, CFG["f00"]["gates"], 4, CFG["seed"])
    por = {r["cubeta"]: r for r in mo["prop16"]["por_cubeta"]}
    for cub, l_b in ell.items():
        assert abs(por[cub]["r_hat"] - l_b) <= 0.01, (cub, por[cub]["r_hat"], l_b)
    assert por["Extreme Altitude"]["r_hat"] > por["Medium Altitude"]["r_hat"] > por["No Altitude"]["r_hat"]
    assert sum(v["perdidos"].values()) > 0
    assert mo["prop17"]["W"]["2"] > 0                                            # la pérdida distinta por cubeta ensancha W


def test_adr016_iii_extra_innings_con_corredor_colocado_no_entran_en_T():
    d0 = generar(120, 5, p_extra=0.6, p_pickoff_fantasma=1.0)
    d = _limpio(d0)
    t_todas = qa._medias_con_eventos(d)
    extras = t_todas.filter((pl.col("Inning") > 9) & ~pl.col("final") & (pl.col("outs") == 2))
    assert extras.height > 0                                    # el corredor puesto out sin lanzamiento deja 2 outs y Z = 1
    T, pasos = qa.conjunto_T(d)
    assert T.filter(pl.col("Inning") > 9).height == 0 and T["PZ"].sum() == 0
    assert {p["filtro"]: p for p in pasos}["Inning ≤ 9"]["excluye"] > 0
    assert qa.prop16(T, 30, 1)["global"]["r_hat"] == 0.0         # con ℓ = 0 y sin extras, r̂ = 0


# --------------------------------------------------------------------------
# Corroboraciones (a)-(e) y el paquete completo de correr_extras
# --------------------------------------------------------------------------
def test_adr016_corroboraciones_informativas_sobre_el_simulador(sin_perdida):
    _d, _v, mo = sin_perdida
    c = mo["corroboraciones"]
    # (a) U = doble matanza = rodado: P tiene muchos más rodados que T∖P.
    assert c["a_rodados"]["definicion"] == "hit_type == GroundBall"
    assert c["a_rodados"]["P"]["pct"] > c["a_rodados"]["T_menos_P"]["pct"] + 20
    # (b) U no quita lanzamientos: Outs previo nunca arranca > 0 y la mayoría no tiene huecos.
    assert c["b_outs_previo"]["P"]["pct_min_outs_mayor_0"] == 0.0 and c["b_outs_previo"]["T_menos_P"]["pct_hueco_en_outs"] < 5
    # (c) logit: ORs por cubeta con IC, Extreme > 1 contra No Altitude.
    lg = c["c_logit"]
    assert lg["base"] == "No Altitude" and lg["sin_N_h"]["Extreme Altitude"]["OR"] > 1.0
    assert lg["sin_N_h"]["Extreme Altitude"]["ic95"][0] < lg["sin_N_h"]["Extreme Altitude"]["OR"] < \
        lg["sin_N_h"]["Extreme Altitude"]["ic95"][1]
    assert lg["sin_N_h"]["convergio"] is True
    # (d) jugadas con OutsOnPlay >= 2: solo ~7 % de las dobles matanzas; la fracción registrada es pequeña.
    assert c["d_dobles"]["tasa_mlb_ref_por_juego"] == 1.63 and 0 < c["d_dobles"]["fraccion_registrada"] < 0.2
    assert {f["evento"] for f in c["d_dobles"]["por_evento"]} == {"OUT_BIP"}
    # (e) |P| por juego: un evento de juego a tasa constante → dispersión de Pearson ≈ 1.
    e = c["e_poisson"]
    assert 0.7 < e["dispersion_phi"] < 1.4 and sum(h["juegos"] for h in e["histograma"]) == e["juegos"]


def test_adr016_corroboracion_a_cae_a_angulo_si_no_hay_rodados(mini):
    d = mini.with_columns(pl.lit(None, dtype=pl.Utf8).alias("hit_type"), pl.lit(5.0).alias("Angle"),
                          pl.lit("OUT_BIP").alias("evento_terminal"))
    T, _ = qa.conjunto_T(d)
    r = qa.corr_a_rodados(d, T)
    assert r["definicion"] == "Angle < 10°"
    assert r["P"]["pct"] == 100.0 and r["T_menos_P"]["pct"] == 100.0


def test_adr016_correr_extras_trae_el_paquete_de_adr016_y_no_pi_k(sin_perdida):
    d, _v, _mo = sin_perdida
    ex = qa.correr_extras(d, CAT, Q, CFG["f00"]["gates"], CFG["fisica"], seed=CFG["seed"])
    assert "perdida_turnos" not in ex
    mo = ex["mecanismo_outs"]
    assert mo["mecanismo_outs"] in {"U", "L", "mezcla"} and isinstance(mo["perdida_ignorable"], bool)
    assert set(mo["T"]) >= {"pasos", "medias_entradas", "P", "Z", "PZ"}
    assert "pi_k" not in repr(ex)
