"""Trayectoria canónica de los 9P (ADR-010) y su marco temporal (ADR-014)."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from pitcheo.fisica import (
    Y_FRENTE_PLATO_FT,
    calibrar_plano_y_signo,
    nueve_p,
    tiempo_al_plato,
    trayectoria_9p,
    velocidad_9p,
)
from pitcheo.sintetico import generar

R0, V0, A = [0.5, 50.0, 6.0], [-2.0, -130.0, 1.0], [3.0, 25.0, -32.174]


def test_en_t_cero_es_la_posicion_inicial():
    assert trayectoria_9p(0.0, R0, V0, A) == pytest.approx(R0)


def test_es_el_modelo_de_aceleracion_constante():
    t = 0.3
    esperado = [R0[i] + V0[i] * t + 0.5 * A[i] * t**2 for i in range(3)]
    assert trayectoria_9p(t, R0, V0, A) == pytest.approx(esperado)
    h = 1e-6   # la velocidad es la derivada: diferencias finitas
    dv = (trayectoria_9p(t + h, R0, V0, A) - trayectoria_9p(t - h, R0, V0, A)) / (2 * h)
    assert dv == pytest.approx(velocidad_9p(t, V0, A), rel=1e-6)


def test_vectorizada_un_tiempo_por_lanzamiento():
    r0, v0, a = (np.tile(x, (4, 1)) for x in (R0, V0, A))
    r = trayectoria_9p(np.array([0.0, 0.1, 0.2, 0.3]), r0, v0, a)
    assert r.shape == (4, 3) and r[2] == pytest.approx(trayectoria_9p(0.2, R0, V0, A))


def test_tiempo_al_plato_es_la_raiz_positiva_pequena():
    t = tiempo_al_plato(R0, V0, A)
    assert t.shape == (1,) and 0.3 < t[0] < 0.5
    assert trayectoria_9p(t[0], R0, V0, A)[1] == pytest.approx(Y_FRENTE_PLATO_FT)
    assert trayectoria_9p(tiempo_al_plato(R0, V0, A, 0.0)[0], R0, V0, A)[1] == pytest.approx(0.0, abs=1e-9)


def test_tiempo_al_plato_sin_solucion_es_nan():
    assert np.isnan(tiempo_al_plato([0, 50, 6], [0, 10, 0], [0, 1, 0])).all()     # se aleja del plato


# --------------------------------------------------------------------------
# ADR-014 — marco temporal único
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sint():
    return generar(5, 3, sucio=False, con_verdad=True)


def test_zonetime_es_tp_menos_ts_y_no_tp(sint):
    d, v = sint
    r0, v0, a = nueve_p(d)
    tp = tiempo_al_plato(r0, v0, a)
    assert tp - v["t_s"] == pytest.approx(d["ZoneTime"].to_numpy(), abs=1e-9)    # ZoneTime ≈ t_p − t_s
    assert np.median(np.abs(d["ZoneTime"].to_numpy() - tp)) == pytest.approx(np.median(np.abs(v["t_s"])), rel=0.2)
    assert (v["t_s"] < 0).all()                   # el polinomio y ZoneTime arrancan ANTES de y = 50 ft


def test_los_9p_arrancan_en_50_pies(sint):
    d, _ = sint
    assert d["y0"].to_list() == pytest.approx([50.0] * d.height)


def test_el_error_de_v24_se_reproduce_al_evaluar_los_9p_en_zonetime(sint):
    """v2.4 evaluó los 9P en t = ZoneTime y vio ~4 ft de error en y: era el reloj, no los 9P."""
    d, _ = sint
    r0, v0, a = nueve_p(d)
    y = trayectoria_9p(d["ZoneTime"].to_numpy(), r0, v0, a)[:, 1]
    assert 2.0 < float(np.median(np.abs(y - Y_FRENTE_PLATO_FT))) < 6.0          # real: 4.27 ft


def test_con_el_tiempo_al_plato_correcto_el_error_es_cero(sint):
    d, _ = sint
    r0, v0, a = nueve_p(d)
    r = trayectoria_9p(tiempo_al_plato(r0, v0, a), r0, v0, a)
    assert -r[:, 0] == pytest.approx(d["PlateLocSide"].to_numpy(), abs=1e-9)     # signo sembrado: -1
    assert r[:, 2] == pytest.approx(d["PlateLocHeight"].to_numpy(), abs=1e-9)


@pytest.mark.parametrize("signo,plano", [(-1, Y_FRENTE_PLATO_FT), (1, Y_FRENTE_PLATO_FT), (-1, 0.0), (1, 0.0)])
def test_calibrar_recupera_el_plano_y_el_signo_sembrados(signo, plano):
    d, v = generar(5, 4, sucio=False, con_verdad=True, signo_plateloc_x=signo, y_plano_ft=plano)
    c = calibrar_plano_y_signo(d, v["t_s"])
    assert (c["elegida"]["signo"], round(c["elegida"]["y_plano_ft"], 6)) == (signo, round(plano, 6))
    assert c["elegida"]["error_side_ft"]["p99"] < 1e-6 and c["elegida"]["error_height_ft"]["p99"] < 1e-6
    assert c["zonetime"]["mediana"] < 1e-9                              # ZoneTime ≈ t_p − t_s
    assert len(c["combinaciones"]) == 4
    peor = max(c["combinaciones"], key=lambda x: x["error_side_ft"]["mediana"])
    assert peor["error_side_ft"]["mediana"] > 0.05                    # las demás combinaciones sí se distinguen


def test_calibrar_sin_t_s_no_verifica_zonetime(sint):
    c = calibrar_plano_y_signo(sint[0])
    assert c["zonetime"] is None and "elegida" in c


def test_calibrar_con_pocos_datos_no_revienta():
    assert calibrar_plano_y_signo(generar(2, 1, sucio=False).head(5))["n"] < 10


def test_calibrar_tolera_nulos():
    d, v = generar(4, 6, con_verdad=True)                               # con los nulos reales del sucio
    c = calibrar_plano_y_signo(d, v["t_s"])
    assert c["elegida"]["signo"] == -1 and c["n"] <= d.height


def test_ruido_en_plateloc_se_ve_en_los_errores(sint):
    d, v = sint
    rng = np.random.default_rng(0)
    ruido = d.with_columns(pl.Series("PlateLocSide", d["PlateLocSide"].to_numpy() + rng.normal(0, 0.3, d.height)))
    c = calibrar_plano_y_signo(ruido, v["t_s"])
    assert c["elegida"]["signo"] == -1 and c["elegida"]["error_side_ft"]["mediana"] > 0.1
