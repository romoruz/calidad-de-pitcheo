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
    for k in ("I1", "I2", "I3", "I4", "I5", "I6p", "I7", "I8", "I9"):
        assert r[k]["cumplimiento"] == 1.0, (k, r[k])
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
    h = df.select("game_anon_id", "Inning", "Top/Bottom").unique().head(1)
    g, i, t = h["game_anon_id"][0], h["Inning"][0], h["Top/Bottom"][0]
    mal = df.with_columns(pl.when((pl.col("game_anon_id") == g) & (pl.col("Inning") == i)
                                  & (pl.col("Top/Bottom") == t)).then(0).otherwise(pl.col("OutsOnPlay"))
                          .alias("OutsOnPlay"))
    assert qa.i7_outs_media_entrada(mal)["cumplimiento"] < qa.i7_outs_media_entrada(df)["cumplimiento"]


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
