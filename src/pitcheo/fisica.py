"""Física del lanzamiento: trayectoria canónica de los 9P (ADR-010) y, desde F2, la descomposición
arrastre-Magnus y el estimador de densidad por juego (Props. 1-3, pendientes).

Los 9P son las columnas `x0,y0,z0`, `vx0,vy0,vz0`, `ax0,ay0,az0`: el modelo de aceleración
constante  r(t) = r0 + v0·t + ½·a·t²  con convención conocida (ejes Trackman de ROADMAP §2: origen
en la punta del plato, y hacia el montículo, z hacia arriba; pies y segundos). Por ADR-010 esa es
la trayectoria canónica del proyecto. Los polinomios `PitchTrajectory{X,Y,Z}c{0,1,2}` del dato real
no comparten ejes con los 9P y ninguna fase depende de ellos.
"""
from __future__ import annotations

import numpy as np
import polars as pl

Y_FRENTE_PLATO_FT = 17.0 / 12.0  # el frente del plato, donde se miden PlateLocSide/PlateLocHeight

_R0 = ("x0", "y0", "z0")
_V0 = ("vx0", "vy0", "vz0")
_A0 = ("ax0", "ay0", "az0")


def trayectoria_9p(t, r0, v0, a) -> np.ndarray:
    """Posición r(t) = r0 + v0·t + ½·a·t² con los 9P.

    `r0`, `v0`, `a`: (3,) o (n, 3). `t`: escalar o (n,) (un tiempo por lanzamiento). Devuelve (n, 3)
    (o (3,) si todo es escalar), en pies. Es exactamente el modelo de aceleración constante.
    """
    r0, v0, a = (np.asarray(x, dtype=float) for x in (r0, v0, a))
    t = np.asarray(t, dtype=float)
    tt = t[..., None] if t.ndim else t
    return r0 + v0 * tt + 0.5 * a * tt**2


def nueve_p(df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(r0, v0, a) como matrices (n, 3) a partir de las columnas 9P del DataFrame."""
    return tuple(df.select(cols).to_numpy().astype(float) for cols in (_R0, _V0, _A0))


def velocidad_9p(t, v0, a) -> np.ndarray:
    """Velocidad v(t) = v0 + a·t."""
    v0, a, t = np.asarray(v0, dtype=float), np.asarray(a, dtype=float), np.asarray(t, dtype=float)
    return v0 + a * (t[..., None] if t.ndim else t)


def tiempo_en_plano_y(r0, v0, a, y_plano: float = Y_FRENTE_PLATO_FT) -> np.ndarray:
    """Primer t > 0 con y(t) = y_plano (raíz positiva más pequeña de la cuadrática en y). NaN si no existe."""
    r0, v0, a = (np.atleast_2d(np.asarray(x, dtype=float)) for x in (r0, v0, a))
    c0, c1, c2 = r0[:, 1] - y_plano, v0[:, 1], 0.5 * a[:, 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        t_lineal = -c0 / c1
        raiz = np.sqrt(np.where(c1**2 - 4 * c2 * c0 >= 0, c1**2 - 4 * c2 * c0, np.nan))
        t1, t2 = (-c1 - raiz) / (2 * c2), (-c1 + raiz) / (2 * c2)
        positivo = lambda x: np.where(x > 0, x, np.inf)
        cuadratico = np.minimum(positivo(t1), positivo(t2))
    cuadratico = np.where(np.isfinite(cuadratico), cuadratico, np.nan)
    return np.where(np.abs(c2) < 1e-12, np.where(t_lineal > 0, t_lineal, np.nan), cuadratico)


def verificar_9p(df: pl.DataFrame) -> dict:
    """Contrasta los 9P con lo que el dato dice por su cuenta (agregado, informativo).

    1. La posición (x, z) en t = ZoneTime debe reproducir PlateLocSide / PlateLocHeight.
    2. y(ZoneTime) debe caer en el frente del plato (17/12 ft).
    """
    d = df.select(*_R0, *_V0, *_A0, "ZoneTime", "PlateLocSide", "PlateLocHeight").drop_nulls()
    if d.height < 10:
        return {"n": d.height}
    r0, v0, a = nueve_p(d)
    r = trayectoria_9p(d["ZoneTime"].to_numpy(), r0, v0, a)
    err_x = np.abs(r[:, 0] - d["PlateLocSide"].to_numpy())
    err_z = np.abs(r[:, 2] - d["PlateLocHeight"].to_numpy())
    err_y = np.abs(r[:, 1] - Y_FRENTE_PLATO_FT)
    q = lambda v, p: float(np.quantile(v, p))
    return {
        "n": int(d.height),
        "error_plato_x_ft": {"mediana": q(err_x, 0.5), "p99": q(err_x, 0.99)},
        "error_plato_z_ft": {"mediana": q(err_z, 0.5), "p99": q(err_z, 0.99)},
        "error_y_en_zonetime_ft": {"mediana": q(err_y, 0.5), "p99": q(err_y, 0.99)},
    }
