"""El generador sintético respeta el diccionario y REPRODUCE cada caso real de D00 (una prueba por caso)."""
from __future__ import annotations

import polars as pl
import pytest

from pitcheo.config import Config
from pitcheo.io import leer_diccionario
from pitcheo.limpieza import cargar_categorias
from pitcheo.sintetico import generar, spinaxis_a_tilt

CFG = Config.load()
DICC = leer_diccionario(CFG.ruta("diccionario"))
CAT = cargar_categorias(CFG.ruta("categorias"))


@pytest.fixture(scope="module")
def df() -> pl.DataFrame:
    return generar(n_juegos=12, semilla=2026)


@pytest.fixture(scope="module")
def limpio() -> pl.DataFrame:
    return generar(n_juegos=12, semilla=2026, sucio=False)


def _vals(df: pl.DataFrame, col: str) -> set:
    return set(df[col].cast(pl.Utf8).drop_nulls().unique().to_list())


# --------------------------------------------------------------------------
# Esquema del diccionario
# --------------------------------------------------------------------------
def test_todas_las_columnas_presentes_y_en_orden(df):
    assert list(df.columns) == [s.nombre for s in DICC]


def test_ids_con_formato_y_pitchuid_unico(df):
    assert df["game_anon_id"].str.contains(r"^game_\d{6}$").all()
    assert df["pitcher_anon_id"].drop_nulls().str.contains(r"^pitcher_\d{5}$").all()
    assert df["batter_anon_id"].drop_nulls().str.contains(r"^batter_\d{5}$").all()
    assert df["catcher_anon_id"].drop_nulls().str.contains(r"^catcher_\d{5}$").all()
    assert df["PitchUID"].n_unique() == df.height


def test_esquema_de_tipos_real(df):
    """Tal como llegan los datos reales (reports/FASE_00_0.md)."""
    assert df.schema["year"] == pl.Int32 and df.schema["in_strike_zone"] == pl.Int32
    assert df.schema["EffectiveVelo"] == pl.Utf8      # el dato real trae EffectiveVelo como texto
    for c in ("AutoPitchType", "PitchCall", "play_result", "Top/Bottom"):
        assert df.schema[c] == pl.Categorical
    for s in DICC:
        if s.nombre in ("year", "in_strike_zone", "EffectiveVelo"):
            continue
        if s.es_booleana or s.es_numerica:           # flags y enteros llegan como Float64
            assert df.schema[s.nombre] == pl.Float64, s.nombre


def test_todo_valor_tiene_regla_en_el_inventario(df):
    """El generador solo emite valores inventariados en config/categorias.yaml."""
    for col, info in CAT["columnas"].items():
        assert _vals(df, col) <= set(info["valores"]), (col, _vals(df, col) - set(info["valores"]))


def test_tilt_sin_cero_a_la_izquierda(df):
    assert spinaxis_a_tilt(0.0) == "12:00"
    assert spinaxis_a_tilt(30.0) == "1:00"
    assert spinaxis_a_tilt(345.0) == "11:30"
    assert df["Tilt"].drop_nulls().str.contains(r"^(1[0-2]|[1-9]):[0-5]\d$").all()


def test_determinista():
    a, b = generar(4, 3), generar(4, 3)
    assert a.equals(b)


# --------------------------------------------------------------------------
# Un caso real por prueba
# --------------------------------------------------------------------------
def test_caso_12_autopitchtype(df):
    esperados = set(CAT["familia"]["mapa"]) - {"Undefined"}
    assert _vals(df, "AutoPitchType") == esperados and len(esperados) == 12


def test_caso_mano_lanzador_undefined_y_nula(df):
    assert "Undefined" in _vals(df, "PitcherThrows")
    assert df["PitcherThrows"].null_count() > 0


def test_caso_bateador_switch_undefined_y_nulo(df):
    assert {"Switch", "Undefined"} <= _vals(df, "BatterSide")
    assert df["BatterSide"].null_count() > 0


def test_caso_tres_foulball_y_undefined(df):
    assert {"FoulBall", "FoulBallFieldable", "FoulBallNotFieldable", "Undefined"} <= _vals(df, "PitchCall")


def test_caso_cubeta_nula_en_juegos_completos_y_sueltos(df):
    nulos = df.filter(pl.col("altitude_category").is_null())
    por_juego = df.group_by("game_anon_id").agg(pl.col("altitude_category").is_null().mean().alias("f"))
    assert nulos.height > 0
    assert (por_juego["f"] == 1.0).any()                                    # un juego entero nulo
    assert ((por_juego["f"] > 0) & (por_juego["f"] < 1)).any()              # filas sueltas


def test_caso_outs_3(df):
    assert (df["Outs"] == 3).sum() >= 3


def test_caso_16_play_result(df):
    assert _vals(df, "play_result") == set(CAT["columnas"]["play_result"]["valores"])
    assert len(_vals(df, "play_result")) == 16


def test_caso_is_hit_by_pitch_siempre_cero_pero_hay_hbp(df):
    assert (df["is_hit_by_pitch"] == 0).all()
    assert (df["PitchCall"].cast(pl.Utf8) == "HitByPitch").any()


def test_caso_ids_nulos_y_efective_velo_texto(df):
    for c in ("pitcher_anon_id", "batter_anon_id", "catcher_anon_id"):
        assert df[c].null_count() > 0
    assert df["EffectiveVelo"].str.contains(r"^\d+(\.\d+)?$").all()


def test_caso_nulos_fisicos(df):
    for c in ("SpinAxis", "Tilt", "VertBreak", "Extension", "SpinRate", "Distance"):
        assert df[c].null_count() > 0, c


def test_sin_sucio_no_hay_defectos(limpio):
    assert _vals(limpio, "PitcherThrows") <= {"Left", "Right"}
    assert "Undefined" not in _vals(limpio, "PitchCall")
    assert limpio["altitude_category"].null_count() == 0
    assert (limpio["Outs"] <= 2).all()
    assert limpio["pitcher_anon_id"].null_count() == 0


def test_la_cubeta_extreme_mezcla_varios_parques():
    """Extreme trae más de una altitud: no se identifica un parque por cubeta (ADR-005)."""
    assert len(CFG["sintetico"]["cubetas"]["Extreme Altitude"]["altitudes_m"]) >= 2
