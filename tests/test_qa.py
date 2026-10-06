"""Identidades I1-I5, I6′, I7-I10: con el sintético pasan; con violaciones sembradas, cada una se detecta."""
from __future__ import annotations

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
    for k in ("I1", "I2", "I3", "I4", "I5", "I8", "I9"):
        assert r[k]["cumplimiento"] == 1.0, (k, r[k])
    # v2.4: el dato real no es perfecto y el sintético lo reproduce a propósito.
    assert 0.995 <= r["I6p"]["cumplimiento"] < 1.0           # ADR-011: is_* no son partición exacta de PitchCall
    assert r["I6p"]["whiff_implica_strike_swinging"] == 1.0
    assert r["I7"]["cumplimiento"] < 0.95                    # A estricto: hay medias entradas de 2 outs (ADR-012)
    assert r["I7"]["B_no_finales"] >= 0.95                   # B amplio: lo que evalúa G0.3
    assert r["I7"]["inconsistentes"] >= 1                    # medias entradas con >= 4 outs
    assert r["I10"]["violaciones"] == 3                      # las filas sembradas con Outs = 3
    assert r["I3"]["por_eje"]["X"]["razon_mediana_2c2_sobre_a0"] == pytest.approx(1.0)
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


def test_i3_detecta_polinomio_y_reporta_la_razon(df):
    mal = _con(df, PitchTrajectoryZc2=pl.col("PitchTrajectoryZc2") * 2)   # otra convención de tiempo
    r = qa.i3_polinomio(mal)
    assert r["cumplimiento"] < 0.01
    assert r["por_eje"]["Z"]["razon_mediana_2c2_sobre_a0"] == pytest.approx(2.0)
    assert r["por_eje"]["X"]["cumplimiento"] == 1.0


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
# ADR-010 — matriz 3×3 de los polinomios contra los 9P
# --------------------------------------------------------------------------
def _sintetico(**kw) -> pl.DataFrame:
    return generar(8, 21, sucio=False, **kw)


def test_adr010_convencion_identidad_se_reconoce():
    r = qa.matriz_polinomios(_sintetico())
    assert r["existe"] and r["decision"] == "mapeo_con_signo"
    assert r["permutacion"] == {"X": "x", "Y": "y", "Z": "z"} and set(r["signos"].values()) == {1}
    assert r["r2_min_permutacion"] > 0.999999
    assert r["escala_2c2_sobre_a0"]["Y"] == pytest.approx(1.0)
    assert all(v["mediana_s"] == pytest.approx(0.0, abs=1e-9) for v in r["t_s"].values())


def test_adr010_matriz_tiene_las_tres_familias_y_nueve_celdas():
    r = qa.matriz_polinomios(_sintetico())
    assert set(r["matriz"]) == {"c0", "c1", "c2"}
    for fam in r["matriz"].values():
        assert {(p, q) for p in fam for q in fam[p]} == {(p, q) for p in "XYZ" for q in "xyz"}
        assert all(set(c) == {"pendiente", "intercepto", "r2"} for p in fam.values() for c in p.values())
    assert r["matriz"]["c2"]["X"]["x"]["pendiente"] == pytest.approx(0.5)      # c2 = a0 / 2


def test_adr010_permutacion_con_signo_y_eje_invertido():
    """Lo que insinúa el dato real: un eje con razón ≈ -1 y otros permutados."""
    conv = {"X": ("z", -1), "Y": ("y", -1), "Z": ("x", 1)}
    r = qa.matriz_polinomios(_sintetico(convencion_polinomio=conv))
    assert r["existe"] and r["permutacion"] == {"X": "z", "Y": "y", "Z": "x"}
    assert r["signos"] == {"X": -1, "Y": -1, "Z": 1}
    assert r["r2_min_permutacion"] > 0.999999
    # La identidad I3 literal falla, justo como en el dato real, pero el mapeo la explica.
    assert qa.i3_polinomio(_sintetico(convencion_polinomio=conv))["cumplimiento"] < 0.5


def test_adr010_polinomios_sin_relacion_se_declaran_no_canonicos():
    r = qa.matriz_polinomios(_sintetico(convencion_polinomio="ruido"))
    assert not r["existe"] and r["decision"] == "no_canonicos" and r["t_s"] is None
    assert r["r2_min_permutacion"] < 0.5


def test_adr010_estima_el_desplazamiento_de_tiempo():
    d = _sintetico()
    ts = 0.03
    for p, (r0, v0, a0) in {"X": ("x0", "vx0", "ax0"), "Y": ("y0", "vy0", "ay0"), "Z": ("z0", "vz0", "az0")}.items():
        d = d.with_columns(
            (pl.col(v0) + pl.col(a0) * ts).alias(f"PitchTrajectory{p}c1"),                       # c1 = v(ts)
            (pl.col(r0) + pl.col(v0) * ts + 0.5 * pl.col(a0) * ts**2).alias(f"PitchTrajectory{p}c0"))
    r = qa.matriz_polinomios(d)
    assert r["existe"]
    assert all(v["mediana_s"] == pytest.approx(ts, abs=1e-6) for v in r["t_s"].values())


def test_adr010_marco_rotado_no_es_permutacion_pero_la_regresion_conjunta_lo_ve():
    """c2 en un marco rotado (mezcla de x y z): ninguna permutación con signo sirve; la conjunta, sí."""
    d = _sintetico().with_columns(
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
def test_adr012_dos_outs_dejan_turno_incompleto_y_tres_outs_no(df):
    r = qa.diagnostico_dos_outs(df)
    d2, d3 = r["dos_outs"], r["tres_outs"]
    assert d2["n"] > 0 and d3["n"] > d2["n"]
    assert d2["pct_con_turno_incompleto"] > 80                        # 3er out sin lanzamiento: turno cortado
    assert d3["pct_con_turno_incompleto"] < 15                        # solo ruido (ids nulos)
    assert d2["pct_ultima_del_juego"] < 20
    assert set(d2["eventos_terminales_por_media_entrada"]) == {"K", "OUT_BIP", "SAC", "BB", "HBP", "ROE"}
    # los eventos que son outs suman lo mismo que OutsOnPlay: no hay outs "perdidos" en el conteo
    assert d2["outs_implicados_por_eventos_menos_OutsOnPlay"].get("0", 0) > 0.5 * d2["n"]


def test_adr012_outs_on_play_por_evento_cuenta_el_out_de_los_ponches(df):
    t = qa.diagnostico_dos_outs(df)["outs_on_play_x_evento_terminal"]
    k = {f["OutsOnPlay"]: f["n"] for f in t if f["evento"] == "K"}
    assert set(k) <= {0, 1} and k.get(1, 0) > 0.95 * sum(k.values())
    assert {f["evento"] for f in t} >= {"K", "BB", "OUT_BIP", "NO_TERMINAL"}


def test_adr012_sin_dos_outs_no_revienta(df):
    solo3 = df.filter(pl.col("media_entrada_A"))
    assert qa.diagnostico_dos_outs(solo3)["dos_outs"] == {"n": 0}


# --------------------------------------------------------------------------
# 9P como trayectoria canónica
# --------------------------------------------------------------------------
def test_9p_reproducen_la_ubicacion_en_el_plato_y_el_frente(df):
    v = qa.verificar_9p(df)
    assert v["n"] > 0
    for k in ("error_plato_x_ft", "error_plato_z_ft", "error_y_en_zonetime_ft"):
        assert v[k]["p99"] < 1e-6
