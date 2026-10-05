"""El generador sintético cumple el diccionario y las identidades I1-I8 de F0."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from pitcheo.config import Config
from pitcheo.io import leer_diccionario
from pitcheo.sintetico import G_FTS2, generar, spinaxis_a_tilt

CFG = Config.load()
DICC = leer_diccionario(CFG.ruta("diccionario"))


@pytest.fixture(scope="module")
def df() -> pl.DataFrame:
    return generar(n_juegos=12, semilla=2026)


# --------------------------------------------------------------------------
# Diccionario
# --------------------------------------------------------------------------
def test_todas_las_columnas_presentes_y_en_orden(df):
    assert list(df.columns) == [s.nombre for s in DICC]


def test_sin_columnas_no_documentadas(df):
    assert set(df.columns) == {s.nombre for s in DICC}


def test_tipos_por_diccionario(df):
    enteros = (pl.Int8, pl.Int16, pl.Int32, pl.Int64)
    for s in DICC:
        dt = df.schema[s.nombre]
        if s.es_entera:
            assert dt in enteros, f"{s.nombre}: {dt} no es entero"
        elif s.es_booleana:
            assert dt == pl.Int8, f"{s.nombre}: {dt} no es Int8"
            vals = set(df[s.nombre].drop_nulls().unique().to_list())
            assert vals <= {0, 1}, f"{s.nombre}: valores {vals} fuera de 0/1"
        elif s.es_numerica:
            assert dt == pl.Float64, f"{s.nombre}: {dt} no es Float64"
        else:
            assert dt == pl.Utf8, f"{s.nombre}: {dt} no es Utf8"


def test_categorias_cerradas(df):
    for s in DICC:
        enum = s.valores_enumerados
        if enum is None:
            continue
        permitidos = {e.strip() for e in enum}
        vistos = set(df[s.nombre].drop_nulls().unique().to_list())
        assert vistos <= permitidos, f"{s.nombre}: {vistos - permitidos} fuera del diccionario"


def test_rangos_enteros(df):
    for s in DICC:
        ri = s.rango_entero
        if ri is None:
            continue
        col = df[s.nombre].drop_nulls()
        if col.len():
            assert col.min() >= ri[0] and col.max() <= ri[1], f"{s.nombre} fuera de {ri}"


def test_ids_con_formato(df):
    assert df["game_anon_id"].str.contains(r"^game_\d{6}$").all()
    assert df["pitcher_anon_id"].str.contains(r"^pitcher_\d{5}$").all()
    assert df["batter_anon_id"].str.contains(r"^batter_\d{5}$").all()
    assert df["catcher_anon_id"].str.contains(r"^catcher_\d{5}$").all()
    assert df["PitchUID"].n_unique() == df.height  # único


# --------------------------------------------------------------------------
# Identidades I1-I8
# --------------------------------------------------------------------------
def test_I1_speeddrop(df):
    d = (df["RelSpeed"] - df["ZoneSpeed"] - df["SpeedDrop"]).abs().max()
    assert d < 0.05


def test_I2_count(df):
    esperado = df["Balls"].cast(pl.Utf8) + "-" + df["Strikes"].cast(pl.Utf8)
    assert (df["count"] == esperado).all()
    assert df["Balls"].max() <= 3 and df["Strikes"].max() <= 2


def test_I3_polinomio(df):
    for eje, acc in (("X", "ax0"), ("Y", "ay0"), ("Z", "az0")):
        c2 = df[f"PitchTrajectory{eje}c2"].to_numpy()
        a0 = df[acc].to_numpy()
        assert np.allclose(2 * c2, a0, rtol=1e-9, atol=1e-9)


def test_I4_caida_gravedad(df):
    izq = (df["InducedVertBreak"] - df["VertBreak"]).to_numpy()
    der = 0.5 * G_FTS2 * df["ZoneTime"].to_numpy() ** 2 * 12.0
    assert np.allclose(izq, der, rtol=1e-6, atol=1e-6)


def test_I5_tilt_biyectivo(df):
    recalc = [spinaxis_a_tilt(a) for a in df["SpinAxis"].to_list()]
    assert (df["Tilt"] == pl.Series(recalc)).all()
    # Correlación circular SpinAxis <-> Tilt (en ángulo) > 0.99.
    def tilt_a_angulo(t):
        h, m = (int(x) for x in t.split(":"))
        return ((h % 12) * 60 + m) / 720.0 * 360.0
    ang = np.radians(np.array([tilt_a_angulo(t) for t in df["Tilt"].to_list()]))
    axis = np.radians(df["SpinAxis"].to_numpy())
    r = np.abs(np.mean(np.exp(1j * (ang - axis))))
    assert r > 0.99


def test_I6_flags_swing(df):
    assert (df["is_swing"] == df["is_whiff"] + df["is_contact"]).all()
    whiffs = df.filter(pl.col("is_whiff") == 1)
    assert (whiffs["PitchCall"] == "StrikeSwinging").all()


def test_I7_outs_por_media_entrada(df):
    g = (df.group_by("game_anon_id", "Inning", "Top/Bottom")
         .agg(pl.col("OutsOnPlay").sum().alias("outs")))
    frac = (g["outs"] == 3).mean()
    assert frac >= 0.90, f"solo {frac:.2%} de medias entradas con 3 outs"


def test_I8_horzbreak_invierte_con_mano(df):
    for tipo in df["AutoPitchType"].unique().to_list():
        sub = df.filter(pl.col("AutoPitchType") == tipo)
        r = sub.filter(pl.col("PitcherThrows") == "Right")["HorzBreak"]
        l = sub.filter(pl.col("PitcherThrows") == "Left")["HorzBreak"]
        if r.len() >= 20 and l.len() >= 20:
            assert r.mean() * l.mean() < 0, f"{tipo}: mismo signo R={r.mean():.2f} L={l.mean():.2f}"
