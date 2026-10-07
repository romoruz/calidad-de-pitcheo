"""Física del lanzamiento: trayectoria canónica de los 9P (ADR-010) y, desde F2, la descomposición
arrastre-Magnus (Prop. 1) y el estimador de densidad por juego (Prop. 2′, docs/MODELO_MATEMATICO.md F2).

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

import math
from dataclasses import dataclass, field

import numpy as np
import polars as pl
from scipy import sparse
from scipy.sparse import csgraph

Y_FRENTE_PLATO_FT = 17.0 / 12.0  # el frente del plato, donde se miden PlateLocSide/PlateLocHeight

# Constantes SI (ROADMAP §2) y conversiones de unidades de las columnas (pies, mph, rpm).
FT_M = 0.3048
MPH_MS = 0.44704
RPM_RADS = 2.0 * math.pi / 60.0
M_BOLA = 0.145                      # kg (5.125 oz)
R_BOLA = 0.0368                     # m (circunferencia 9.125 in)
A_BOLA = math.pi * R_BOLA**2        # m²
G_SI = 32.174 * FT_M                # 9.80665 m/s²
DOS_M_SOBRE_A = 2.0 * M_BOLA / A_BOLA   # ≈ 68.2 kg/m²: ρC = −(2m/A)·(ã·v̂)/‖v̄‖²

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


# ==========================================================================
# F2 — Prop. 1: descomposición arrastre-Magnus evaluada en t_m = (t_s + t_p)/2
# ==========================================================================
def tiempo_liberacion(c1_x, vy0, ay0, piso: float = 1.0) -> np.ndarray:
    """t_s por lanzamiento (ADR-010 enmienda): t_s = (c1_X − v_y0)/a_y0, con c1_X = `PitchTrajectoryXc1`.

    El polinomio X corre sobre el eje y de los 9P (permutación X→y) y arranca en la liberación; los 9P, en
    y0 = 50 ft. NaN donde |a_y0| < `piso` (ft/s²): el cociente no está definido.
    """
    c1_x, vy0, ay0 = (np.asarray(x, dtype=float) for x in (c1_x, vy0, ay0))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.abs(ay0) >= piso, (c1_x - vy0) / ay0, np.nan)


def factor_giro(spin_rpm, v_norma_ms) -> np.ndarray:
    """S = r·ω/‖v‖ (§2) con ω = `SpinRate` total (rad/s) y ‖v‖ en m/s."""
    return R_BOLA * np.asarray(spin_rpm, dtype=float) * RPM_RADS / np.asarray(v_norma_ms, dtype=float)


def descomposicion_arrastre_magnus(r0, v0, a, t_s, y_plano: float = Y_FRENTE_PLATO_FT) -> dict:
    """Prop. 1: ρ·C_D y ρ·C_L por lanzamiento desde los 9P, en SI.

    Entradas en las unidades de las columnas (pies, ft/s, ft/s²), `t_s` en s (un valor por lanzamiento).
    Con ã = a − g (g = (0, 0, −g)), v̄ = v0 + a·t_m y t_m = ½(t_s + t_p), donde t_p es la raíz de
    y(t) = y_plano con los 9P (ADR-014; el reloj de los 9P arranca en y0 = 50 ft y t_s < 0):

        ρ·C_D = −(2m/A)·(ã·v̂) / ‖v̄‖²          ρ·C_L = (2m/A)·‖ã − (ã·v̂)v̂‖ / ‖v̄‖².

    Devuelve arrays alineados con las filas: `rho_cd`, `rho_cl`, `v_barra` (n,3, m/s), `v_norma`, `a_tilde`
    (n,3, m/s²), `a_perp` (n,3, vector perpendicular a v̄: dirección de la sustentación medida), `l_perp`
    (su norma), `t_p`, `t_m`. NaN donde t_p o t_s no están definidos. La velocidad representativa es el punto
    medio de la regla del error de segundo orden (docs/MODELO_MATEMATICO.md F2.2).
    """
    r0, v0, a = (np.atleast_2d(np.asarray(x, dtype=float)) for x in (r0, v0, a))
    t_s = np.atleast_1d(np.asarray(t_s, dtype=float))
    t_p = tiempo_al_plato(r0, v0, a, y_plano)
    t_m = 0.5 * (t_s + t_p)
    v_barra = (v0 + a * t_m[:, None]) * FT_M
    a_tilde = a * FT_M + np.array([0.0, 0.0, G_SI])          # ã = a − g, con g = (0, 0, −G_SI)
    v_norma = np.linalg.norm(v_barra, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        v_hat = v_barra / v_norma[:, None]
        a_par = np.einsum("ij,ij->i", a_tilde, v_hat)
        a_perp = a_tilde - a_par[:, None] * v_hat
        l_perp = np.linalg.norm(a_perp, axis=1)
        rho_cd = -DOS_M_SOBRE_A * a_par / v_norma**2
        rho_cl = DOS_M_SOBRE_A * l_perp / v_norma**2
    return {"rho_cd": rho_cd, "rho_cl": rho_cl, "v_barra": v_barra, "v_norma": v_norma, "a_tilde": a_tilde,
            "a_perp": a_perp, "l_perp": l_perp, "t_p": t_p, "t_m": t_m}


# ==========================================================================
# F2 — Prop. 2′: dos efectos fijos (juego + lanzador×forma) con f_D como B-spline de S por estrato
# ==========================================================================
def base_bspline(x, nudos, rango, grado: int = 3) -> np.ndarray:
    """Base B-spline de `x` con nudos internos `nudos` sobre `rango` = (lo, hi), SIN la columna constante.

    La base completa suma 1 (equivale al intercepto), que ya cubren los efectos fijos de juego y de
    lanzador×forma; se descarta la primera columna (vale 0 en el borde inferior) para que el diseño tenga
    rango completo. Devuelve (n, len(nudos) + grado).
    """
    from scipy.interpolate import BSpline
    lo, hi = rango
    t = np.r_[[lo] * (grado + 1), np.asarray(nudos, dtype=float), [hi] * (grado + 1)]
    xs = np.clip(np.asarray(x, dtype=float), lo, hi)
    return BSpline.design_matrix(xs, t, grado, extrapolate=False).toarray()[:, 1:]


def _bloque_spline(x: np.ndarray, n_nudos: int, grado: int, n_min_por_col: int) -> tuple[np.ndarray, str]:
    """Columnas de f_D para un estrato. Fallback: menos nudos → lineal → sin término (ROADMAP §1.6 (5))."""
    lo, hi = float(np.min(x)), float(np.max(x))
    n = len(x)
    if hi - lo < 1e-12:
        return np.zeros((n, 0)), "constante"
    for q in range(n_nudos, 0, -1):                                   # menos nudos
        df = q + grado
        if n >= n_min_por_col * df:
            nudos = np.quantile(x, np.linspace(0.0, 1.0, q + 2)[1:-1])
            if len(np.unique(np.r_[lo, nudos, hi])) == q + 2:
                return base_bspline(x, nudos, (lo, hi), grado), ("spline" if q == n_nudos else f"spline_{q}_nudos")
    if n >= 3 * n_min_por_col:                                        # lineal
        return ((x - lo) / (hi - lo))[:, None], "lineal"
    return np.zeros((n, 0)), "constante"


@dataclass
class DisenoDensidad:
    """Diseño de la Prop. 2′ sobre el conjunto conectado: índices de juego y lanzador×forma, bloques de f_D."""
    usadas: np.ndarray                     # (n_entrada,) bool: filas que entraron (conjunto conectado y válidas)
    juego: np.ndarray                      # (n,) índice 0..G-1 de cada fila usada
    jk: np.ndarray                         # (n,) índice 0..J-1
    juegos: np.ndarray                     # (G,) etiquetas de juego
    grupos: np.ndarray                     # (J,) etiquetas lanzador×forma
    cubeta_juego: np.ndarray               # (G,) cubeta de cada juego (objeto/str, None si no hay)
    bloques: list = field(default_factory=list)   # [(filas (m,), B (m, df), pinv (df, m), nombre, estrato)]
    conectado: dict = field(default_factory=dict)

    @property
    def n_cols_spline(self) -> int:
        return int(sum(b[1].shape[1] for b in self.bloques))


def conjunto_conectado(juego, jk) -> tuple[np.ndarray, dict]:
    """Componente gigante del grafo bipartito juegos–(lanzador×forma) (Abowd–Kramarz–Margolis).

    `juego`, `jk`: etiquetas por fila (sin nulos). Devuelve (máscara de filas en el gigante, resumen). Dentro de
    él δ_g − δ_g' está identificado; fuera, no.
    """
    j_u, j_i = np.unique(np.asarray(juego), return_inverse=True)
    k_u, k_i = np.unique(np.asarray(jk), return_inverse=True)
    n_j, n_k = len(j_u), len(k_u)
    aristas = sparse.coo_matrix((np.ones(len(j_i)), (j_i, n_j + k_i)), shape=(n_j + n_k, n_j + n_k))
    n_comp, etiq = csgraph.connected_components(aristas, directed=False)
    tam = np.bincount(etiq)
    gigante = int(np.argmax(tam))
    juegos_en = etiq[:n_j] == gigante
    filas_en = juegos_en[j_i]
    resumen = {"componentes": int(n_comp), "juegos": int(n_j), "juegos_conectados": int(juegos_en.sum()),
               "grupos_jk": int(n_k), "grupos_jk_conectados": int((etiq[n_j:] == gigante).sum()),
               "filas": len(j_i), "filas_conectadas": int(filas_en.sum()),
               "juegos_fuera": [str(x) for x in j_u[~juegos_en]][:50]}
    return filas_en, resumen


def construir_diseno(juego, lanzador_forma, S, estrato, cubeta=None, n_nudos: int = 3, grado: int = 3,
                     n_min_por_col: int = 20) -> DisenoDensidad:
    """Arma el diseño de la Prop. 2′. Las filas con nulos se descartan; solo entra el conjunto conectado.

    `S`: factor de giro por fila; `estrato`: etiqueta de forma×mano×year por fila (un B-spline de S por
    estrato, con nudos por cuantiles del propio estrato). `cubeta`: cubeta por fila (o None).
    """
    juego, jk, estrato = (np.asarray(x) for x in (juego, lanzador_forma, estrato))
    S = np.asarray(S, dtype=float)
    cub = np.asarray(cubeta, dtype=object) if cubeta is not None else np.full(len(S), None, dtype=object)
    valido = np.isfinite(S) & np.array([(a is not None) and (b is not None) and (c is not None)
                                        for a, b, c in zip(juego, jk, estrato, strict=True)])
    idx = np.flatnonzero(valido)
    en_gigante, resumen = conjunto_conectado(juego[idx], jk[idx])
    usadas = np.zeros(len(S), dtype=bool)
    usadas[idx[en_gigante]] = True
    j_u, j_i = np.unique(juego[usadas], return_inverse=True)
    k_u, k_i = np.unique(jk[usadas], return_inverse=True)
    cub_u = np.empty(len(j_u), dtype=object)
    cub_u[j_i] = cub[usadas]
    d = DisenoDensidad(usadas=usadas, juego=j_i, jk=k_i, juegos=j_u, grupos=k_u, cubeta_juego=cub_u,
                       conectado=resumen)
    s_u, e_i = S[usadas], np.unique(estrato[usadas], return_inverse=True)
    for e in range(len(e_i[0])):
        filas = np.flatnonzero(e_i[1] == e)
        B, nombre = _bloque_spline(s_u[filas], n_nudos, grado, n_min_por_col)
        if B.shape[1]:
            d.bloques.append((filas, B, np.linalg.pinv(B), nombre, str(e_i[0][e])))
        else:
            d.bloques.append((filas, B, B.T, nombre, str(e_i[0][e])))
    d.conectado["estratos"] = {str(b[4]): {"n": len(b[0]), "df": int(b[1].shape[1]), "spline": b[3]}
                               for b in d.bloques}
    return d


def _ajuste_spline(d: DisenoDensidad, r: np.ndarray) -> np.ndarray:
    """Proyección de r sobre las columnas de f_D, estrato por estrato (bloques independientes)."""
    out = np.zeros_like(r)
    for filas, B, P, *_ in d.bloques:
        if B.shape[1]:
            out[filas] = B @ (P @ r[filas])
    return out


def ajustar_alternando(d: DisenoDensidad, y, tol: float = 1e-10, max_iter: int = 5000) -> dict:
    """Mínimos cuadrados de y sobre {δ_g} + {α_jk} + f_D por proyecciones alternadas (Guimarães–Portugal 2010).

    Cada vuelta proyecta sobre los dummies de juego, luego los de lanzador×forma y luego los bloques de f_D;
    converge al ajuste de MCO. Devuelve `delta` (G,), `alpha` (J,), `ajuste_f` (n,), `resid` (n,) y el número
    de iteraciones. δ y α quedan identificados salvo una constante común (se fija al normalizar).
    """
    y = np.asarray(y, dtype=float)[d.usadas]
    n_g, n_j = len(d.juegos), len(d.grupos)
    cg, cj = np.bincount(d.juego, minlength=n_g), np.bincount(d.jk, minlength=n_j)
    delta, alpha, spl = np.zeros(n_g), np.zeros(n_j), np.zeros_like(y)
    ajuste, cambio, it = np.zeros_like(y), np.inf, 0
    for it in range(1, max_iter + 1):
        delta = np.bincount(d.juego, y - alpha[d.jk] - spl, minlength=n_g) / cg
        alpha = np.bincount(d.jk, y - delta[d.juego] - spl, minlength=n_j) / cj
        spl = _ajuste_spline(d, y - delta[d.juego] - alpha[d.jk])
        nuevo = delta[d.juego] + alpha[d.jk] + spl
        cambio = float(np.max(np.abs(nuevo - ajuste)))
        ajuste = nuevo
        if cambio < tol:
            break
    return {"delta": delta, "alpha": alpha, "ajuste_f": spl, "resid": y - ajuste, "iteraciones": it,
            "convergio": bool(cambio < tol), "cambio_final": cambio}


def matriz_diseno_dispersa(d: DisenoDensidad, ref_juego: int = 0) -> tuple[sparse.csr_matrix, dict]:
    """Matriz X (n × p) de la Prop. 2′ en una parametrización de rango completo, para MCO exacto y CR2.

    Columnas: dummies de juego (menos el de referencia `ref_juego`, δ = 0), dummies de lanzador×forma y las
    columnas de f_D. Devuelve (X, {'cols_juego': (G,) posición de cada δ (−1 para la referencia)}).
    """
    n, n_g, n_j = len(d.juego), len(d.juegos), len(d.grupos)
    pos_g = np.full(n_g, -1, dtype=int)
    otros = [g for g in range(n_g) if g != ref_juego]
    pos_g[otros] = np.arange(len(otros))
    filas = np.arange(n)
    bloques = []
    m = pos_g[d.juego]
    ok = m >= 0
    bloques.append(sparse.csr_matrix((np.ones(ok.sum()), (filas[ok], m[ok])), shape=(n, n_g - 1)))
    bloques.append(sparse.csr_matrix((np.ones(n), (filas, d.jk)), shape=(n, n_j)))
    # Las columnas de f_D de cada estrato ocupan su propio rango de columnas.
    ancho, pieza, off = d.n_cols_spline, [], 0
    for f, B, *_ in d.bloques:
        if B.shape[1]:
            fila = np.repeat(f, B.shape[1])
            col = off + np.tile(np.arange(B.shape[1]), len(f))
            pieza.append(sparse.csr_matrix((B.ravel(), (fila, col)), shape=(n, ancho)))
            off += B.shape[1]
    spl = sum(pieza) if pieza else sparse.csr_matrix((n, 0))
    X = sparse.hstack([bloques[0], bloques[1], spl]).tocsr()
    return X, {"cols_juego": pos_g, "n_juego": n_g - 1, "n_jk": n_j, "n_spline": ancho}


def estimador_densidad_juego(y, juego, lanzador_forma, S, estrato, cubeta=None, referencia: str = "No Altitude",
                             n_nudos: int = 3, grado: int = 3, n_min_por_col: int = 20, tol: float = 1e-10,
                             max_iter: int = 5000, diseno: DisenoDensidad | None = None) -> dict:
    """Prop. 2′: δ_g por juego desde y = log(ρC) con efectos fijos de juego y lanzador×forma y f_D(S) por estrato.

    `y`: (n,) o (n, m) (p. ej. las columnas δ^D y δ^L comparten diseño). Se estima por proyecciones alternadas
    dentro del conjunto conectado. **Normalización:** δ̄ sobre los juegos de la cubeta `referencia` := 0 (el
    nivel absoluto no está identificado). Los juegos sin cubeta se estiman pero no entran en la referencia.
    Devuelve `delta` (G, m), `alpha`, `resid` (n_usadas, m), `diseno`, `iteraciones`, `convergio`.
    """
    y = np.asarray(y, dtype=float)
    y2 = y[:, None] if y.ndim == 1 else y
    d = diseno or construir_diseno(juego, lanzador_forma, S, estrato, cubeta, n_nudos, grado, n_min_por_col)
    en_ref = np.array([c == referencia for c in d.cubeta_juego])
    if not en_ref.any():
        raise ValueError(f"no hay juegos de la cubeta de referencia {referencia!r} en el conjunto conectado")
    deltas, alphas, resids, info = [], [], [], []
    for j in range(y2.shape[1]):
        ok_y = np.isfinite(y2[:, j])
        if not ok_y.all():
            raise ValueError("y tiene nulos entre las filas usadas; filtra antes de llamar al estimador")
        r = ajustar_alternando(d, y2[:, j], tol, max_iter)
        nivel = float(np.mean(r["delta"][en_ref]))
        deltas.append(r["delta"] - nivel)
        alphas.append(r["alpha"] + nivel)                    # δ + c, α − c deja el ajuste intacto
        resids.append(r["resid"])
        info.append({k: r[k] for k in ("iteraciones", "convergio", "cambio_final")})
    return {"delta": np.column_stack(deltas), "alpha": np.column_stack(alphas), "resid": np.column_stack(resids),
            "diseno": d, "ajuste": info, "juegos": d.juegos, "en_referencia": en_ref}
