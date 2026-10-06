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
                "excluir_modelo", "excluir_cadena", "ADR-010 — ejes de los polinomios", "ADR-011 — banderas is_*",
                "ADR-012 — medias entradas de 2 outs", "OutsOnPlay × evento_terminal", "G0.6"):
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


def _modificar(tmp_path, crudo, **cambios):
    """Copia del crudo con columnas reemplazadas por expresiones; devuelve la ruta."""
    pl.read_parquet(crudo).with_columns(**cambios).write_parquet(tmp_path / "mod.parquet")
    return tmp_path / "mod.parquet"


def test_v24_reporte_trae_matriz_decision_y_diagnostico_en_el_json(tmp_path, crudo):
    _correr(tmp_path, crudo)
    js = json.loads((tmp_path / "reports" / "fase_00.json").read_text(encoding="utf-8"))
    ex = js["extras"]
    assert ex["polinomios"]["decision"] == "mapeo_con_signo" and "matriz" in ex["polinomios"]
    assert ex["dos_outs"]["dos_outs"]["n"] > 0 and ex["discrepancias_flags"]["es_contacto"]["tabla"]
    assert js["exclusiones"]["modelo"]["total"] >= js["exclusiones"]["cadena"]["total"]
    md = (tmp_path / "reports" / "FASE_00.md").read_text(encoding="utf-8")
    assert "mapeo_con_signo" in md and "| polinomio \\ 9P | x | y | z |" in md


def test_v24_g02_pasa_aunque_los_polinomios_sean_no_canonicos(tmp_path):
    """ADR-010: si ninguna permutación encaja, se declaran no canónicos y la compuerta PASA (la canónica es 9P)."""
    p = tmp_path / "ruido.parquet"
    generar(12, 8, convencion_polinomio="ruido").write_parquet(p)
    res = _correr(tmp_path, p)
    assert res["gates"]["G0.2"]["ok"] and "NO canónicos" in res["gates"]["G0.2"]["detalle"]
    assert res["ok"], {k: v for k, v in res["gates"].items() if not v["ok"]}


def test_v24_g02_pasa_con_polinomios_permutados(tmp_path):
    p = tmp_path / "perm.parquet"
    generar(12, 8, convencion_polinomio={"X": ("z", -1), "Y": ("y", -1), "Z": ("x", 1)}).write_parquet(p)
    res = _correr(tmp_path, p)
    assert res["gates"]["G0.2"]["ok"] and "verificación cruzada" in res["gates"]["G0.2"]["detalle"]


def test_v24_g03_falla_si_el_criterio_b_cae_bajo_95(tmp_path, crudo):
    p = _modificar(tmp_path, crudo, Outs=pl.lit(0.0))             # sin estado previo Outs = 2: B = 0 %
    res = _correr(tmp_path, p)
    assert not res["gates"]["G0.3"]["ok"] and "criterio B" in res["gates"]["G0.3"]["detalle"]
    assert (tmp_path / "reports" / "FASE_00.md").exists()


def test_v24_g06_falla_si_excluir_cadena_pasa_de_0_5_pct(tmp_path, crudo):
    n = pl.read_parquet(crudo).height
    p = _modificar(tmp_path, crudo, PitchCall=pl.when(pl.int_range(pl.len()) < int(0.02 * n))
                   .then(pl.lit("Undefined", dtype=pl.Utf8)).otherwise(pl.col("PitchCall").cast(pl.Utf8))
                   .cast(pl.Categorical))
    res = _correr(tmp_path, p)
    assert not res["gates"]["G0.6"]["ok"] and "excluir_cadena" in res["gates"]["G0.6"]["detalle"]


def test_v24_g01_i6p_admite_el_0_25_pct_pero_no_un_1_pct(tmp_path, crudo):
    ok = _correr(tmp_path, crudo)
    assert ok["gates"]["G0.1"]["ok"]                             # el sintético ya trae ~0.25 % de discrepancia
    n = pl.read_parquet(crudo).height
    p = _modificar(tmp_path, crudo, is_contact=pl.when(pl.int_range(pl.len()) < int(0.03 * n))
                   .then(1.0 - pl.col("is_contact")).otherwise(pl.col("is_contact")))
    assert not _correr(tmp_path, p)["gates"]["G0.1"]["ok"]
