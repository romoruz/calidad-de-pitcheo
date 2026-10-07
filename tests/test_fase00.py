"""F0 de punta a punta sobre el sintético: compuertas G0.1-G0.9, parquet particionado, reporte y fallos esperados."""
from __future__ import annotations

import json

import polars as pl
import pytest
import yaml

from pitcheo import cli, fase00
from pitcheo.config import DEFAULT, Config
from pitcheo.io import leer_pitches
from pitcheo.sintetico import escribir_tres_formatos, generar

CFG = Config.load()
GATES = ["G0.1", "G0.2", "G0.3", "G0.4", "G0.5", "G0.6", "G0.7", "G0.8′", "G0.9"]
CFG_E2E = CFG


def _correr(tmp_path, parquet, cfg=CFG_E2E):
    return fase00.correr(cfg, parquet, tmp_path / "pitches.parquet", tmp_path / "reports",
                         tmp_path / "reports" / "logs", tmp_path / "figuras")


@pytest.fixture(scope="module")
def crudo(tmp_path_factory):
    d = tmp_path_factory.mktemp("crudo")
    escribir_tres_formatos(generar(20, 3), d / "stuff_model_df")
    return d / "stuff_model_df.parquet"


def _cfg_archivo(tmp_path, **mods):
    """Config temporal (YAML) con cambios puntuales (`seccion__clave=valor`); devuelve su ruta."""
    c = yaml.safe_load(DEFAULT.read_text(encoding="utf-8"))
    for k, v in mods.items():
        seccion, clave = k.split("__")
        c[seccion][clave] = v
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(c, allow_unicode=True), encoding="utf-8")
    return p


def test_f0_pasa_todas_las_compuertas_con_el_sintetico(tmp_path, crudo):
    res = _correr(tmp_path, crudo)
    assert res["ok"], {k: v for k, v in res["gates"].items() if not v["ok"]}
    assert sorted(res["gates"]) == GATES


def test_f0_escribe_parquet_particionado_con_columnas_nuevas_y_enums(tmp_path, crudo):
    _correr(tmp_path, crudo)
    carpetas = sorted(p.name for p in (tmp_path / "pitches.parquet").iterdir())
    assert carpetas == ["year=2024", "year=2025", "year=2026"]
    d = leer_pitches(tmp_path / "pitches.parquet").collect()
    bruto = pl.read_parquet(crudo)
    assert d.height == bruto.height and set(bruto.columns) <= set(d.columns)   # las crudas se conservan
    for c in ("familia", "es_sweeper", "pitcher_throws_r", "batter_side_r", "pitch_call_h", "evento_terminal",
              "excluir_modelo", "motivo_exclusion", "excluir_cadena", "motivo_cadena", "altitude_category_h",
              "es_swing", "es_whiff", "es_contacto", "es_foul", "es_bip", "media_entrada_A", "media_entrada_B"):
        assert c in d.columns
    assert isinstance(d.schema["familia"], pl.Enum) and isinstance(d.schema["AutoPitchType"], pl.Enum)
    assert d.schema["is_swing"] == pl.Boolean and d.schema["EffectiveVelo"] == pl.Float64


def test_f0_reporte_trae_bloque_tabla_de_eventos_y_sin_filas(tmp_path, crudo):
    _correr(tmp_path, crudo)
    md = (tmp_path / "reports" / "FASE_00.md").read_text(encoding="utf-8")
    for txt in ("Bloque para el orquestador — F00", "play_result × pitch_call_h × KorBB", "ADR-003",
                "excluir_modelo", "excluir_cadena", "ADR-010 (enmienda v2.5)", "ADR-014 — marco temporal único",
                "ADR-011 — banderas is_*", "ADR-012 / ADR-016", "OutsOnPlay × evento_terminal",
                "out faltante (sin turno incompleto)", "Out faltante (sin turno incompleto) por cubeta",
                "t_s por lanzamiento", "ponches por out registrado", "Prop. 16 por cubeta y global",
                "Prop. 17 — cota del sesgo", "Corroboraciones", "(a) Rodados", "(b) Columna `Outs`", "(c) Logit",
                "(d) Jugadas", "(e) |P| por juego", "sustituida por G0.2 (ADR-010)", "G0.6", "G0.7", "G0.8′", "G0.9",
                "W(Γ=2)", "perdida_ignorable"):
        assert txt in md, txt
    assert "π̂_K" not in md and "turno final perdido" not in md      # π̂_K retirado; "out faltante" sustituye al nombre viejo
    assert "pitch_00" not in md and "pitcher_0" not in md          # ni ids ni filas por lanzamiento
    js = json.loads((tmp_path / "reports" / "fase_00.json").read_text(encoding="utf-8"))
    assert js["sin_regla"] == [] and (tmp_path / "figuras" / "alcance.png").exists()
    assert (tmp_path / "figuras" / "P_por_juego_vs_poisson.png").exists()                       # corroboración (e)
    assert list((tmp_path / "reports" / "logs").glob("f00_*.log"))


def test_f0_valor_sin_regla_falla_y_no_escribe_parquet(tmp_path, crudo):
    bruto = pl.read_parquet(crudo)
    sucio = bruto.with_columns(
        pl.when(pl.int_range(pl.len()) < 3).then(pl.lit("Nuevo", dtype=pl.Utf8))
        .otherwise(pl.col("AutoPitchType").cast(pl.Utf8)).cast(pl.Categorical).alias("AutoPitchType"))
    p = tmp_path / "sucio.parquet"
    sucio.write_parquet(p)
    res = _correr(tmp_path, p)
    assert not res["ok"] and not res["gates"]["G0.5"]["ok"] and sorted(res["gates"]) == GATES
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
    cli.main(["--config", str(_cfg_archivo(tmp_path)), "f00", "--sintetico", "12", "--out", str(tmp_path / "out")])
    assert (tmp_path / "out" / "reports" / "FASE_00.md").exists()
    assert (tmp_path / "out" / "pitches.parquet").is_dir()


def test_cli_f00_sale_con_codigo_2_si_falla_una_compuerta(tmp_path, monkeypatch):
    forzadas = {g: {"ok": g != "G0.1", "detalle": "forzado"} for g in GATES}
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
    assert ex["polinomios"]["decision"] == "equivalentes" and "matriz" in ex["polinomios"]
    assert ex["dos_outs"]["dos_outs"]["n"] > 0 and ex["discrepancias_flags"]["es_contacto"]["tabla"]
    assert js["exclusiones"]["modelo"]["total"] >= js["exclusiones"]["cadena"]["total"]
    md = (tmp_path / "reports" / "FASE_00.md").read_text(encoding="utf-8")
    assert "equivalentes" in md and "| polinomio \\ 9P | x | y | z |" in md


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


# --------------------------------------------------------------------------
# v2.5 — G0.2 (ADR-010 enmendado), G0.3 y G0.7 (ADR-014)
# --------------------------------------------------------------------------
def test_v25_g02_y_g07_pasan_con_la_convencion_real(tmp_path, crudo):
    res = _correr(tmp_path, crudo)
    assert res["gates"]["G0.2"]["ok"] and "equivalentes" in res["gates"]["G0.2"]["detalle"]
    assert res["gates"]["G0.7"]["ok"] and "coincide" in res["gates"]["G0.7"]["detalle"]
    assert res["calibracion_elegida"]["signo"] == -1 and res["calibracion_elegida"]["y_plano_ft"] == pytest.approx(17 / 12)


def test_v25_g02_falla_si_los_polinomios_no_son_los_9p_y_g07_no_puede_verificar_zonetime(tmp_path):
    """v2.4 pasaba G0.2 declarándolos no canónicos; v2.5 exige confirmar la permutación con c2 y c1 con t_s."""
    p = tmp_path / "ruido.parquet"
    generar(12, 8, convencion_polinomio="ruido").write_parquet(p)
    res = _correr(tmp_path, p)
    assert not res["gates"]["G0.2"]["ok"] and "no_canonicos" in res["gates"]["G0.2"]["detalle"]
    assert not res["gates"]["G0.7"]["ok"]                        # sin t_s por lanzamiento no hay verificación de ZoneTime


def test_v25_g07_detecta_un_reloj_equivocado(tmp_path):
    """Polinomios alineados con los 9P pero con t_s = 0: ZoneTime ≠ t_p − 0 (el error de 3.5 ft de v2.4)."""
    p = tmp_path / "reloj.parquet"
    generar(12, 8, convencion_polinomio={"X": ("x", 1), "Y": ("y", 1), "Z": ("z", 1)}).write_parquet(p)
    res = _correr(tmp_path, p)
    assert res["gates"]["G0.2"]["ok"]                            # los polinomios sí son los 9P...
    assert not res["gates"]["G0.7"]["ok"] and "ZoneTime" in res["gates"]["G0.7"]["detalle"]   # ...pero el reloj no cuadra


def test_v25_g07_detecta_ruido_en_plateloc(tmp_path, crudo):
    n = pl.read_parquet(crudo).height
    p = _modificar(tmp_path, crudo, PlateLocSide=pl.col("PlateLocSide")
                   + pl.Series([0.4 * ((i * 7919) % 100 / 50 - 1) for i in range(n)]))
    assert not _correr(tmp_path, p)["gates"]["G0.7"]["ok"]


def test_v25_g07_elige_el_signo_de_los_datos_y_avisa_si_la_config_difiere(tmp_path):
    p = tmp_path / "signo_mas.parquet"
    generar(12, 8, signo_plateloc_x=1).write_parquet(p)
    res = _correr(tmp_path, p)
    assert res["gates"]["G0.7"]["ok"] and res["calibracion_elegida"]["signo"] == 1
    assert "DIFIERE" in res["gates"]["G0.7"]["detalle"] and "--aplicar" in res["gates"]["G0.7"]["detalle"]


def test_v25_g03_ya_no_depende_del_criterio_b(tmp_path, crudo):
    p = _modificar(tmp_path, crudo, Outs=pl.lit(0.0))             # sin estado previo Outs = 2: B = 0 %
    res = _correr(tmp_path, p)
    assert res["gates"]["G0.3"]["ok"] and "turno incompleto" in res["gates"]["G0.3"]["detalle"]


# --------------------------------------------------------------------------
# v2.6 — G0.8′ (Prop. 17) y G0.9 (Prop. 16, mecanismo)
# --------------------------------------------------------------------------
def test_v26_g08p_y_g09_con_el_sintetico_sin_perdida(tmp_path, crudo):
    """ℓ = 0: todo el out faltante es U. G0.9 → U, G0.8′ pasa y la pérdida es ignorable; el cambio por cubeta que
    habría tumbado el G0.8 de v2.5 ya no es compuerta."""
    res = _correr(tmp_path, crudo)
    g8, g9 = res["gates"]["G0.8′"], res["gates"]["G0.9"]
    assert g8["ok"] and "perdida_ignorable = true" in g8["detalle"] and "W(Γ=2)" in g8["detalle"]
    assert g9["ok"] and "**U**" in g9["detalle"]
    assert res["mecanismo_outs"] == "U" and res["perdida_ignorable"] is True
    js = json.loads((tmp_path / "reports" / "fase_00.json").read_text(encoding="utf-8"))
    mo = js["extras"]["mecanismo_outs"]
    assert mo["G09"]["mecanismo"] == "U" and mo["prop17"]["W"]["2"] == pytest.approx(0.0, abs=0.01)
    assert "G0.8" not in js["gates"] and "perdida_turnos" not in js["extras"]


def test_v26_g08p_falla_con_una_perdida_muy_distinta_por_cubeta_y_lo_dice(tmp_path):
    """ℓ = (0, 10, 50) %: el ancho del conjunto identificado supera 3.92·SE_ref → discrepancia, no se sigue a F1."""
    p = tmp_path / "cubeta.parquet"
    generar(40, 3, perdida_cubeta={"No Altitude": 0.0, "Medium Altitude": 0.1, "Extreme Altitude": 0.5}).write_parquet(p)
    res = _correr(tmp_path, p)
    g = res["gates"]["G0.8′"]
    assert not g["ok"] and "DISCREPANCIA" in g["detalle"] and "no se sigue a F1" in g["detalle"]
    assert not res["ok"] and res["perdida_ignorable"] is False
    assert (tmp_path / "reports" / "FASE_00.md").exists()               # el reporte se escribe antes de fallar


def test_v26_g09_se_reporta_siempre_y_no_falla_aunque_la_perdida_domine(tmp_path):
    p = tmp_path / "perdida.parquet"
    todas = {"No Altitude": 0.6, "Medium Altitude": 0.6, "Extreme Altitude": 0.6}
    generar(30, 5, perdida_cubeta=todas).write_parquet(p)
    res = _correr(tmp_path, p)
    assert res["gates"]["G0.9"]["ok"] and "**L**" in res["gates"]["G0.9"]["detalle"] and res["mecanismo_outs"] == "L"


def test_v26_g09_g08p_no_evaluadas_si_hay_valores_sin_regla(tmp_path, crudo):
    sucio = pl.read_parquet(crudo).with_columns(
        pl.when(pl.int_range(pl.len()) < 3).then(pl.lit("Nuevo", dtype=pl.Utf8))
        .otherwise(pl.col("AutoPitchType").cast(pl.Utf8)).cast(pl.Categorical).alias("AutoPitchType"))
    p = tmp_path / "sucio.parquet"
    sucio.write_parquet(p)
    res = _correr(tmp_path, p)
    assert not res["gates"]["G0.8′"]["ok"] and not res["gates"]["G0.9"]["ok"] and res["mecanismo_outs"] is None
    assert "no evaluada" in res["gates"]["G0.9"]["detalle"]


def test_v26_el_reporte_no_trae_filas_por_lanzamiento_ni_tablas_por_lanzador(tmp_path, crudo):
    _correr(tmp_path, crudo)
    md = (tmp_path / "reports" / "FASE_00.md").read_text(encoding="utf-8")
    js = (tmp_path / "reports" / "fase_00.json").read_text(encoding="utf-8")
    log = next((tmp_path / "reports" / "logs").glob("f00_*.log")).read_text(encoding="utf-8")
    for txt in (md, js, log):
        assert "pitch_0" not in txt and "pitcher_0" not in txt and "batter_0" not in txt and "catcher_0" not in txt

# --------------------------------------------------------------------------
# --aplicar: dejar en config lo que midió F0 (ADR-014: y_p y signo; ADR-016: mecanismo_outs y perdida_ignorable)
# --------------------------------------------------------------------------
def test_aplicar_config_reescribe_solo_las_cuatro_lineas(tmp_path):
    cfg = tmp_path / "default.yaml"
    cfg.write_text(DEFAULT.read_text(encoding="utf-8"), encoding="utf-8")
    antes = cfg.read_text(encoding="utf-8")
    c0 = yaml.safe_load(antes)
    assert c0["qa"]["mecanismo_outs"] in ("U", "L", "mezcla") and isinstance(c0["qa"]["perdida_ignorable"], bool)
    # Se aplica un mecanismo distinto del vigente (F0 real dejó U) y la bandera contraria, para que cambien las 4 líneas.
    nuevo_mec = "L" if c0["qa"]["mecanismo_outs"] != "L" else "mezcla"
    nueva_ign = not c0["qa"]["perdida_ignorable"]
    r = fase00.aplicar_config(cfg, {"y_plano_ft": 0.0, "signo": 1}, nuevo_mec, nueva_ign)
    despues = cfg.read_text(encoding="utf-8")
    assert r["cambio"] and set(r) == {"cambio", "y_plato_ft", "signo_plateloc_x", "mecanismo_outs", "perdida_ignorable"}
    dif = [(a, b) for a, b in zip(antes.splitlines(), despues.splitlines(), strict=True) if a != b]
    assert len(dif) == 4                                          # solo cambian esas cuatro líneas (comentarios intactos)
    c = yaml.safe_load(despues)
    assert (c["fisica"]["signo_plateloc_x"], c["qa"]["mecanismo_outs"], c["qa"]["perdida_ignorable"]) == (1, nuevo_mec, nueva_ign)
    assert fase00.aplicar_config(cfg, {"y_plano_ft": 0.0, "signo": 1}, nuevo_mec, nueva_ign) == {"cambio": False}   # idempotente


def test_aplicar_config_acepta_cada_mecanismo_y_ignora_valores_invalidos(tmp_path):
    cfg = tmp_path / "default.yaml"
    cfg.write_text(DEFAULT.read_text(encoding="utf-8"), encoding="utf-8")
    for mec in ("L", "mezcla", "U"):
        fase00.aplicar_config(cfg, None, mec, False)
        assert yaml.safe_load(cfg.read_text(encoding="utf-8"))["qa"]["mecanismo_outs"] == mec
    assert fase00.aplicar_config(cfg, None, "otro", None) == {"cambio": False}
    assert yaml.safe_load(cfg.read_text(encoding="utf-8"))["qa"]["mecanismo_outs"] == "U"


def test_cli_aplicar_escribe_lo_medido_en_la_config_usada(tmp_path):
    parquet = tmp_path / "raw.parquet"
    generar(12, 8).write_parquet(parquet)                         # verdad sembrada: signo -1, y_p = 17/12, mecanismo U
    cfg = _cfg_archivo(tmp_path, rutas__raw_parquet=str(parquet), rutas__pitches=str(tmp_path / "p.parquet"),
                       rutas__reportes=str(tmp_path / "rep"), rutas__logs=str(tmp_path / "rep" / "logs"),
                       rutas__figuras=str(tmp_path / "fig"), fisica__signo_plateloc_x=1,   # config equivocada a propósito
                       qa__mecanismo_outs="L", qa__perdida_ignorable=False)
    cli.main(["--config", str(cfg), "f00", "--aplicar"])
    c = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert c["fisica"]["signo_plateloc_x"] == -1 and c["fisica"]["y_plato_ft"] == pytest.approx(17 / 12)
    assert c["qa"]["mecanismo_outs"] == "U" and c["qa"]["perdida_ignorable"] is True


def test_cli_sin_aplicar_no_toca_la_config(tmp_path):
    parquet = tmp_path / "raw.parquet"
    generar(12, 8).write_parquet(parquet)
    cfg = _cfg_archivo(tmp_path, rutas__raw_parquet=str(parquet), rutas__pitches=str(tmp_path / "p.parquet"),
                       rutas__reportes=str(tmp_path / "rep"), rutas__logs=str(tmp_path / "rep" / "logs"),
                       rutas__figuras=str(tmp_path / "fig"), qa__mecanismo_outs="L")
    antes = cfg.read_text(encoding="utf-8")
    cli.main(["--config", str(cfg), "f00"])
    assert cfg.read_text(encoding="utf-8") == antes


def test_cli_aplicar_con_sintetico_no_toca_la_config(tmp_path):
    antes = DEFAULT.read_text(encoding="utf-8")
    cli.main(["--config", str(_cfg_archivo(tmp_path)), "f00", "--sintetico", "12", "--aplicar",
              "--out", str(tmp_path / "out")])
    assert DEFAULT.read_text(encoding="utf-8") == antes
