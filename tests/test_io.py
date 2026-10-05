"""io.comparar_formatos cumple el criterio 1-4 y detecta diferencias sembradas."""
from __future__ import annotations

import pandas as pd
import pytest

from pitcheo.config import Config
from pitcheo.io import comparar_formatos, leer_diccionario, perfilar_parquet
from pitcheo.sintetico import escribir_tres_formatos, generar

CFG = Config.load()
DICC = leer_diccionario(CFG.ruta("diccionario"))


@pytest.fixture(scope="module")
def tres(tmp_path_factory):
    d = tmp_path_factory.mktemp("raw")
    base = d / "stuff_model_df"
    df = generar(n_juegos=6, semilla=7)
    escribir_tres_formatos(df, base)
    return base


def _rutas(base):
    return (base.with_suffix(".parquet"), base.with_suffix(".pkl"), base.with_suffix(".rds"))


def test_tres_formatos_equivalentes(tres):
    pq, pkl, rds = _rutas(tres)
    rep = comparar_formatos(pq, pkl, rds)
    for nombre in ("pkl", "rds"):
        c = rep["comparaciones"][nombre]
        assert c["estado"] == "comparado", c
        assert c["pitchuid"]["comparables"], (nombre, c["pitchuid"])
        assert c["equivalentes"], (nombre, {k: v for k, v in c["por_columna"].items()
                                            if v["estado"] != "igual"})


def test_detecta_celda_alterada(tres, tmp_path):
    pq, pkl, _ = _rutas(tres)
    df = pd.read_pickle(pkl)
    df.loc[0, "RelSpeed"] = df.loc[0, "RelSpeed"] + 10.0
    malo = tmp_path / "alterado.pkl"
    df.to_pickle(malo)
    rep = comparar_formatos(pq, malo, None)
    c = rep["comparaciones"]["pkl"]
    assert not c["equivalentes"]
    assert c["por_columna"]["RelSpeed"]["estado"] == "distinta"
    assert c["por_columna"]["RelSpeed"]["n_dif"] >= 1


def test_detecta_columna_faltante(tres, tmp_path):
    pq, pkl, _ = _rutas(tres)
    df = pd.read_pickle(pkl).drop(columns=["HorzBreak"])
    malo = tmp_path / "sin_columna.pkl"
    df.to_pickle(malo)
    rep = comparar_formatos(pq, malo, None)
    c = rep["comparaciones"]["pkl"]
    assert "HorzBreak" in c["columnas_solo_en_a"]
    assert not c["equivalentes"]


def test_detecta_id_duplicado(tres, tmp_path):
    pq, pkl, _ = _rutas(tres)
    df = pd.read_pickle(pkl)
    df.loc[1, "PitchUID"] = df.loc[0, "PitchUID"]  # duplica un ID
    malo = tmp_path / "id_dup.pkl"
    df.to_pickle(malo)
    rep = comparar_formatos(pq, malo, None)
    c = rep["comparaciones"]["pkl"]
    assert not c["pitchuid"]["comparables"]
    assert not c["equivalentes"]


def test_perfil_sin_faltantes_ni_extra(tres):
    pq, _, _ = _rutas(tres)
    perfil = perfilar_parquet(pq, DICC)
    assert perfil["faltantes"] == []
    assert perfil["no_documentadas"] == []
    assert perfil["n_filas"] > 0
