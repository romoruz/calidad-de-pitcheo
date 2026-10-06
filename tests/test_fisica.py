"""Trayectoria canónica de los 9P (ADR-010)."""
from __future__ import annotations

import numpy as np
import pytest

from pitcheo.fisica import Y_FRENTE_PLATO_FT, nueve_p, tiempo_en_plano_y, trayectoria_9p, velocidad_9p
from pitcheo.sintetico import generar

R0, V0, A = [0.5, 50.0, 6.0], [-2.0, -130.0, 1.0], [3.0, 25.0, -32.174]


def test_en_t_cero_es_la_posicion_inicial():
    assert trayectoria_9p(0.0, R0, V0, A) == pytest.approx(R0)


def test_es_el_modelo_de_aceleracion_constante():
    t = 0.3
    esperado = [R0[i] + V0[i] * t + 0.5 * A[i] * t**2 for i in range(3)]
    assert trayectoria_9p(t, R0, V0, A) == pytest.approx(esperado)
    # la velocidad es la derivada: diferencias finitas
    h = 1e-6
    dv = (trayectoria_9p(t + h, R0, V0, A) - trayectoria_9p(t - h, R0, V0, A)) / (2 * h)
    assert dv == pytest.approx(velocidad_9p(t, V0, A), rel=1e-6)


def test_vectorizada_un_tiempo_por_lanzamiento():
    r0, v0, a = (np.tile(x, (4, 1)) for x in (R0, V0, A))
    t = np.array([0.0, 0.1, 0.2, 0.3])
    r = trayectoria_9p(t, r0, v0, a)
    assert r.shape == (4, 3)
    assert r[2] == pytest.approx(trayectoria_9p(0.2, R0, V0, A))


def test_tiempo_en_el_frente_del_plato_es_la_raiz_positiva_pequena():
    t = tiempo_en_plano_y(R0, V0, A)
    assert t.shape == (1,) and 0.3 < t[0] < 0.5
    assert trayectoria_9p(t[0], R0, V0, A)[1] == pytest.approx(Y_FRENTE_PLATO_FT)


def test_tiempo_en_plano_sin_solucion_es_nan():
    assert np.isnan(tiempo_en_plano_y([0, 50, 6], [0, 10, 0], [0, 1, 0])).all()     # se aleja del plato


def test_los_9p_del_sintetico_reproducen_zonetime_y_el_plato():
    d = generar(4, 3, sucio=False)
    r0, v0, a = nueve_p(d)
    t = tiempo_en_plano_y(r0, v0, a)
    assert t == pytest.approx(d["ZoneTime"].to_numpy(), abs=1e-9)
    r = trayectoria_9p(d["ZoneTime"].to_numpy(), r0, v0, a)
    assert r[:, 0] == pytest.approx(d["PlateLocSide"].to_numpy(), abs=1e-9)
    assert r[:, 2] == pytest.approx(d["PlateLocHeight"].to_numpy(), abs=1e-9)
