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


def test_caso_16_play_result(grande):
    assert _vals(grande, "play_result") == set(CAT["columnas"]["play_result"]["valores"])
    assert len(_vals(grande, "play_result")) == 16


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


# --------------------------------------------------------------------------
# Casos de la corrida real de F0 (ROADMAP §1.2, ADR-010 a 013)
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def grande() -> pl.DataFrame:
    return generar(n_juegos=30, semilla=2026)      # muestra mayor para lo raro (triples, 0-1 outs)


def test_caso_medias_entradas_de_2_outs_y_de_mas_de_3(grande):
    from pitcheo.limpieza import tabla_medias_entradas
    t = tabla_medias_entradas(grande)
    dos = (t["outs"] == 2).mean()
    assert 0.04 < dos < 0.25                                   # real: 12.9 %
    assert (t["outs"] >= 4).sum() >= 1 and (t["outs"] <= 1).sum() >= 1


def test_caso_media_entrada_de_2_outs_termina_en_turno_incompleto(df):
    """El mecanismo sembrado: robo/pickoff con el bateador a medias (lanzamientos sin evento terminal)."""
    sin_ev = df.filter(pl.col("KorBB") == "Undefined").height
    assert sin_ev > 0
    # una media entrada de 2 outs tiene su último bateador sin ponche/base/bola en juego
    t = generar(6, 99, sucio=False)
    assert t.filter(pl.col("Outs") == 2).height > 0


def test_caso_pitcher_id_nulo_y_foul_con_ponche_y_inplay_sin_resultado(df):
    assert df["pitcher_anon_id"].null_count() > 0
    foul = df.filter(pl.col("PitchCall").cast(pl.Utf8).str.starts_with("FoulBall") & (pl.col("KorBB") == "Strikeout"))
    assert foul.height >= 1 and (foul["play_result"].cast(pl.Utf8) == "Strikeout").all()
    inplay_neutral = df.filter((pl.col("PitchCall") == "InPlay") & (pl.col("play_result") == "NeutralPlay"))
    assert inplay_neutral.height >= 1


def test_caso_banderas_is_no_son_particion_de_pitchcall(df):
    foul = df.filter(pl.col("PitchCall").cast(pl.Utf8).str.starts_with("FoulBall"))
    assert (foul["is_contact"] == 0).sum() > 0                  # foul sin is_contact
    assert (foul["is_contact"] == 0).mean() < 0.05
    assert not ((df["is_whiff"] == 1) & (df["PitchCall"].cast(pl.Utf8) != "StrikeSwinging")).any()   # whiff => SS


def test_convencion_de_polinomio_real_por_defecto():
    """ADR-010 enmendado: los polinomios son los 9P con ejes permutados X→y, Y→z, Z→x y origen en la liberación."""
    d, v = generar(3, 1, sucio=False, con_verdad=True)
    assert d["PitchTrajectoryXc2"].to_list() == pytest.approx((d["ay0"] / 2).to_list())
    assert d["PitchTrajectoryYc2"].to_list() == pytest.approx((d["az0"] / 2).to_list())
    assert d["PitchTrajectoryZc2"].to_list() == pytest.approx((d["ax0"] / 2).to_list())
    ts = v["t_s"]
    for p, (v0, a0) in {"X": ("vy0", "ay0"), "Y": ("vz0", "az0"), "Z": ("vx0", "ax0")}.items():     # c1 = v0 + a·t_s
        assert d[f"PitchTrajectory{p}c1"].to_list() == pytest.approx((d[v0] + d[a0] * ts).to_list())
    for p, (r0, v0, a0) in {"X": ("y0", "vy0", "ay0"), "Y": ("z0", "vz0", "az0"), "Z": ("x0", "vx0", "ax0")}.items():
        assert d[f"PitchTrajectory{p}c0"].to_list() == pytest.approx(
            (d[r0] + d[v0] * ts + 0.5 * d[a0] * ts**2).to_list())
    assert (ts < 0).all() and 0.01 < float(-ts.mean()) < 0.06           # real: ≈ -0.026 s (liberación ~54 ft)


def test_convencion_de_polinomio_configurable():
    conv = {"X": ("z", -1), "Y": ("y", -1), "Z": ("x", 1)}
    d = generar(3, 1, sucio=False, convencion_polinomio=conv)
    assert d["PitchTrajectoryXc2"].to_list() == pytest.approx((-d["az0"] / 2).to_list())
    assert d["PitchTrajectoryYc1"].to_list() == pytest.approx((-d["vy0"]).to_list())
    assert d["PitchTrajectoryZc0"].to_list() == pytest.approx(d["x0"].to_list())
    ruido = generar(3, 1, sucio=False, convencion_polinomio="ruido")
    assert ruido["PitchTrajectoryXc2"].to_list() != pytest.approx((ruido["ay0"] / 2).to_list())


def test_caso_9p_arrancan_en_50_pies_y_zonetime_en_la_liberacion():
    d, v = generar(3, 1, sucio=False, con_verdad=True)
    assert d["y0"].to_list() == pytest.approx([50.0] * d.height)
    assert d["ZoneTime"].min() > 0.3 and (v["t_s"] < 0).all()
    # El tiempo de vuelo desde la liberación es mayor que el tiempo desde y = 50 ft (el reloj de los 9P).
    from pitcheo.fisica import nueve_p, tiempo_al_plato
    assert (d["ZoneTime"].to_numpy() - tiempo_al_plato(*nueve_p(d))).min() > 0.01


def test_caso_plateloc_side_con_signo_sembrado_y_plano_configurable():
    d, v = generar(3, 2, sucio=False, con_verdad=True)
    assert v["signo_x"] == -1 and v["y_plano_ft"] == pytest.approx(17 / 12)
    d1, _v1 = generar(3, 2, sucio=False, con_verdad=True, signo_plateloc_x=1)
    assert (d1["PlateLocSide"] + d["PlateLocSide"]).abs().max() < 1e-9          # mismo vuelo, signo opuesto
    d0, v0 = generar(3, 2, sucio=False, con_verdad=True, y_plano_ft=0.0)       # otro plano: otro vuelo y otras filas
    assert d0["ZoneTime"].mean() > d["ZoneTime"].mean() and v0["y_plano_ft"] == 0.0


def test_caso_turnos_finales_perdidos_sobre_todo_ponches():
    """ADR-015: la mayoría de las medias entradas de 2 outs perdió su último turno COMPLETO, y más a menudo si era K."""
    from pitcheo.io import leer_diccionario
    from pitcheo.limpieza import limpiar
    from pitcheo.qa import diagnostico_dos_outs
    d0, v = generar(20, 5, con_verdad=True)
    d, _ = limpiar(d0, leer_diccionario(CFG.ruta("diccionario")), CAT, CFG["f00"])
    cla = diagnostico_dos_outs(d)["clasificacion_no_finales"]
    assert cla["pct_turno_final_perdido"] > 70 and cla["pct_turno_incompleto"] > 3
    assert v["perdidos"]["K"] > 0 and v["perdidos"]["OUT_BIP"] > 0
    assert v["pi_k"] > 0.5                                       # sembrado MNAR: los ponches se pierden más


def test_caso_turnos_finales_perdidos_estratificados_y_por_cubeta():
    _d0, v = generar(12, 4, con_verdad=True, p_perdida_tipo={"K": 0.0, "OUT_BIP": 0.0})
    assert v["perdidos"] == {"K": 0, "OUT_BIP": 0}              # sin pérdida sembrada no se pierde nada
    _d1, v1 = generar(12, 4, con_verdad=True, p_perdida_cubeta={"No Altitude": 0.0, "Medium Altitude": 0.0,
                                                               "Extreme Altitude": 0.0})
    assert v1["perdidos"] == {"K": 0, "OUT_BIP": 0}


def test_cada_defecto_sembrado_cabe_en_las_compuertas(df):
    """El sintético sucio no debe rozar los topes: excluir_modelo <= 3 % y excluir_cadena <= 0.5 %."""
    from pitcheo.io import leer_diccionario
    from pitcheo.limpieza import limpiar
    _d, rep = limpiar(df, leer_diccionario(CFG.ruta("diccionario")), CAT, CFG["f00"])
    assert rep["exclusiones"]["modelo"]["pct_total"] < 3.0
    assert rep["exclusiones"]["cadena"]["pct_total"] < 0.5
