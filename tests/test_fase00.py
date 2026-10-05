"""F0 de punta a punta sobre el sintético: compuertas, parquet particionado, reporte y fallo por 'sin regla'."""
from __future__ import annotations

import json

import polars as pl
import pytest

from pitcheo import cli, fase00
from pitcheo.config import Config
from pitcheo.io import leer_pitches
from pitcheo.sintetico import escribir_tres_formatos, generar

CFG = Config.load()


def _correr(tmp_path, parquet):
    return fase00.correr(CFG, parquet, tmp_path / "pitches.parquet", tmp_path / "reports",
                         tmp_path / "reports" / "logs", tmp_path / "figuras")


@pytest.fixture(scope="module")
def crudo(tmp_path_factory):
    d = tmp_path_factory.mktemp("crudo")
    escribir_tres_formatos(generar(20, 3), d / "stuff_model_df")
    return d / "stuff_model_df.parquet"


def test_f0_pasa_todas_las_compuertas_con_el_sintetico(tmp_path, crudo):
    res = _correr(tmp_path, crudo)
    assert res["ok"], {k: v for k, v in res["gates"].items() if not v["ok"]}
    assert sorted(res["gates"]) == ["G0.1", "G0.2", "G0.3", "G0.4", "G0.5", "G0.6"]


def test_f0_escribe_parquet_particionado_con_columnas_nuevas_y_enums(tmp_path, crudo):
    _correr(tmp_path, crudo)
    carpetas = sorted(p.name for p in (tmp_path / "pitches.parquet").iterdir())
    assert carpetas == ["year=2024", "year=2025", "year=2026"]
    d = leer_pitches(tmp_path / "pitches.parquet").collect()
    bruto = pl.read_parquet(crudo)
    assert d.height == bruto.height and set(bruto.columns) <= set(d.columns)   # las crudas se conservan
    for c in ("familia", "es_sweeper", "pitcher_throws_r", "batter_side_r", "pitch_call_h", "evento_terminal",
              "excluir_modelo", "motivo_exclusion", "altitude_category_h"):
        assert c in d.columns
    assert isinstance(d.schema["familia"], pl.Enum) and isinstance(d.schema["AutoPitchType"], pl.Enum)
    assert d.schema["is_swing"] == pl.Boolean and d.schema["EffectiveVelo"] == pl.Float64


def test_f0_reporte_trae_bloque_tabla_de_eventos_y_sin_filas(tmp_path, crudo):
    _correr(tmp_path, crudo)
    md = (tmp_path / "reports" / "FASE_00.md").read_text(encoding="utf-8")
    for txt in ("Bloque para el orquestador — F00", "play_result × pitch_call_h × KorBB", "ADR-003",
                "Exclusiones de modelos", "G0.6"):
        assert txt in md
    assert "pitch_00" not in md and "pitcher_0" not in md          # ni ids ni filas por lanzamiento
    js = json.loads((tmp_path / "reports" / "fase_00.json").read_text(encoding="utf-8"))
    assert js["sin_regla"] == [] and (tmp_path / "figuras" / "alcance.png").exists()
    assert list((tmp_path / "reports" / "logs").glob("f00_*.log"))


def test_f0_valor_sin_regla_falla_y_no_escribe_parquet(tmp_path, crudo):
    bruto = pl.read_parquet(crudo)
    sucio = bruto.with_columns(
        pl.when(pl.int_range(pl.len()) < 3).then(pl.lit("Nuevo", dtype=pl.Utf8))
        .otherwise(pl.col("AutoPitchType").cast(pl.Utf8)).cast(pl.Categorical).alias("AutoPitchType"))
    p = tmp_path / "sucio.parquet"
    sucio.write_parquet(p)
    res = _correr(tmp_path, p)
    assert not res["ok"] and not res["gates"]["G0.5"]["ok"]
    assert not (tmp_path / "pitches.parquet").exists()              # nada a medias
    md = (tmp_path / "reports" / "FASE_00.md").read_text(encoding="utf-8")
    assert "Nuevo" in md and "NO se escribió" in md and "Bloque para el orquestador" in md


def test_f0_falla_la_compuerta_de_exclusiones(tmp_path, crudo):
    """Si más del 3 % queda excluido (aquí: todo Knuckleball) G0.6 falla pero el reporte se escribe."""
    bruto = pl.read_parquet(crudo)
    n = bruto.height
    exc = bruto.with_columns(
        pl.when(pl.int_range(pl.len()) < int(0.05 * n)).then(pl.lit("Knuckleball", dtype=pl.Utf8))
        .otherwise(pl.col("AutoPitchType").cast(pl.Utf8)).cast(pl.Categorical).alias("AutoPitchType"))
    p = tmp_path / "exc.parquet"
    exc.write_parquet(p)
    res = _correr(tmp_path, p)
    assert not res["gates"]["G0.6"]["ok"] and res["gates"]["G0.5"]["ok"] and not res["ok"]
    assert (tmp_path / "reports" / "FASE_00.md").exists()


def test_cli_f00_sintetico_sale_con_exito(tmp_path):
    cli.main(["f00", "--sintetico", "8", "--out", str(tmp_path / "out")])
    assert (tmp_path / "out" / "reports" / "FASE_00.md").exists()
    assert (tmp_path / "out" / "pitches.parquet").is_dir()


def test_cli_f00_sale_con_codigo_2_si_falla_una_compuerta(tmp_path, monkeypatch):
    forzadas = {g: {"ok": g != "G0.1", "detalle": "forzado"} for g in ("G0.1", "G0.2", "G0.3", "G0.4", "G0.5", "G0.6")}
    monkeypatch.setattr(fase00, "evaluar_gates", lambda *a, **k: forzadas)
    with pytest.raises(SystemExit) as e:
        cli.main(["f00", "--sintetico", "4", "--out", str(tmp_path / "out")])
    assert e.value.code == 2
    assert (tmp_path / "out" / "reports" / "FASE_00.md").exists()   # el reporte se escribe antes de salir
