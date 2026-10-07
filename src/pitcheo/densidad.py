"""F2 — Densidad del aire por juego desde la trayectoria: análisis sobre los resultados del estimador.

Implementa lo que `docs/MODELO_MATEMATICO.md` (sección F2, revisada por ROADMAP §1.6) pide por encima de la física
de `fisica.py`:

  - `preparar_datos`: Prop. 1 por lanzamiento (marco temporal de ADR-014) y variables del estimador.
  - `estimar_densidad`: Prop. 2′ para δ^D y δ^L, normalización, conjunto conectado y soporte común.
  - `se_cr2`: errores estándar robustos por conglomerados (lanzador dentro del juego) con la corrección CR2
    (Bell y McCaffrey, 2002) sobre la matriz de diseño exacta.
  - `varianza_dos_vias`, `media_cubeta`, `deming`: agrupamiento doble juego × lanzador (Cameron, Gelbach y Miller, 2011)
    para los contrastes entre cubetas y la regresión de Deming.
  - `c_g_desde_diferencia`, `c_g_detector_e`, `verificar_spinaxis_medido`: Prop. 3′ (residuo c_g·g).
  - `parques_latentes`: mezcla gaussiana con BIC sobre δ̂_g por cubeta (🔎, exploratorio).

(`altitud.py` queda reservado para F8, el efecto altitud y los veredictos H1-H6.)

Solo física por lanzamiento: ningún outcome entra en F2. Los `*_anon_id` entran como efecto fijo de
lanzador×forma, para agrupar los SE y para validar; nunca como feature de un modelo de resultados.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import polars as pl
from scipy import linalg, sparse, special

from . import fisica
from .fisica import G_SI

SIN_CUBETA = "(sin cubeta)"


# ==========================================================================
# Preparación: Prop. 1 por lanzamiento + variables del estimador
# ==========================================================================
def _txt(df: pl.DataFrame, col: str) -> pl.Series:
    return df[col].cast(pl.Utf8)


def preparar_datos(df: pl.DataFrame, y_plano_ft: float = fisica.Y_FRENTE_PLATO_FT, piso_ay: float = 1.0) -> dict:
    """Prop. 1 sobre las filas válidas de F0. Devuelve {'d': DataFrame por lanzamiento, 'vec': arrays, 'conteo': ...}.

    Filtros (cada uno se cuenta): `excluir_modelo`, familia EXC (ADR-002: sin descomposición Magnus), id de lanzador
    o de juego nulo, 9P/polinomio/giro nulos, `t_s` o `t_p` indefinidos, ρC_D ≤ 0 o ρC_L ≤ 0 (no hay log).
    `d` trae: juego, lanzador, familia, mano, year, cubeta, `y_D = log ρC_D`, `y_L = log ρC_L`, `S` (factor de giro),
    `estrato` (forma×mano×year) y `lanzador_forma`. `vec` guarda por fila los vectores que usa Prop. 3′
    (ã, v̄, a_⊥, SpinAxis, sesgo de PlateLocHeight, RelHeight) para el detector ê y los parques latentes.
    """
    req = ["game_anon_id", "pitcher_anon_id", "familia", "pitcher_throws_r", "year", "altitude_category_h",
           "excluir_modelo", *fisica._R0, *fisica._V0, *fisica._A0, "PitchTrajectoryXc1", "SpinRate", "SpinAxis"]
    extra = [c for c in ("RelHeight", "PlateLocHeight", "parque_id") if c in df.columns]
    t = df.select([*req, *extra]).with_columns(
        _txt(df, "game_anon_id").alias("game_anon_id"), _txt(df, "pitcher_anon_id").alias("pitcher_anon_id"),
        _txt(df, "familia").alias("familia"), _txt(df, "altitude_category_h").alias("altitude_category_h"),
        *([_txt(df, "parque_id").alias("parque_id")] if "parque_id" in extra else []))
    conteo = {"filas_entrada": t.height}

    def filtrar(nombre: str, mascara: pl.Expr) -> None:
        nonlocal t
        antes = t.height
        t = t.filter(mascara)
        conteo[nombre] = antes - t.height

    filtrar("excluir_modelo", ~pl.col("excluir_modelo").fill_null(True))
    filtrar("familia_EXC", pl.col("familia").is_not_null() & (pl.col("familia") != "EXC"))
    filtrar("id_nulo", pl.col("game_anon_id").is_not_null() & pl.col("pitcher_anon_id").is_not_null()
            & pl.col("pitcher_throws_r").is_not_null())
    num = [*fisica._R0, *fisica._V0, *fisica._A0, "PitchTrajectoryXc1", "SpinRate"]
    filtrar("fisica_nula", pl.all_horizontal(*[pl.col(c).is_finite() for c in num]) & (pl.col("SpinRate") > 0))
    r0, v0, a = fisica.nueve_p(t)
    t_s = fisica.tiempo_liberacion(t["PitchTrajectoryXc1"].to_numpy(), t["vy0"].to_numpy(), t["ay0"].to_numpy(), piso_ay)
    dm = fisica.descomposicion_arrastre_magnus(r0, v0, a, t_s, y_plano_ft)
    s_giro = fisica.factor_giro(t["SpinRate"].to_numpy(), dm["v_norma"])
    valido = (np.isfinite(t_s) & np.isfinite(dm["t_p"]) & np.isfinite(dm["rho_cd"]) & np.isfinite(dm["rho_cl"])
              & (dm["rho_cd"] > 0) & (dm["rho_cl"] > 0) & np.isfinite(s_giro) & (s_giro > 0))
    conteo["t_s_t_p_o_rho_no_positiva"] = int((~valido).sum())
    t = t.filter(pl.Series(valido))
    k = np.flatnonzero(valido)
    mano = np.where(t["pitcher_throws_r"].to_numpy(), "R", "L")
    d = pl.DataFrame({
        "juego": t["game_anon_id"], "lanzador": t["pitcher_anon_id"], "familia": t["familia"], "mano": mano,
        "year": t["year"].cast(pl.Int64), "cubeta": t["altitude_category_h"],
        "y_D": np.log(dm["rho_cd"][k]), "y_L": np.log(dm["rho_cl"][k]), "S": s_giro[k],
    }).with_columns(
        (pl.col("familia") + "|" + pl.col("mano") + "|" + pl.col("year").cast(pl.Utf8)).alias("estrato"),
        (pl.col("lanzador") + "|" + pl.col("familia")).alias("lanzador_forma"))
    vec = {"a_tilde": dm["a_tilde"][k], "v_barra": dm["v_barra"][k], "a_perp": dm["a_perp"][k],
           "l_perp": dm["l_perp"][k], "t_s": t_s[k], "t_p": dm["t_p"][k], "t_m": dm["t_m"][k],
           "spin_axis": t["SpinAxis"].to_numpy().astype(float), "rho_cd": dm["rho_cd"][k], "rho_cl": dm["rho_cl"][k]}
    if "PlateLocHeight" in extra:
        z_p = fisica.trayectoria_9p(dm["t_p"][k], r0[k], v0[k], a[k])[:, 2]
        vec["sesgo_plateloc_z"] = t["PlateLocHeight"].to_numpy().astype(float) - z_p
    if "RelHeight" in extra:
        vec["rel_height"] = t["RelHeight"].to_numpy().astype(float)
    if "parque_id" in extra:
        d = d.with_columns(t["parque_id"].alias("parque"))
    conteo["filas_salida"] = d.height
    return {"d": d, "vec": vec, "conteo": conteo}


# ==========================================================================
# Estimación: Prop. 2′ para δ^D y δ^L
# ==========================================================================
def soporte_comun(d: pl.DataFrame, diseno, q=(0.025, 0.975), n_min_cubeta: int = 30) -> tuple[np.ndarray, dict]:
    """Soporte común de S entre cubetas por estrato → (máscara por fila usada, resumen).

    En cada estrato se toman los cuantiles `q` de S dentro de cada cubeta y el soporte común es la intersección de esos
    rangos. Una fila está en el soporte si su S cae adentro. Es la condición de rango de la Prop. 2′: solo allí se
    compara el mismo tipo de lanzamiento entre parques de distinta densidad.
    """
    u = diseno.usadas
    S = d["S"].to_numpy()[u]
    est = d["estrato"].to_numpy()[u]
    cub = d["cubeta"].to_numpy()[u]
    tiene = np.array([c is not None for c in cub])
    en = np.zeros(len(S), dtype=bool)
    sin_soporte = []
    for e in np.unique(est):
        f = np.flatnonzero(est == e)
        rangos = []
        for c in np.unique(cub[f][tiene[f]]):
            ff = f[cub[f] == c]
            if len(ff) >= n_min_cubeta:
                rangos.append(np.quantile(S[ff], q))
        if len(rangos) < 2:
            en[f] = True                                  # un solo parque en el estrato: nada contra qué comparar
            continue
        lo, hi = max(r[0] for r in rangos), min(r[1] for r in rangos)
        if hi <= lo:
            sin_soporte.append(str(e))
            continue
        en[f] = (S[f] >= lo) & (S[f] <= hi)
    return en, {"estratos_sin_soporte_comun": sin_soporte, "filas_en_soporte": int(en.sum()), "filas": len(en)}


def estimar_densidad(d: pl.DataFrame, cfg_f02: dict, referencia: str = "No Altitude", sin_alpha: bool = False) -> dict:
    """Prop. 2′ para y_D y y_L: δ^D, δ^L, conjunto conectado, n efectivo y baja confianza.

    `sin_alpha=True` ajusta el modelo de un solo efecto fijo (sin lanzador×forma) para exhibir el sesgo de
    confusión de los planteles locales (ROADMAP §1.6 (2); solo diagnóstico y sintética).
    """
    jk = d["lanzador_forma"].to_numpy() if not sin_alpha else np.full(d.height, "todos", dtype=object)
    cub = np.array([None if c is None else str(c) for c in d["cubeta"].to_list()], dtype=object)
    y = np.column_stack([d["y_D"].to_numpy(), d["y_L"].to_numpy()])
    args = (cfg_f02.get("n_nudos", 3), cfg_f02.get("grado", 3), cfg_f02.get("n_min_por_col", 20))
    dis = fisica.construir_diseno(d["juego"].to_numpy(), jk, d["S"].to_numpy(), d["estrato"].to_numpy(), cub, *args)
    u = dis.usadas
    res = fisica.estimador_densidad_juego(y[u], d["juego"].to_numpy()[u], jk[u], d["S"].to_numpy()[u],
                                          d["estrato"].to_numpy()[u], cub[u], referencia, *args,
                                          tol=cfg_f02.get("tol_ap", 1e-10), max_iter=cfg_f02.get("max_iter_ap", 5000),
                                          solver=cfg_f02.get("solver", "lsmr"))
    dsg = res["diseno"]
    en_soporte, sop = soporte_comun(d.filter(pl.Series(u)), dsg, tuple(cfg_f02.get("soporte_q", (0.025, 0.975))))
    n_g = np.bincount(dsg.juego, minlength=len(dsg.juegos))
    n_ef = np.bincount(dsg.juego, weights=en_soporte.astype(float), minlength=len(dsg.juegos))
    return {"res": res, "diseno": dsg, "n_g": n_g, "n_efectivo": n_ef, "soporte": sop, "en_soporte": en_soporte,
            "mascara": u, "baja_confianza": n_ef < cfg_f02.get("n_min_efectivo", 30)}


# ==========================================================================
# Errores estándar: CR2 por conglomerados lanzador-dentro-del-juego
# ==========================================================================
def se_cr2(diseno, resid: np.ndarray, conglomerado: np.ndarray, en_referencia: np.ndarray,
           max_p: int = 14000) -> dict:
    """SE de δ_g normalizado (δ_g − media de la cubeta de referencia) con corrección CR2 (Bell–McCaffrey 2002).

    Sobre la matriz de diseño EXACTA X (juegos sin el de referencia + lanzador×forma + f_D). Para cada conglomerado
    c (lanzador dentro del juego) con filas X_c y residuo e_c: H_cc = X_c (X'X)⁻¹ X_c', A_c = (I − H_cc)^{-1/2} y la
    varianza de c'β̂ es Σ_c (c'(X'X)⁻¹ X_c' A_c e_c)². El contraste es c = e_g − promedio de los juegos de referencia,
    el mismo que normaliza δ. `resid`: (n, m) para m respuestas con el mismo diseño.

    Devuelve `se` (G, m), `sigma_eta` (m,), `se_ingenuo` (G, m) = σ_η/√n_g y `metodo`. Si p > `max_p` (inversa
    densa inviable) cae a un CR0 aproximado (sin corrección de apalancamiento) y lo declara. No se usan grados de
    libertad de Satterthwaite: G2.4 solo pide el SE.
    """
    n = resid.shape[0]
    n_g = len(diseno.juegos)
    ref = int(np.argmax(en_referencia))
    X, info = fisica.matriz_diseno_dispersa(diseno, ref_juego=ref)
    p = X.shape[1]
    sigma = np.sqrt((resid**2).sum(axis=0) / max(n - p, 1))
    n_juego = np.bincount(diseno.juego, minlength=n_g)
    se_ing = sigma[None, :] / np.sqrt(n_juego)[:, None]
    if p > max_p:
        return {**_cr0_aprox(diseno, resid, conglomerado), "sigma_eta": sigma, "se_ingenuo": se_ing, "p": p}
    minv = _inversa_gram(X)
    pos = info["cols_juego"]
    R = np.zeros((n_g, p))
    ok = pos >= 0
    R[ok] = minv[pos[ok]]
    M = R - R[en_referencia].mean(axis=0)                           # (G, p): contraste δ_g − media_ref
    var = _var_cr2(X, minv, resid, conglomerado, M)
    return {"se": np.sqrt(var), "sigma_eta": sigma, "se_ingenuo": se_ing, "metodo": "CR2", "p": p}


def _inversa_gram(X: sparse.csr_matrix) -> np.ndarray:
    """(X'X)⁻¹ densa con un ridge mínimo (Cholesky); pinv si no es definida positiva."""
    p = X.shape[1]
    xtx = (X.T @ X).toarray()
    try:
        c = linalg.cho_factor(xtx + 1e-12 * np.trace(xtx) / p * np.eye(p), lower=True, check_finite=False)
        return linalg.cho_solve(c, np.eye(p), check_finite=False)
    except linalg.LinAlgError:
        return np.linalg.pinv(xtx, hermitian=True)


def _var_cr2(X: sparse.csr_matrix, minv: np.ndarray, resid: np.ndarray, conglomerado: np.ndarray,
             M: np.ndarray) -> np.ndarray:
    """Var CR2 (Bell–McCaffrey) de los contrastes C·β̂: Σ_c (M X_c' A_c e_c)², A_c = (I − H_cc)^{-1/2}.

    `M` (q × p) es el contraste YA multiplicado por (X'X)⁻¹ (M = C·minv). `resid` (n, m) puede traer varias respuestas
    con el mismo diseño; devuelve la varianza (q, m).
    """
    orden = np.argsort(conglomerado, kind="stable")
    Xs, es = X[orden], resid[orden]
    cs = np.asarray(conglomerado)[orden]
    cortes = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1], True])
    var = np.zeros((M.shape[0], resid.shape[1]))
    for a, b in itertools.pairwise(cortes):
        Xc = Xs[a:b]
        cols = np.unique(Xc.indices)
        Xd = np.zeros((b - a, len(cols)))
        filas = np.repeat(np.arange(b - a), np.diff(Xc.indptr))
        Xd[filas, np.searchsorted(cols, Xc.indices)] = Xc.data
        h = Xd @ minv[np.ix_(cols, cols)] @ Xd.T
        w, v = np.linalg.eigh(np.eye(b - a) - h)
        inv_raiz = np.where(w > 1e-8, 1.0 / np.sqrt(np.clip(w, 1e-8, None)), 0.0)
        ajustado = (v * inv_raiz) @ (v.T @ es[a:b])                 # A_c e_c
        s = M[:, cols] @ (Xd.T @ ajustado)                          # (q, m)
        var += s**2
    return var


def _cr0_aprox(diseno, resid: np.ndarray, conglomerado: np.ndarray) -> dict:
    """Respaldo si no cabe la inversa densa: Var(δ_g) ≈ (1/n_g²) Σ_c (Σ_{i∈c} e_i)², sin corrección de apalancamiento."""
    n_g = len(diseno.juegos)
    n_juego = np.bincount(diseno.juego, minlength=n_g)
    c_u, c_i = np.unique(conglomerado, return_inverse=True)
    juego_c = np.zeros(len(c_u), dtype=int)
    juego_c[c_i] = diseno.juego
    var = np.zeros((n_g, resid.shape[1]))
    for j in range(resid.shape[1]):
        suma_c = np.bincount(c_i, resid[:, j], minlength=len(c_u))
        var[:, j] = np.bincount(juego_c, suma_c**2, minlength=n_g) / n_juego**2
    return {"se": np.sqrt(var), "metodo": "CR0_aproximado (no cupo la inversa densa)"}


# ==========================================================================
# Agrupamiento doble juego × lanzador (Cameron–Gelbach–Miller 2011)
# ==========================================================================
def pesos_juego_lanzador(juego_i: np.ndarray, lanzador_i: np.ndarray, juegos: np.ndarray) -> sparse.csr_matrix:
    """W (G × P): fracción de los lanzamientos del juego g que lanzó el lanzador p (cada fila suma 1)."""
    p_u, p_i = np.unique(lanzador_i, return_inverse=True)
    g_pos = {g: i for i, g in enumerate(juegos)}
    g_i = np.array([g_pos.get(g, -1) for g in juego_i])
    ok = g_i >= 0
    w = sparse.coo_matrix((np.ones(ok.sum()), (g_i[ok], p_i[ok])), shape=(len(juegos), len(p_u))).tocsr()
    w.sum_duplicates()
    fila = np.asarray(w.sum(axis=1)).ravel()
    fila[fila == 0] = 1.0
    return (sparse.diags(1.0 / fila) @ w).tocsr()


def varianza_dos_vias(u: np.ndarray, W: sparse.csr_matrix) -> float:
    """Var = Σ_g u_g² + Σ_p (Σ_g w_gp u_g)² − Σ_{g,p} (w_gp u_g)² (juego + lanzador − intersección).

    `u_g` es la contribución de influencia del juego g al estimador (θ̂ − θ ≈ Σ u_g). Un juego tiene varios lanzadores
    y un lanzador aparece en varios juegos; con pertenencia fraccionaria w_gp la influencia del juego se reparte entre sus
    lanzadores en proporción a sus lanzamientos. Se reduce al estimador de una vía si cada juego tiene un solo lanzador.
    """
    u = np.asarray(u, dtype=float)
    v_juego = float(np.sum(u**2))
    v_lanz = float(np.sum((W.T @ u) ** 2))
    celdas = W.multiply(u[:, None]).tocsr()
    v_inter = float(celdas.multiply(celdas).sum())
    return v_juego + v_lanz - v_inter


def media_cubeta(delta: np.ndarray, grupo: np.ndarray, W: sparse.csr_matrix) -> dict:
    """Media de δ̂_g en un grupo de juegos y su EE con agrupamiento doble. `grupo`: máscara booleana (G,)."""
    n = int(grupo.sum())
    if n < 2:
        return {"n": n, "media": float(delta[grupo].mean()) if n else None, "se": None, "u": None}
    m = float(delta[grupo].mean())
    u = np.where(grupo, (delta - m) / n, 0.0)
    return {"n": n, "media": m, "se": math.sqrt(max(varianza_dos_vias(u, W), 0.0)), "u": u}


def contraste_cubetas(delta: np.ndarray, g1: np.ndarray, g0: np.ndarray, W: sparse.csr_matrix) -> dict:
    """Media(g1) − media(g0) con EE de dos vías (las influencias de cada media se restan)."""
    a, b = media_cubeta(delta, g1, W), media_cubeta(delta, g0, W)
    if a["se"] is None or b["se"] is None:
        return {"diferencia": None, "se": None}
    u = a["u"] - b["u"]
    return {"diferencia": a["media"] - b["media"], "se": math.sqrt(max(varianza_dos_vias(u, W), 0.0))}


# ==========================================================================
# Deming: δ^L sobre δ^D con ambos medidos con error
# ==========================================================================
def deming_pendiente(x: np.ndarray, y: np.ndarray, razon: float) -> tuple[float, float]:
    """Regresión de Deming de y sobre x con `razon` = Var(error de y)/Var(error de x). Devuelve (pendiente, intercepto)."""
    xm, ym = x.mean(), y.mean()
    sxx, syy = np.mean((x - xm) ** 2), np.mean((y - ym) ** 2)
    sxy = np.mean((x - xm) * (y - ym))
    b = (syy - razon * sxx + math.sqrt((syy - razon * sxx) ** 2 + 4 * razon * sxy**2)) / (2 * sxy)
    return float(b), float(ym - b * xm)


def deming(delta_d: np.ndarray, delta_l: np.ndarray, se_d: np.ndarray, se_l: np.ndarray, W: sparse.csr_matrix) -> dict:
    """Deming de δ^L sobre δ^D con razón de varianzas de error de los SE por juego (CR2) e inferencia por dos vías.

    La influencia de cada juego sobre la pendiente se aproxima por *leave-one-game-out*: u_g = (N−1)/N·(b − b_{(−g)}),
    de modo que b̂ − b ≈ Σ u_g, y se combina con `varianza_dos_vias` (juego × lanzador). Hipótesis física: pendiente 1,
    intercepto 0. Devuelve pendiente, intercepto, sus EE, el z de H0: pendiente = 1 y la razón usada.
    """
    n = len(delta_d)
    razon = float(np.mean(se_l**2) / np.mean(se_d**2))
    b, a0 = deming_pendiente(delta_d, delta_l, razon)
    b_sin, a_sin = np.empty(n), np.empty(n)
    for g in range(n):
        k = np.arange(n) != g
        b_sin[g], a_sin[g] = deming_pendiente(delta_d[k], delta_l[k], razon)
    u_b, u_a = (n - 1) / n * (b - b_sin), (n - 1) / n * (a0 - a_sin)
    se_b = math.sqrt(max(varianza_dos_vias(u_b, W), 0.0))
    se_a = math.sqrt(max(varianza_dos_vias(u_a, W), 0.0))
    return {"pendiente": b, "intercepto": a0, "se_pendiente": se_b, "se_intercepto": se_a,
            "z_pendiente_vs_1": (b - 1.0) / se_b if se_b > 0 else None,
            "z_intercepto_vs_0": a0 / se_a if se_a > 0 else None, "razon_varianzas": razon, "n_juegos": n}


# ==========================================================================
# Prop. 3′: ĉ_g desde δ^L − δ^D, y detector ê con SpinAxis medido
# ==========================================================================
def kappa_sustentacion(a_perp: np.ndarray, l_perp: np.ndarray) -> np.ndarray:
    """k_i = (g·n̂_i)/ℓ_i: sensibilidad de log ρC_L a c_g (Prop. 3′), con n̂ = a_⊥/ℓ la sustentación medida.

    Con ã_⊥ = (λ/τ²)·a_L·n̂ + c_g·g_⊥, d log‖ã_⊥‖/dc ≈ (g·n̂)/ℓ, con g = (0, 0, −G): g·n̂ = −G·n̂_z. Cambia de signo
    entre efecto hacia atrás (n̂ hacia arriba, k < 0) y hacia adelante (k > 0): el promedio sobre los lanzamientos es lo
    que ve δ^L.
    """
    with np.errstate(invalid="ignore", divide="ignore"):
        return -G_SI * (a_perp[:, 2] / l_perp) / l_perp


def c_g_desde_diferencia(delta_d: np.ndarray, delta_l: np.ndarray, en_referencia: np.ndarray,
                         kappa_medio: float) -> np.ndarray:
    """ĉ_g = (δ^L_g − δ^D_g − media_ref(δ^L − δ^D)) / κ̄: relativo a la cubeta de referencia (como δ).

    El nivel común de c (el mismo error de calibración en todos los parques, incluida la referencia) lo absorbe
    f_L y no se identifica, igual que el nivel absoluto de ρ; lo que se estima es c_g − c_ref.
    """
    dif = delta_l - delta_d
    return (dif - dif[en_referencia].mean()) / kappa_medio


def _circ_dif(a_deg: np.ndarray, b_deg: np.ndarray) -> np.ndarray:
    return (np.asarray(a_deg) - np.asarray(b_deg) + 180.0) % 360.0 - 180.0


def _r2_dentro(y: np.ndarray, x: np.ndarray, grupos: np.ndarray) -> float:
    """R² multivariado (suma de las columnas de y) de y sobre x tras restar la media por grupo (dentro de lanzador×forma)."""
    _, gi = np.unique(grupos, return_inverse=True)
    n_g = np.bincount(gi)

    def centrar(m: np.ndarray) -> np.ndarray:
        return m - np.column_stack([np.bincount(gi, m[:, k]) / n_g for k in range(m.shape[1])])[gi]

    yc, xc = centrar(y), centrar(x)
    beta = np.linalg.lstsq(xc, yc, rcond=None)[0]
    sst = float(np.sum(yc**2))
    return 1.0 - float(np.sum((yc - xc @ beta) ** 2)) / sst if sst > 0 else float("nan")


def verificar_spinaxis_medido(spin_axis_deg: np.ndarray, a_tilde: np.ndarray, v_barra: np.ndarray,
                              grupos_jk: np.ndarray, desfase_min_grados: float = 1.0, var_min_ms2: float = 0.05,
                              r2_max: float = 0.95) -> dict:
    """¿`SpinAxis` es medido o inferido del movimiento? (ROADMAP §1.6 (1), docs/MODELO_MATEMATICO.md F2.4).

    (i) Se compara el eje con el que implica el movimiento: θ_mov = eje cuya sustentación n̂_M(θ) apunta a ã_⊥. Si
        SpinAxis fue DERIVADO del movimiento, el desfase circular es ≈ 0 (dispersión por debajo de `desfase_min_grados`).
        Se elige el signo lateral σ ∈ {±1} que minimiza ese desfase (la convención del radar no está documentada).
    (ii) Con ê = v̂ × n̂_spin, la desviación estándar de ã·ê dentro de lanzador×forma debe superar `var_min_ms2` (m/s²):
        si es ≈ 0 el eje no aporta información independiente del movimiento.
    (iii) Circularidad (ADR-017): R² de (sen θ, cos θ) de SpinAxis sobre las columnas de movimiento (sen θ_mov,
        cos θ_mov), dentro de lanzador×forma. Si SpinAxis sale del movimiento el R² es ≈ 1 (≥ `r2_max`); con un eje
        medido con su propio ruido queda bien por debajo (sintética: ≈ 0.53 medido contra ≈ 0.99 inferido). El criterio (i)
        solo atrapa un eje derivado con la MISMA v̂ que usa F2; (ii) y (iii) atrapan los derivados con otra.
    Si cualquiera marca "inferido" el eje se declara inferido y el único detector de calibración es G2.3 (Deming).
    """
    from .sintetico import direccion_magnus
    v_hat = v_barra / np.linalg.norm(v_barra, axis=1)[:, None]
    a_par = np.einsum("ij,ij->i", a_tilde, v_hat)
    perp = a_tilde - a_par[:, None] * v_hat
    n_mov = perp / np.linalg.norm(perp, axis=1)[:, None]
    mejor = None
    for sg in (1, -1):
        theta_mov = np.degrees(np.arctan2(n_mov[:, 0] / sg, -n_mov[:, 2])) % 360.0
        desv = float(np.sqrt(np.mean(_circ_dif(spin_axis_deg, theta_mov) ** 2)))
        if mejor is None or desv < mejor[0]:
            mejor = (desv, sg)
    desv, signo = mejor
    th_mov = np.radians(np.degrees(np.arctan2(n_mov[:, 0] / signo, -n_mov[:, 2])) % 360.0)
    th_obs = np.radians(np.asarray(spin_axis_deg, dtype=float))
    r2 = _r2_dentro(np.column_stack([np.sin(th_obs), np.cos(th_obs)]), np.column_stack([np.sin(th_mov), np.cos(th_mov)]),
                    grupos_jk)
    e_hat = np.cross(v_hat, direccion_magnus(spin_axis_deg, v_hat, signo))
    z = np.einsum("ij,ij->i", a_tilde, e_hat)
    _, gi = np.unique(grupos_jk, return_inverse=True)
    sd_z = float(np.std(z - (np.bincount(gi, z) / np.bincount(gi))[gi]))
    inferido = bool(desv < desfase_min_grados or sd_z < var_min_ms2 or r2 >= r2_max)
    return {"medido": not inferido, "signo_lateral": int(signo), "desfase_rms_grados": desv,
            "sd_a_por_e_dentro_jk_ms2": sd_z, "umbral_desfase_grados": desfase_min_grados,
            "umbral_sd_ms2": var_min_ms2, "r2_circularidad": r2, "umbral_r2": r2_max,
            "veredicto": ("SpinAxis medido: se usa el detector ê" if not inferido
                          else "SpinAxis INFERIDO del movimiento: el único detector es G2.3 (Deming)")}


def c_g_detector_e(spin_axis_deg: np.ndarray, a_tilde: np.ndarray, v_barra: np.ndarray, juego_i: np.ndarray,
                   grupos_jk: np.ndarray, juegos: np.ndarray, en_referencia: np.ndarray, signo_lateral: int) -> dict:
    """ĉ_g por juego desde ã·ê = c_g (g·ê) + β_{j,k} + ε con ê = v̂ × n̂_spin (ROADMAP §1.6 (1)).

    Se resta la media por lanzador×forma (β_{j,k}) de ã·ê y de g·ê y se regresa por juego: ĉ_g = Σ x̃ z̃ / Σ x̃²,
    con x = g·ê, z = ã·ê. Como en δ, lo identificado es c_g − c_ref (la cubeta de referencia). Devuelve `c_g`
    (G,) relativo a la referencia y `c_g_crudo` sin normalizar.
    """
    from .sintetico import direccion_magnus
    v_hat = v_barra / np.linalg.norm(v_barra, axis=1)[:, None]
    e_hat = np.cross(v_hat, direccion_magnus(spin_axis_deg, v_hat, signo_lateral))
    z = np.einsum("ij,ij->i", a_tilde, e_hat)
    x = -G_SI * e_hat[:, 2]
    _, gi = np.unique(grupos_jk, return_inverse=True)
    n_g = np.bincount(gi)
    zt, xt = z - (np.bincount(gi, z) / n_g)[gi], x - (np.bincount(gi, x) / n_g)[gi]
    pos = {g: i for i, g in enumerate(juegos)}
    jidx = np.array([pos.get(g, -1) for g in juego_i])
    ok = jidx >= 0
    sxz = np.bincount(jidx[ok], (xt * zt)[ok], minlength=len(juegos))
    sxx = np.bincount(jidx[ok], (xt * xt)[ok], minlength=len(juegos))
    with np.errstate(invalid="ignore", divide="ignore"):
        c_crudo = sxz / sxx
    return {"c_g": c_crudo - np.nanmean(c_crudo[en_referencia]), "c_g_crudo": c_crudo, "sxx": sxx}


# ==========================================================================
# G2.3b: detector ê por parque con Wald (SE CR2) y Benjamini–Hochberg
# ==========================================================================
def benjamini_hochberg(p: np.ndarray, q: float = 0.05) -> np.ndarray:
    """Rechazos con control de FDR al nivel `q` (Benjamini–Hochberg 1995). `p` (m,) → máscara booleana (m,)."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    if m == 0:
        return np.zeros(0, dtype=bool)
    orden = np.argsort(p)
    ok = p[orden] <= q * np.arange(1, m + 1) / m
    k = int(np.flatnonzero(ok).max()) + 1 if ok.any() else 0
    rechazo = np.zeros(m, dtype=bool)
    rechazo[orden[:k]] = True
    return rechazo


def detector_e_parques(spin_axis_deg: np.ndarray, a_tilde: np.ndarray, v_barra: np.ndarray, grupos_jk: np.ndarray,
                       parque: np.ndarray, cubeta: np.ndarray, conglomerado: np.ndarray, signo_lateral: int,
                       q: float = 0.05, min_parques: int = 3, max_p: int = 14000) -> dict:
    """ĉ_ê por parque, centrado en la mediana de su cubeta, con Wald (SE CR2) y BH (G2.3b, ADR-017).

    Modelo: ã·ê = c_parque·(g·ê) + β_{j,k} + ε sobre todos los lanzamientos con parque (id de F0 o parque latente);
    β_{j,k} entra como dummies de lanzador×forma, de modo que las hat values de CR2 son las del modelo completo. Dentro
    de cada cubeta con ≥ `min_parques` parques se resta la mediana de los ĉ (con la mediana de dos centrales si hay un
    número par): el contraste es lineal en β, así que el SE CR2 incluye la covarianza con los parques que fijan la
    mediana. El parque mediano (conteo impar) tiene contraste 0 y no se evalúa. Wald z = contraste/SE, valor p
    normal de dos colas y BH al nivel `q` sobre todos los parques evaluados.

    `parque` y `cubeta` por fila (None = fuera). Devuelve una fila por parque en `parques` y el método de SE.
    """
    from .sintetico import direccion_magnus
    en = np.array([p is not None for p in parque])
    v_hat = v_barra / np.linalg.norm(v_barra, axis=1)[:, None]
    e_hat = np.cross(v_hat, direccion_magnus(spin_axis_deg, v_hat, signo_lateral))
    z = np.einsum("ij,ij->i", a_tilde, e_hat)[en]
    x = (-G_SI * e_hat[:, 2])[en]
    par, jk, cub = (np.asarray(a)[en] for a in (parque, grupos_jk, cubeta))
    cong = np.asarray(conglomerado)[en]
    p_u, p_i = np.unique(par.astype(str), return_inverse=True)
    k_u, k_i = np.unique(jk, return_inverse=True)
    n, n_p, n_k = len(z), len(p_u), len(k_u)
    filas = np.arange(n)
    X = sparse.hstack([sparse.csr_matrix((x, (filas, p_i)), shape=(n, n_p)),
                       sparse.csr_matrix((np.ones(n), (filas, k_i)), shape=(n, n_k))]).tocsr()
    p_tot = n_p + n_k
    cub_p = np.empty(n_p, dtype=object)
    cub_p[p_i] = cub
    metodo = "CR2"
    if p_tot > max_p:                                         # respaldo: FWL + sandwich por conglomerado, sin apalancamiento
        metodo = "CR0 (no cupo la inversa densa)"
        xs, zs = _demedia(x, k_i), _demedia(z, k_i)
        sxx = np.bincount(p_i, xs * xs, minlength=n_p)
        beta = np.bincount(p_i, xs * zs, minlength=n_p) / sxx
        e = zs - beta[p_i] * xs
        c_u, c_i = np.unique(cong, return_inverse=True)
        score = np.bincount(c_i * n_p + p_i, xs * e, minlength=len(c_u) * n_p).reshape(len(c_u), n_p)
        cov_b = np.einsum("ci,cj->ij", score, score) / np.outer(sxx, sxx)
        minv = None
    else:
        minv = _inversa_gram(X)
        coef = minv @ (X.T @ z)
        beta = coef[:n_p]
        e = z - X @ coef
    filas_out, evaluables = [], []
    for c in sorted({c for c in cub_p if c is not None}):
        idx = np.flatnonzero(cub_p == c)
        if len(idx) < min_parques:
            for i in idx:
                filas_out.append({"parque": str(p_u[i]), "cubeta": str(c), "c_hat": float(beta[i]), "evaluable": False})
            continue
        orden = idx[np.argsort(beta[idx])]
        w = np.zeros(n_p)
        if len(orden) % 2:
            w[orden[len(orden) // 2]] = 1.0
        else:
            w[orden[len(orden) // 2 - 1]] = w[orden[len(orden) // 2]] = 0.5
        for i in idx:
            r = -w.copy()
            r[i] += 1.0
            evaluables.append((i, c, r))
    if evaluables:
        C = np.zeros((len(evaluables), p_tot))
        for k, (_, _, r) in enumerate(evaluables):
            C[k, :n_p] = r
        if minv is not None:
            var = _var_cr2(X, minv, e[:, None], cong, C @ minv)[:, 0]
        else:
            var = np.einsum("ki,ij,kj->k", C[:, :n_p], cov_b, C[:, :n_p])
        se = np.sqrt(var)
        cen = np.array([r @ beta for _, _, r in evaluables])
        with np.errstate(invalid="ignore", divide="ignore"):
            zw = np.where(se > 0, cen / se, 0.0)
        pv = np.where(se > 0, special.erfc(np.abs(zw) / math.sqrt(2.0)), 1.0)
        rech = benjamini_hochberg(pv, q)
        for (i, c, _), ce, s_, zz, pp, rr in zip(evaluables, cen, se, zw, pv, rech, strict=True):
            filas_out.append({"parque": str(p_u[i]), "cubeta": str(c), "c_hat": float(beta[i]), "c_centrado": float(ce),
                              "se": float(s_), "z": float(zz), "p": float(pp), "rechaza_bh": bool(rr), "evaluable": True})
    return {"parques": filas_out, "metodo_se": metodo, "q": q, "n_parques": int(n_p)}


def _demedia(v: np.ndarray, grupo: np.ndarray) -> np.ndarray:
    return v - (np.bincount(grupo, v) / np.bincount(grupo))[grupo]


def cobertura_ic95(delta_hat: np.ndarray, delta_verdad: np.ndarray, se: np.ndarray, z: float = 1.96) -> float:
    """Fracción de juegos cuyo IC95 = δ̂ ± z·SE contiene a la δ verdadera."""
    ok = np.isfinite(se) & (se > 0)
    return float(np.mean(np.abs(delta_hat[ok] - delta_verdad[ok]) <= z * se[ok]))


def etiquetas_parque_latente(delta_d: np.ndarray, cubeta_juego: np.ndarray, max_comp: int = 4, n_init: int = 5,
                             semilla: int = 2026) -> np.ndarray:
    """🔎 Parque latente por juego: componente de la mezcla gaussiana (BIC) de δ̂ᴰ dentro de su cubeta (argmax de la
    probabilidad posterior). Etiqueta 'cubeta|k' con k por media creciente; None si el juego no tiene cubeta o la cubeta
    tiene pocos juegos. Sustituye al id de parque cuando F0 no lo trae."""
    from sklearn.mixture import GaussianMixture
    cub = np.array([None if c is None else str(c) for c in cubeta_juego], dtype=object)
    out = np.full(len(cub), None, dtype=object)
    for c in sorted({x for x in cub if x is not None}):
        m = np.flatnonzero(cub == c)
        if len(m) < 8:
            continue
        mz = mezcla_bic(delta_d[m], max_comp, n_init, semilla)
        k = mz["n_componentes"]
        gm = GaussianMixture(k, n_init=n_init, random_state=semilla, reg_covar=1e-8).fit(delta_d[m][:, None])
        rango = np.argsort(np.argsort(gm.means_.ravel()))
        lab = rango[gm.predict(delta_d[m][:, None])]
        out[m] = [f"{c}|{int(i)}" for i in lab]
    return out


def distribucion_por_cubeta(valores: np.ndarray, cubeta_juego: np.ndarray) -> dict:
    """Media, desviación y cuantiles de un valor por juego, por cubeta (agregado)."""
    out = {}
    cub = np.array([None if c is None else str(c) for c in cubeta_juego], dtype=object)
    for c in sorted({x for x in cub if x is not None}):
        v = valores[cub == c]
        v = v[np.isfinite(v)]
        if len(v):
            out[c] = {"n": len(v), "media": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else None,
                      "p05": float(np.quantile(v, 0.05)), "mediana": float(np.median(v)), "p95": float(np.quantile(v, 0.95))}
    return out


# ==========================================================================
# Parques latentes (🔎 exploratorio) y predicción de cubeta
# ==========================================================================
def mezcla_bic(x: np.ndarray, max_comp: int = 4, n_init: int = 5, semilla: int = 2026) -> dict:
    """Mezcla gaussiana 1-D con BIC mínimo sobre `x`. Componentes ordenados por media (la de menor media = la de más
    altitud / menor densidad)."""
    from sklearn.mixture import GaussianMixture
    x = np.asarray(x, dtype=float)[:, None]
    mejor = None
    for k in range(1, min(max_comp, max(len(x) // 5, 1)) + 1):
        gm = GaussianMixture(k, n_init=n_init, random_state=semilla, reg_covar=1e-8).fit(x)
        bic = float(gm.bic(x))
        if mejor is None or bic < mejor[0]:
            mejor = (bic, k, gm)
    bic, k, gm = mejor
    o = np.argsort(gm.means_.ravel())
    return {"n_componentes": int(k), "bic": bic,
            "componentes": [{"media": float(gm.means_.ravel()[i]), "sd": float(np.sqrt(gm.covariances_.ravel()[i])),
                             "peso": float(gm.weights_[i])} for i in o]}


def parques_latentes(delta_d: np.ndarray, cubeta_juego: np.ndarray, rel_height_resid: np.ndarray | None,
                     sesgo_plateloc: np.ndarray | None, max_comp: int = 4, n_init: int = 5, semilla: int = 2026) -> dict:
    """🔎 Mezcla gaussiana con BIC sobre δ̂_g dentro de cada cubeta; la componente de menor media de *Extreme* define
    ρ_CDMX (ADR-005). Reporta también la distribución por cubeta de los descriptores por juego (RelHeight residual tras
    el efecto fijo de lanzador y sesgo medio de PlateLocHeight) si existen."""
    out = {}
    cub = np.array([None if c is None else str(c) for c in cubeta_juego], dtype=object)
    for c in sorted({x for x in cub if x is not None}):
        m = cub == c
        if m.sum() >= 8:
            out[c] = mezcla_bic(delta_d[m], max_comp, n_init, semilla)
    desc = {}
    for nombre, v in (("rel_height_residual_ft", rel_height_resid), ("sesgo_plateloc_height_ft", sesgo_plateloc)):
        if v is not None:
            desc[nombre] = distribucion_por_cubeta(v, cubeta_juego)
    return {"mezclas": out, "descriptores_por_juego": desc, "etiqueta": "🔎 exploratorio"}


def predecir_cubeta(delta: np.ndarray, cubeta_juego: np.ndarray, sin_cubeta: np.ndarray) -> dict:
    """🔎 Para los juegos sin cubeta, la más verosímil según la normal de δ̂_g de cada cubeta (agregado por cubeta)."""
    cub = np.array([None if c is None else str(c) for c in cubeta_juego], dtype=object)
    par = {}
    for c in sorted({x for x in cub if x is not None}):
        v = delta[cub == c]
        if len(v) >= 3:
            par[c] = (float(v.mean()), float(v.std(ddof=1)))
    if not par or not sin_cubeta.any():
        return {"n": int(sin_cubeta.sum()), "predichas": {}}
    cuenta: dict = {}
    for dd in delta[sin_cubeta]:
        ll = {c: -0.5 * ((dd - mu) / sd) ** 2 - math.log(sd) for c, (mu, sd) in par.items()}
        mejor = max(ll, key=ll.get)
        cuenta[mejor] = cuenta.get(mejor, 0) + 1
    return {"n": int(sin_cubeta.sum()), "predichas": cuenta, "etiqueta": "🔎 exploratorio"}
