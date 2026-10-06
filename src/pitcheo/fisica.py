"""Física del lanzamiento: trayectoria canónica de los 9P (ADR-010) y, desde F2, la descomposición
arrastre-Magnus y el estimador de densidad por juego (Props. 1-3, pendientes).

Los 9P son las columnas `x0,y0,z0`, `vx0,vy0,vz0`, `ax0,ay0,az0`: el modelo de aceleración
constante  r(t) = r0 + v0·t + ½·a·t²  con convención conocida (ejes Trackman de ROADMAP §2: origen
en la punta del plato, y hacia el montículo, z hacia arriba; pies y segundos). Por ADR-010 esa es
la trayectoria canónica del proyecto.

**Marco temporal único (ADR-014, ROADMAP §1.3).** El reloj de los 9P arranca en y0 = 50 ft; los polinomios
`PitchTrajectory{X,Y,Z}c{0,1,2}` y `ZoneTime` arrancan en la liberación (t_s < 0 en el reloj de los 9P).
Por eso el tiempo al plato NO es `ZoneTime`: es la raíz de y(t_p) = y_p con los 9P, y
`ZoneTime ≈ t_p − t_s`. Los polinomios son los 9P en ejes permutados (ADR-010, enmienda).
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


def tiempo_al_plato(r0, v0, a, y_plano: float = Y_FRENTE_PLATO_FT) -> np.ndarray:
    """ADR-014: primer t > 0 con y(t) = y_plano en el reloj de los 9P (raíz positiva menor). NaN si no existe."""
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


def _estad(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"mediana": None, "p99": None, "n": 0}
    return {"mediana": float(np.median(v)), "p99": float(np.quantile(v, 0.99)), "n": int(v.size)}


def calibrar_plano_y_signo(df: pl.DataFrame, t_s: np.ndarray | None = None,
                           planos=(Y_FRENTE_PLATO_FT, 0.0), signos=(1, -1)) -> dict:
    """ADR-014: elige el plano y_p y el signo s de PlateLocSide = s·x(t_p) con los 9P (agregado).

    Para cada combinación calcula t_p (raíz de y(t_p) = y_p), evalúa la trayectoria 9P en t_p y compara
    con `PlateLocSide` / `PlateLocHeight`. Elige la de menor suma de errores medianos. Con `t_s` (por
    lanzamiento, alineado con las filas de `df`, NaN si no definido; ADR-010) verifica además
    `ZoneTime ≈ t_p − t_s` con el y_p elegido.
    """
    d = df.select(*_R0, *_V0, *_A0, "ZoneTime", "PlateLocSide", "PlateLocHeight").to_numpy().astype(float)
    ok = np.isfinite(d).all(axis=1)
    if ok.sum() < 10:
        return {"n": int(ok.sum())}
    r0, v0, a, zt, lado, alto = d[ok, 0:3], d[ok, 3:6], d[ok, 6:9], d[ok, 9], d[ok, 10], d[ok, 11]
    combos, tp_de = [], {}
    for yp in planos:
        tp = tiempo_al_plato(r0, v0, a, yp)
        tp_de[float(yp)] = tp
        r = trayectoria_9p(tp, r0, v0, a)
        e_alto = np.abs(r[:, 2] - alto)
        for sg in signos:
            e_lado = np.abs(sg * r[:, 0] - lado)
            combos.append({"y_plano_ft": float(yp), "signo": int(sg),
                           "error_side_ft": _estad(e_lado), "error_height_ft": _estad(e_alto)})
    elegida = min(combos, key=lambda c: (c["error_side_ft"]["mediana"] or np.inf) + (c["error_height_ft"]["mediana"] or np.inf))
    out = {"n": int(ok.sum()), "combinaciones": combos, "elegida": elegida, "zonetime": None}
    if t_s is not None:
        tp = tp_de[elegida["y_plano_ft"]]
        e = np.abs(zt - (tp - np.asarray(t_s, dtype=float)[ok]))
        out["zonetime"] = _estad(e)
        out["zonetime_cruda"] = _estad(np.abs(zt - tp))   # lo que se hacía mal: ZoneTime ≈ t_p
    return out
