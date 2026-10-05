"""ADR-002 a ADR-007 exactamente como están en ROADMAP §1.1, regla por regla."""
from __future__ import annotations

import polars as pl
import pytest

from pitcheo.config import Config
from pitcheo.io import leer_diccionario
from pitcheo.limpieza import aplicar_adr, cargar_categorias, limpiar, normalizar_tipos, verificar_categorias
from pitcheo.sintetico import generar

CFG = Config.load()
CAT = cargar_categorias(CFG.ruta("categorias"))
F00 = CFG["f00"]
DICC = leer_diccionario(CFG.ruta("diccionario"))

_DEFAULTS = {"AutoPitchType": "Four-Seam", "PitchCall": "BallCalled", "PitcherThrows": "Right",
             "pitcher_anon_id": "p1", "RelSide": -1.5, "BatterSide": "Right", "batter_anon_id": "b1",
             "altitude_category": "No Altitude", "game_anon_id": "g1", "KorBB": "Undefined",
             "play_result": "NeutralPlay", "Outs": 0.0}
_FLOATS = {"RelSide", "Outs"}


def mk(**cols) -> pl.DataFrame:
    """Marco mínimo con las columnas que usa `aplicar_adr`; los escalares se difunden."""
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    out = {}
    for c, d in _DEFAULTS.items():
        v = cols.get(c, d)
        v = v if isinstance(v, list) else [v] * n
        out[c] = pl.Series(c, v, dtype=pl.Float64 if c in _FLOATS else pl.Utf8)
    return pl.DataFrame(out)


def adr(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    return aplicar_adr(df, CAT, F00)


# --------------------------------------------------------------------------
# ADR-002 — familia
# --------------------------------------------------------------------------
def test_adr002_familia_de_cada_valor_real():
    esperado = {"Four-Seam": "FF", "Sinker": "SI", "TwoSeamFastBall": "SI", "OneSeamFastBall": "SI",
                "Cutter": "FC", "Slider": "SL", "Sweeper": "SL", "Curveball": "CU", "Changeup": "CH",
                "Splitter": "CH", "Knuckleball": "EXC", "Other": "EXC", "Undefined": "EXC"}
    d, _ = adr(mk(AutoPitchType=list(esperado)))
    assert dict(zip(esperado, d["familia"].cast(pl.Utf8).to_list(), strict=True)) == esperado


def test_adr002_bandera_sweeper_y_cruda_conservada():
    d, rep = adr(mk(AutoPitchType=["Sweeper", "Slider", "Four-Seam"]))
    assert d["es_sweeper"].to_list() == [True, False, False]
    assert d["AutoPitchType"].to_list() == ["Sweeper", "Slider", "Four-Seam"]
    assert rep["ADR-002"]["sweepers"] == 1


def test_adr002_knuckleball_se_excluye():
    d, _ = adr(mk(AutoPitchType=["Knuckleball", "Four-Seam"]))
    assert d["excluir_modelo"].to_list() == [True, False]
    assert d["motivo_exclusion"].to_list() == ["ADR-002:EXC", None]


# --------------------------------------------------------------------------
# ADR-003 — mano del lanzador
# --------------------------------------------------------------------------
def _lanzadores(n_def=20):
    """Lanzador pA: todo derecho (moda). Lanzador pB: 50/50. Negativo = derecho (convención sembrada)."""
    manos = ["Right"] * n_def + ["Right"] * 10 + ["Left"] * 10
    ids = ["pA"] * n_def + ["pB"] * 20
    rel = [-1.5 if m == "Right" else 1.5 for m in manos]
    return manos, ids, rel


def test_adr003_lanzador_moda_si_participacion_alta():
    manos, ids, rel = _lanzadores()
    d, rep = adr(mk(PitcherThrows=manos + ["Undefined"], pitcher_anon_id=ids + ["pA"], RelSide=rel + [1.5]))
    # pA es 100 % derecho: aunque el signo de RelSide diga zurdo, manda la moda del lanzador.
    assert d["pitcher_throws_r"][-1] is True
    assert rep["ADR-003"]["lanzador"]["imputadas_por_moda"] == 1


def test_adr003_lanzador_signo_de_relside_aprendido_derecha_negativo():
    manos, ids, rel = _lanzadores()
    d, rep = adr(mk(PitcherThrows=manos + ["Undefined"], pitcher_anon_id=ids + ["pB"], RelSide=rel + [-1.5]))
    assert d["pitcher_throws_r"][-1] is True            # pB no tiene moda: decide el signo
    r = rep["ADR-003"]["lanzador"]
    assert r["imputadas_por_relside"] == 1 and r["relside"]["derecha_es_signo_positivo"] is False


def test_adr003_el_signo_se_aprende_no_se_supone():
    """Con la convención invertida (derecha = RelSide > 0) la imputación se invierte sola."""
    manos, ids, rel = _lanzadores()
    rel = [-x for x in rel]
    d, rep = adr(mk(PitcherThrows=manos + ["Undefined"], pitcher_anon_id=ids + ["pB"], RelSide=rel + [1.5]))
    assert d["pitcher_throws_r"][-1] is True
    assert rep["ADR-003"]["lanzador"]["relside"]["derecha_es_signo_positivo"] is True


def test_adr003_lanzador_sin_id_usa_relside():
    manos, ids, rel = _lanzadores()
    d, _ = adr(mk(PitcherThrows=manos + [None], pitcher_anon_id=ids + [None], RelSide=rel + [1.5]))
    assert d["pitcher_throws_r"][-1] is False           # nulo en la mano = Undefined; sin id: RelSide


def test_adr003_lanzador_se_descarta_sin_salida():
    manos, ids, rel = _lanzadores()
    d, rep = adr(mk(PitcherThrows=manos + ["Undefined", "Undefined"], pitcher_anon_id=ids + [None, None],
                    RelSide=rel + [None, 0.0]))
    assert d["pitcher_throws_r"][-2:].to_list() == [None, None]
    assert d["motivo_exclusion"][-1] == "ADR-003:lanzador"
    assert rep["ADR-003"]["lanzador"]["descartadas"] == 2


def test_adr003_relside_inactivo_si_la_concordancia_es_baja():
    """Si el signo no concuerda con la mano >= 99 % no se usa: se descarta."""
    manos = ["Right"] * 50 + ["Left"] * 50
    rel = [-1.5] * 50 + [1.5] * 50
    rel[0], rel[1], rel[2] = 1.5, 1.5, 1.5              # 3 % de discordancia
    d, rep = adr(mk(PitcherThrows=manos + ["Undefined"], pitcher_anon_id=["x"] * 50 + ["y"] * 50 + [None],
                    RelSide=rel + [-1.5]))
    assert rep["ADR-003"]["lanzador"]["relside"]["regla_activa"] is False
    assert d["pitcher_throws_r"][-1] is None


# --------------------------------------------------------------------------
# ADR-003 — lado del bateador
# --------------------------------------------------------------------------
def test_adr003_bateador_switch_toma_la_mano_opuesta():
    d, rep = adr(mk(PitcherThrows=["Right", "Left"], BatterSide=["Switch", "Switch"],
                    pitcher_anon_id=["p1", "p2"], RelSide=[-1.5, 1.5]))
    assert d["batter_side_r"].to_list() == [False, True]
    assert rep["ADR-003"]["bateador"]["switch_resueltos_opuesta"] == 2


def test_adr003_bateador_undefined_usa_su_moda():
    d, _ = adr(mk(BatterSide=["Right"] * 20 + ["Undefined"], batter_anon_id=["b"] * 21))
    assert d["batter_side_r"][-1] is True


def test_adr003_bateador_con_ambos_lados_toma_opuesta_al_lanzador():
    lados = ["Right"] * 10 + ["Left"] * 10 + ["Undefined"]
    d, _ = adr(mk(BatterSide=lados, batter_anon_id=["b"] * 21,
                  PitcherThrows=["Right"] * 21, pitcher_anon_id=["p"] * 21))
    assert d["batter_side_r"][-1] is False              # pitcher derecho -> bateador zurdo


def test_adr003_bateador_se_descarta_sin_filas_resueltas_ni_id():
    d, rep = adr(mk(BatterSide=["Undefined", "Undefined"], batter_anon_id=["solo", None]))
    assert d["batter_side_r"].to_list() == [None, None]
    assert d["motivo_exclusion"].to_list() == ["ADR-003:bateador"] * 2
    assert rep["ADR-003"]["bateador"]["descartadas"] == 2


def test_adr003_switch_con_lanzador_descartado_se_descarta():
    manos, ids, rel = _lanzadores()
    d, _ = adr(mk(PitcherThrows=manos + ["Undefined"], pitcher_anon_id=ids + [None], RelSide=rel + [None],
                  BatterSide=["Right"] * 40 + ["Switch"], batter_anon_id=["b"] * 40 + ["sw"]))
    assert d["batter_side_r"][-1] is None


# --------------------------------------------------------------------------
# ADR-004 — PitchCall
# --------------------------------------------------------------------------
def test_adr004_los_tres_fouls_son_foul_y_la_cruda_se_conserva():
    calls = ["FoulBall", "FoulBallFieldable", "FoulBallNotFieldable", "InPlay"]
    d, rep = adr(mk(PitchCall=calls))
    assert d["pitch_call_h"].cast(pl.Utf8).to_list() == ["Foul", "Foul", "Foul", "InPlay"]
    assert d["PitchCall"].to_list() == calls
    assert rep["ADR-004"]["foul_unificados"] == 3


def test_adr004_undefined_se_excluye():
    d, rep = adr(mk(PitchCall=["Undefined", "StrikeCalled"]))
    assert d["excluir_modelo"].to_list() == [True, False]
    assert d["motivo_exclusion"][0] == "ADR-004:Undefined" and rep["ADR-004"]["undefined_excluidos"] == 1


# --------------------------------------------------------------------------
# ADR-005 — cubeta de altitud
# --------------------------------------------------------------------------
def test_adr005_imputa_por_juego_solo_si_es_constante():
    d, rep = adr(mk(
        game_anon_id=["g1", "g1", "g1", "g2", "g2", "g3", "g3", "g3"],
        altitude_category=["Extreme Altitude", None, "Extreme Altitude", None, None,
                           "No Altitude", "Medium Altitude", None]))
    h = d["altitude_category_h"].cast(pl.Utf8).to_list()
    assert h[:3] == ["Extreme Altitude"] * 3              # constante: se imputa
    assert h[3:5] == [None, None]                         # juego entero nulo: queda sin cubeta
    assert h[5:] == ["No Altitude", "Medium Altitude", None]   # dos cubetas: no se inventa
    assert d["altitude_category"].null_count() == 4       # la cruda se conserva
    a = rep["ADR-005"]
    assert a["imputadas_por_juego"] == 1 and a["juegos_sin_cubeta"] == 1
    assert a["juegos_con_mas_de_una_cubeta"] == 1 and a["filas_sin_cubeta"] == 3


# --------------------------------------------------------------------------
# ADR-006 — Outs
# --------------------------------------------------------------------------
def test_adr006_outs_3_se_excluye_y_se_cuenta():
    d, rep = adr(mk(Outs=[0.0, 2.0, 3.0]))
    assert d["excluir_modelo"].to_list() == [False, False, True]
    assert d["motivo_exclusion"][2] == "ADR-006:Outs" and rep["ADR-006"]["outs_invalidos"] == 1


def test_exclusiones_se_combinan_sin_doble_conteo():
    d, rep = adr(mk(AutoPitchType=["Knuckleball", "Four-Seam", "Four-Seam"], Outs=[3.0, 0.0, 0.0],
                    PitchCall=["BallCalled", "Undefined", "BallCalled"]))
    assert d["motivo_exclusion"].to_list() == ["ADR-002:EXC;ADR-006:Outs", "ADR-004:Undefined", None]
    assert rep["exclusiones"]["total"] == 2


# --------------------------------------------------------------------------
# ADR-007 — evento terminal
# --------------------------------------------------------------------------
@pytest.mark.parametrize("korbb,call,pr,esperado", [
    ("Strikeout", "StrikeSwinging", "Strikeout", "K"),
    ("Strikeout", "StrikeCalled", "Strikeout", "K"),
    ("Walk", "BallCalled", "Walk", "BB"),
    ("Undefined", "HitByPitch", "HitByPitch", "HBP"),
    ("Strikeout", "HitByPitch", "Strikeout", "K"),         # prioridad 1 sobre 2
    ("Walk", "InPlay", "Single", "BB"),                    # prioridad 1 sobre 3
    ("Undefined", "InPlay", "Single", "1B"),
    ("Undefined", "InPlay", "Double", "2B"),
    ("Undefined", "InPlay", "Triple", "3B"),
    ("Undefined", "InPlay", "HomeRun", "HR"),
    ("Undefined", "InPlay", "Out", "OUT_BIP"),
    ("Undefined", "InPlay", "FieldersChoice", "OUT_BIP"),
    ("Undefined", "InPlay", "Error", "ROE"),
    ("Undefined", "InPlay", "Sacrifice", "SAC"),
    ("Undefined", "BallCalled", "BallCalled", None),       # cualquier otro valor: no terminal
    ("Undefined", "FoulBall", "NeutralPlay", None),
    ("Undefined", "InPlay", "NeutralPlay", None),
    ("Undefined", "BallCalled", "Single", None),           # resultado de bola en juego sin InPlay
])
def test_adr007_evento_terminal(korbb, call, pr, esperado):
    d, _ = adr(mk(KorBB=korbb, PitchCall=call, play_result=pr))
    ev = d["evento_terminal"][0]
    assert (None if ev is None else str(ev)) == esperado


# --------------------------------------------------------------------------
# Valores sin regla: no se asignan en silencio, la fase falla
# --------------------------------------------------------------------------
def _con_valor(df: pl.DataFrame, col: str, valor) -> pl.DataFrame:
    primero = pl.int_range(pl.len()) == 0
    nuevo = (pl.when(primero).then(pl.lit(valor, dtype=pl.Utf8)).otherwise(pl.col(col).cast(pl.Utf8)))
    return df.with_columns(nuevo.cast(df.schema[col]).alias(col))


@pytest.fixture(scope="module")
def base() -> pl.DataFrame:
    return generar(n_juegos=3, semilla=11, sucio=False)


def test_limpiar_sobre_datos_sanos_no_deja_sin_regla(base):
    d, rep = limpiar(base, DICC, CAT, F00)
    assert rep["sin_regla"] == [] and d is not None
    for c in ("familia", "es_sweeper", "pitcher_throws_r", "batter_side_r", "pitch_call_h",
              "evento_terminal", "altitude_category_h", "excluir_modelo", "motivo_exclusion"):
        assert c in d.columns
    assert "AutoPitchType" in d.columns and "PitchCall" in d.columns   # las crudas se conservan


@pytest.mark.parametrize("col,valor", [
    ("AutoPitchType", "Foo"), ("PitchCall", "Rarisimo"), ("play_result", "Weird"),
    ("KorBB", "Strikeout2"), ("PitcherThrows", "Ambidextrous"), ("altitude_category", "Moon")])
def test_valor_nuevo_va_a_la_tabla_sin_regla_y_no_hay_parquet(base, col, valor):
    d, rep = limpiar(_con_valor(base, col, valor), DICC, CAT, F00)
    assert d is None
    assert {"columna": col, "valor": valor, "n": 1} in rep["sin_regla"]


def test_nulo_en_columna_que_no_lo_permite_es_sin_regla(base):
    d, rep = limpiar(base.with_columns(
        pl.when(pl.int_range(pl.len()) < 2).then(None).otherwise(pl.col("KorBB")).alias("KorBB")), DICC, CAT, F00)
    assert d is None and {"columna": "KorBB", "valor": "<nulo>", "n": 2} in rep["sin_regla"]


def test_verificar_categorias_no_marca_los_nulos_permitidos(base):
    sucio = base.with_columns(pl.lit(None, dtype=pl.Utf8).alias("PitcherThrows"))
    assert verificar_categorias(sucio, CAT) == []


# --------------------------------------------------------------------------
# Tipos
# --------------------------------------------------------------------------
def test_tipos_effectivevelo_texto_a_float_con_tokens_nulos():
    df = pl.DataFrame({"EffectiveVelo": ["93.5", "NA", "", " 90.0 ", None]})
    d, conv, problemas = normalizar_tipos(df, DICC)
    assert problemas == []
    assert d["EffectiveVelo"].to_list() == [93.5, None, None, 90.0, None]
    assert conv["EffectiveVelo"]["tokens_nulos"] == 2


def test_tipos_token_no_numerico_es_sin_regla_y_no_se_fuerza():
    df = pl.DataFrame({"EffectiveVelo": ["93.5", "abc", "abc", "-"]})
    d, _, problemas = normalizar_tipos(df, DICC)
    assert d["EffectiveVelo"].dtype == pl.Utf8                  # la columna queda intacta
    assert {"columna": "EffectiveVelo", "valor": "no numérico: abc", "n": 2} in problemas
    assert any(p["valor"] == "no numérico: -" for p in problemas)


def test_tipos_flags_float_a_bool_y_valor_raro_es_sin_regla():
    ok, _, p_ok = normalizar_tipos(pl.DataFrame({"is_swing": [0.0, 1.0, None]}), DICC)
    assert ok["is_swing"].to_list() == [False, True, None] and p_ok == []
    _, _, p_mal = normalizar_tipos(pl.DataFrame({"is_swing": [0.0, 2.0]}), DICC)
    assert p_mal == [{"columna": "is_swing", "valor": "no es 0/1: 2.0", "n": 1}]


def test_tipos_nan_pasa_a_nulo_y_enteros_float_a_int64():
    nan = float("nan")
    d, conv, _ = normalizar_tipos(pl.DataFrame({"SpinRate": [2000.0, nan, 2100.0],
                                                "Outs": [0.0, 1.0, 2.0],
                                                "year": pl.Series([2024, 2025, 2026], dtype=pl.Int32)}), DICC)
    assert d["SpinRate"].null_count() == 1 and conv["SpinRate"]["nan_a_nulo"] == 1
    assert d["Outs"].dtype == pl.Int64 and d["year"].dtype == pl.Int64


def test_tipos_entero_con_decimales_es_sin_regla():
    _, _, p = normalizar_tipos(pl.DataFrame({"Outs": [0.0, 1.5]}), DICC)
    assert p == [{"columna": "Outs", "valor": "no entero: 1.5", "n": 1}]
