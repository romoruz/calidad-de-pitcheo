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
    extra = [c for c in ("RelHeight", "PlateLocHeight", "parque_id", "RelSpeed") if c in df.columns]
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
        "y_D": np.log(dm["rho_cd"][k]), "y_L": np.log(dm["rho_cl"][k]), "S": s_giro[k], "v_norma": dm["v_norma"][k],
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
    if "RelSpeed" in extra:                       # instrumento de log‖v̄‖ en la Prop. 2″ (ADR-019): mph → log m/s
        rs = t["RelSpeed"].to_numpy().astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            d = d.with_columns(pl.Series("log_rel_speed", np.where(rs > 0, np.log(rs * 0.44704), np.nan)))
            sr = fisica.R_BOLA * t["SpinRate"].to_numpy().astype(float) * fisica.RPM_RADS / np.where(rs > 0, rs * 0.44704, np.nan)
            d = d.with_columns(pl.Series("S_rel", sr))      # S con la rapidez de liberación: exógena al arrastre (ADR-019)
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


def estimar_densidad(d: pl.DataFrame, cfg_f02: dict, referencia: str = "No Altitude", sin_alpha: bool = False,
                     por_anio: bool = True) -> dict:
    """Prop. 2′ para y_D y y_L: δ^D, δ^L, conjunto conectado, n efectivo y baja confianza.

    `sin_alpha=True` ajusta el modelo de un solo efecto fijo (sin lanzador×forma) para exhibir el sesgo de
    confusión de los planteles locales (ROADMAP §1.6 (2); solo diagnóstico y sintética).
    `por_anio=True` (default, ADR-018): normaliza δ̄_{referencia, year=y} := 0 en cada año; si False, por media global
    de la referencia (compat ADR-017).
    """
    jk = d["lanzador_forma"].to_numpy() if not sin_alpha else np.full(d.height, "todos", dtype=object)
    cub = np.array([None if c is None else str(c) for c in d["cubeta"].to_list()], dtype=object)
    y = np.column_stack([d["y_D"].to_numpy(), d["y_L"].to_numpy()])
    args = (cfg_f02.get("n_nudos", 3), cfg_f02.get("grado", 3), cfg_f02.get("n_min_por_col", 20))
    dis = fisica.construir_diseno(d["juego"].to_numpy(), jk, d["S"].to_numpy(), d["estrato"].to_numpy(), cub, *args)
    anio_juego = None
    if por_anio:
        jd = d.group_by("juego").agg(pl.col("year").first().alias("year"))
        anio_de = dict(zip(jd["juego"].to_list(), jd["year"].to_list(), strict=True))
        anio_juego = np.array([anio_de.get(g) for g in dis.juegos])
    u = dis.usadas
    res = fisica.estimador_densidad_juego(y[u], d["juego"].to_numpy()[u], jk[u], d["S"].to_numpy()[u],
                                          d["estrato"].to_numpy()[u], cub[u], referencia, *args,
                                          tol=cfg_f02.get("tol_ap", 1e-10), max_iter=cfg_f02.get("max_iter_ap", 5000),
                                          solver=cfg_f02.get("solver", "lsmr"), anio_juego=anio_juego)
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
           max_p: int = 14000, grupos_norm: np.ndarray | None = None) -> dict:
    """SE de δ_g normalizado con corrección CR2 (Bell–McCaffrey 2002) sobre la matriz de diseño exacta X.

    Para cada conglomerado c (lanzador dentro del juego) con filas X_c y residuo e_c: H_cc = X_c (X'X)⁻¹ X_c',
    A_c = (I − H_cc)^{-1/2}, y Var(c'β̂) = Σ_c (c'(X'X)⁻¹ X_c' A_c e_c)². El contraste **para cada juego g** es
    `c = e_g − promedio de los juegos de referencia de su mismo grupo de normalización` (ADR-017: un único grupo;
    ADR-018: un grupo por año). `grupos_norm` (G,) etiqueta por juego: 0..k-1 por grupo con referencia, −1 fuera.
    Si `grupos_norm` es None (default), un único grupo = todos los juegos de referencia (compat).

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
    gn = np.zeros(n_g, dtype=int) if grupos_norm is None else np.asarray(grupos_norm, dtype=int)
    etiquetas = np.unique(gn[gn >= 0])
    promedios = {int(lab): R[en_referencia & (gn == lab)].mean(axis=0) for lab in etiquetas
                 if (en_referencia & (gn == lab)).any()}
    fallback = (np.mean(list(promedios.values()), axis=0) if promedios
                else R[en_referencia].mean(axis=0))                 # compat: si no hay grupos válidos
    M = R.copy()
    for g in range(n_g):
        lab = int(gn[g])
        M[g] -= promedios.get(lab, fallback)                        # (G, p): δ̂_g − media_ref dentro de su grupo
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


def _var_cr2_componentes(X: sparse.csr_matrix, minv: np.ndarray, resid: np.ndarray, conglomerado: np.ndarray,
                         M: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Como `_var_cr2`, pero devuelve también Σ_c s_c⁴ para calcular df Satterthwaite / Pustejovsky–Tipton (2018).

    Para cada contraste q × m, V_q = Σ_c s_{c,q}² (la varianza CR2), y df_PT_q ≈ V_q² / Σ_c s_{c,q}⁴ (aproximación
    Satterthwaite usando las contribuciones por cluster; conservadora respecto a la versión exacta de PT).
    """
    orden = np.argsort(conglomerado, kind="stable")
    Xs, es = X[orden], resid[orden]
    cs = np.asarray(conglomerado)[orden]
    cortes = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1], True])
    v = np.zeros((M.shape[0], resid.shape[1]))
    v4 = np.zeros((M.shape[0], resid.shape[1]))
    for a, b in itertools.pairwise(cortes):
        Xc = Xs[a:b]
        cols = np.unique(Xc.indices)
        Xd = np.zeros((b - a, len(cols)))
        filas = np.repeat(np.arange(b - a), np.diff(Xc.indptr))
        Xd[filas, np.searchsorted(cols, Xc.indices)] = Xc.data
        h = Xd @ minv[np.ix_(cols, cols)] @ Xd.T
        w, u = np.linalg.eigh(np.eye(b - a) - h)
        inv_raiz = np.where(w > 1e-8, 1.0 / np.sqrt(np.clip(w, 1e-8, None)), 0.0)
        ajustado = (u * inv_raiz) @ (u.T @ es[a:b])
        s = M[:, cols] @ (Xd.T @ ajustado)
        s2 = s * s
        v += s2
        v4 += s2 * s2
    return v, v4


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
# Prop. 2″ (ADR-018): corrección de Reynolds para la atenuación en δ̂
# ==========================================================================
def _r2_lineal_dentro(x: np.ndarray, X: sparse.csr_matrix, max_p: int = 14000) -> float:
    """R² de x sobre X por MCO (ridge mínimo si X es rango deficiente). Diagnóstico de colinealidad.

    Si p > `max_p`, usa LSMR y reporta 1 − SSE/SST. Si SST = 0, devuelve nan.
    """
    x = np.asarray(x, dtype=float)
    sst = float(np.sum((x - x.mean()) ** 2))
    if sst <= 0 or X.shape[1] == 0:
        return float("nan")
    if X.shape[1] <= max_p:
        xtx = (X.T @ X).toarray()
        xty = X.T @ x
        try:
            c = linalg.cho_factor(xtx + 1e-12 * np.trace(xtx) / X.shape[1] * np.eye(X.shape[1]), lower=True, check_finite=False)
            b = linalg.cho_solve(c, xty, check_finite=False)
        except linalg.LinAlgError:
            b = np.linalg.pinv(xtx, hermitian=True) @ xty
    else:
        from scipy.sparse.linalg import lsmr
        norma = np.sqrt(np.asarray(X.multiply(X).sum(axis=0)).ravel())
        norma[norma == 0] = 1.0
        Xs = X @ sparse.diags(1.0 / norma)
        sol = lsmr(Xs, x, atol=1e-10, btol=1e-10, maxiter=20000)
        b = sol[0] / norma
    sse = float(np.sum((x - X @ b) ** 2))
    return 1.0 - sse / sst


def _normalizar_por_grupo(delta: np.ndarray, en_ref: np.ndarray, grupos_norm: np.ndarray) -> np.ndarray:
    """Resta de cada δ_g la media de los δ de referencia que comparten su grupo de normalización (ADR-018)."""
    gn = np.asarray(grupos_norm, dtype=int)
    etiquetas = np.unique(gn[gn >= 0])
    medias = {int(lab): float(delta[en_ref & (gn == lab)].mean()) for lab in etiquetas
              if (en_ref & (gn == lab)).any()}
    fallback = float(np.mean(list(medias.values()))) if medias else float(delta[en_ref].mean()) if en_ref.any() else 0.0
    aj = np.array([medias.get(int(a), fallback) for a in gn])
    return delta - aj


def estimar_reynolds(d: pl.DataFrame, cfg_f02: dict, referencia: str = "No Altitude", por_anio: bool = True,
                     instrumento: bool | None = None) -> dict:
    """Prop. 2″ (ADR-018/019): `y_c = δ_g + α_{j,k} + f_c(S) + β_c · log‖v̄‖ + ε` → β̂_c, δ̂_c y δ̃_c = δ̂_c/(1+β̂_c).

    **Endogeneidad (ADR-019).** log‖v̄‖ (rapidez en el punto medio del vuelo) depende del arrastre del propio
    lanzamiento: un C_D mayor frena más y baja ‖v̄‖, justo cuando y = log ρC_D sube. MCO da β̂ sesgado hacia abajo
    (≈ −0.24 en la sintética aun sin ruido de medición). Con la columna `log_rel_speed` (log de la rapidez en la
    liberación, medida antes del vuelo y por tanto exógena al arrastre) se estima por **2SLS**: segunda etapa sobre
    [dummies de juego, lanzador×forma, splines de S, x̂] con x̂ el ajuste de la primera etapa de log‖v̄‖ sobre las
    mismas columnas más el instrumento; el spline de S usa `S_rel = rω/RelSpeed` (exógena) y no S = rω/v̄, que arrastra la
    parte endógena de v̄ y deja un sesgo residual de ≈ +0.03 en β̂ (`prop2pp.s_exogeno`). Como x̂ es una proyección sobre span(X, z), β̂ − β = (W'W)⁻¹W'e exactamente
    (e = residuo ESTRUCTURAL con el log‖v̄‖ observado) y el SE es el sándwich CR2 sobre W (aproximación: leverages de la
    segunda etapa). `instrumento=None` usa IV si hay `log_rel_speed` con datos y `prop2pp.instrumento` no es falso;
    si no, MCO (declarado en `estimador`). Siempre se reporta también `beta_mco` (diagnóstico).

    Devuelve `beta`, `se_beta` (2,), `delta`, `se_delta`, `delta_corregido`, `se_delta_corregido` (G, 2), `estimador`
    ("IV" | "MCO"), `beta_mco`, `primera_etapa` ({corr, F, r2_parcial}), `r2_colinealidad_log_v`, `juegos`, etc.
    """
    p2 = cfg_f02.get("prop2pp") or {}
    quiere_iv = p2.get("instrumento", True) if instrumento is None else instrumento
    n_perdido = 0
    if quiere_iv and "log_rel_speed" in d.columns:
        buenos = np.isfinite(d["log_rel_speed"].to_numpy())
        n_perdido = int((~buenos).sum())
        if buenos.mean() >= p2.get("instrumento_fraccion_min", 0.95):
            d = d.filter(pl.Series(buenos))
        else:
            quiere_iv = False
    else:
        quiere_iv = False
    jk = d["lanzador_forma"].to_numpy()
    cub = np.array([None if c is None else str(c) for c in d["cubeta"].to_list()], dtype=object)
    args = (cfg_f02.get("n_nudos", 3), cfg_f02.get("grado", 3), cfg_f02.get("n_min_por_col", 20))
    s_exo = bool(quiere_iv and p2.get("s_exogeno", True) and "S_rel" in d.columns and np.all(np.isfinite(d["S_rel"].to_numpy())))
    s_col = d["S_rel"].to_numpy() if s_exo else d["S"].to_numpy()    # S = rω/v̄ es endógena (v̄ lleva el arrastre del lanzamiento)
    dis = fisica.construir_diseno(d["juego"].to_numpy(), jk, s_col, d["estrato"].to_numpy(), cub, *args)
    u = dis.usadas
    v_norma = d["v_norma"].to_numpy()
    if not np.all(np.isfinite(v_norma[u]) & (v_norma[u] > 0)):
        raise ValueError("v_norma debe ser positivo y finito tras preparar_datos (filtra antes)")
    x = np.log(v_norma[u])
    ys = np.column_stack([d["y_D"].to_numpy()[u], d["y_L"].to_numpy()[u]])
    ll, jg = d["lanzador"].to_numpy()[u], d["juego"].to_numpy()[u]
    conglom = np.char.add(np.char.add(ll.astype(str), "|"), jg.astype(str))
    en_ref = np.array([c == referencia for c in dis.cubeta_juego])
    if por_anio:
        jd = d.group_by("juego").agg(pl.col("year").first().alias("year"))
        anio_de = dict(zip(jd["juego"].to_list(), jd["year"].to_list(), strict=True))
        anio_juego = np.array([anio_de.get(g) for g in dis.juegos])
        anios_ref = np.unique(anio_juego[en_ref])
        pos_y = {y: i for i, y in enumerate(anios_ref)}
        grupos_norm = np.array([pos_y.get(a, -1) for a in anio_juego], dtype=int)
    else:
        anio_juego = None
        grupos_norm = np.zeros(len(dis.juegos), dtype=int)

    X_base, info = fisica.matriz_diseno_dispersa(dis, ref_juego=0)
    n_base = X_base.shape[1]
    # --- primera etapa (si hay instrumento) y regresor de la segunda etapa
    primera = None
    if quiere_iv:
        z = d["log_rel_speed"].to_numpy()[u]
        Xz = sparse.hstack([X_base, sparse.csr_matrix(z[:, None])]).tocsr()
        b1, _ = fisica.lsmr_coef(Xz, x)
        x_hat = Xz @ b1
        res_x = x - X_base @ fisica.lsmr_coef(X_base, x)[0]
        res_z = z - X_base @ fisica.lsmr_coef(X_base, z)[0]
        r2p = float((res_x @ res_z) ** 2 / ((res_x @ res_x) * (res_z @ res_z)))
        primera = {"corr_parcial": float(np.sqrt(r2p)), "r2_parcial": r2p,
                   "F": float((len(x) - n_base - 1) * r2p / max(1.0 - r2p, 1e-300))}
        regresor = x_hat
    else:
        regresor = x
    W = sparse.hstack([X_base, sparse.csr_matrix(regresor[:, None])]).tocsr()
    Xo = sparse.hstack([X_base, sparse.csr_matrix(x[:, None])]).tocsr()          # con el log‖v̄‖ observado (MCO)
    coef_w = [fisica.lsmr_coef(W, ys[:, k]) for k in range(2)]
    coef_o = [fisica.lsmr_coef(Xo, ys[:, k]) for k in range(2)]
    beta = np.array([c[0][n_base] for c in coef_w])
    beta_mco = np.array([c[0][n_base] for c in coef_o])
    # residuo estructural: y − X_base b − β·x (log‖v̄‖ observado)
    resid = np.column_stack([ys[:, k] - X_base @ coef_w[k][0][:n_base] - beta[k] * x for k in range(2)])
    p_tot = W.shape[1]
    sigma = np.sqrt((resid ** 2).sum(axis=0) / max(len(x) - p_tot, 1))
    minv = _inversa_gram(W)
    n_g = len(dis.juegos)
    pos_juego = info["cols_juego"]
    R = np.zeros((n_g, p_tot))
    ok = pos_juego >= 0
    R[ok] = minv[pos_juego[ok]]
    delta_bruto = np.column_stack([np.where(pos_juego >= 0, coef_w[k][0][np.maximum(pos_juego, 0)], 0.0) for k in range(2)])
    delta_norm = np.column_stack([_normalizar_por_grupo(delta_bruto[:, k], en_ref, grupos_norm) for k in range(2)])
    etiquetas = np.unique(grupos_norm[grupos_norm >= 0])
    promedios = {int(lab): R[en_ref & (grupos_norm == lab)].mean(axis=0) for lab in etiquetas
                 if (en_ref & (grupos_norm == lab)).any()}
    fallback = np.mean(list(promedios.values()), axis=0) if promedios else R[en_ref].mean(axis=0)
    M_delta = R.copy()
    for g in range(n_g):
        M_delta[g] -= promedios.get(int(grupos_norm[g]), fallback)
    var_delta = _var_cr2(W, minv, resid, conglom, M_delta)
    e_beta = np.zeros((1, p_tot))
    e_beta[0, n_base] = 1.0
    var_beta = _var_cr2(W, minv, resid, conglom, e_beta @ minv)[0]
    var_delta_corr = np.empty((n_g, 2))
    for jr in range(2):
        f = 1.0 / (1.0 + beta[jr])
        M_corr = f * M_delta - (delta_norm[:, jr:jr + 1] * f ** 2) * (e_beta @ minv)
        var_delta_corr[:, jr] = _var_cr2(W, minv, resid[:, jr:jr + 1], conglom, M_corr)[:, 0]
    delta_corregido = delta_norm / (1.0 + beta)[None, :]
    r2_col = _r2_lineal_dentro(x, X_base, cfg_f02.get("max_p_cr2", 14000))
    return {"beta": beta, "se_beta": np.sqrt(var_beta), "beta_mco": beta_mco,
            "estimador": "IV" if quiere_iv else "MCO", "primera_etapa": primera, "s_exogena": s_exo,
            "n_instrumento_perdido": n_perdido, "delta": delta_norm, "se_delta": np.sqrt(var_delta),
            "delta_corregido": delta_corregido, "se_delta_corregido": np.sqrt(var_delta_corr),
            "r2_colinealidad_log_v": float(r2_col), "en_referencia": en_ref, "grupos_norm": grupos_norm,
            "anio_juego": anio_juego, "juegos": dis.juegos, "cubeta_juego": dis.cubeta_juego,
            "sigma_eta": sigma, "conectado": dis.conectado,
            "iteraciones": [None, None], "convergio": [coef_w[k][1] for k in range(2)],
            "n_lanzamientos": len(x), "p_cr2": int(p_tot),
            "pendiente_predicha": float((1.0 + beta[1]) / (1.0 + beta[0])),
            "diseno": dis, "mascara": u}


def sobreidentificacion_reynolds(resultado: dict, pendiente_observada: float, se_observada: float,
                                 tolerancia: float = 0.10, z: float = 1.96) -> dict:
    """Equivalencia pre-fijada: |p − b| + z·√(Var(p) + Var(b)) < `tolerancia` con `p = (1+β_L)/(1+β_D)`.

    `Var(p)` por delta method sobre β̂_D y β̂_L (asumiendo independencia entre respuestas; es conservador y se declara).
    """
    beta = resultado["beta"]
    se_beta = resultado["se_beta"]
    p_hat = float((1.0 + beta[1]) / (1.0 + beta[0]))
    dp_dL = 1.0 / (1.0 + beta[0])
    dp_dD = -(1.0 + beta[1]) / (1.0 + beta[0]) ** 2
    var_p = dp_dL ** 2 * se_beta[1] ** 2 + dp_dD ** 2 * se_beta[0] ** 2
    se_dif = math.sqrt(var_p + se_observada ** 2)
    diferencia = p_hat - pendiente_observada
    frontera = abs(diferencia) + z * se_dif
    return {"pendiente_predicha": p_hat, "pendiente_observada": float(pendiente_observada),
            "diferencia": float(diferencia), "se_predicha": math.sqrt(var_p), "se_observada": float(se_observada),
            "se_diferencia": se_dif, "frontera": float(frontera), "tolerancia": float(tolerancia),
            "equivalencia": bool(frontera < tolerancia), "z": float(z),
            "nota": "SE conservador: asume Cov(β̂_D, β̂_L)=0 entre respuestas (misma X, η correlacionados)"}

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
                         kappa_medio: float, grupos_norm: np.ndarray | None = None) -> np.ndarray:
    """ĉ_g = (δ^L_g − δ^D_g − media_ref de su grupo de normalización) / κ̄.

    `grupos_norm` (G,) sigue la convención de `se_cr2`: una etiqueta por juego o −1 si no hay referencia en el grupo
    (fallback: media de las medias). Si es None, un solo grupo global (compat ADR-017).
    """
    dif = delta_l - delta_d
    if grupos_norm is None:
        return (dif - dif[en_referencia].mean()) / kappa_medio
    gn = np.asarray(grupos_norm)
    etiquetas = np.unique(gn[gn >= 0])
    medias = {int(lab): float(dif[en_referencia & (gn == lab)].mean()) for lab in etiquetas
              if (en_referencia & (gn == lab)).any()}
    fallback = float(np.mean(list(medias.values()))) if medias else float(dif[en_referencia].mean())
    ajuste = np.array([medias.get(int(a), fallback) for a in gn])
    return (dif - ajuste) / kappa_medio


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
                              r2_max: float = 0.95, n_min_evaluable: int = 100,
                              fraccion_min_evaluable: float = 0.5) -> dict:
    """¿`SpinAxis` es medido o inferido del movimiento? **Fail-closed** (ADR-018): un criterio NaN o la máscara de
    evaluación por debajo del umbral declaran el eje INFERIDO/NO EVALUABLE (nunca "medido" por defecto).

    (i) Desfase circular entre SpinAxis y el eje que implica el movimiento (θ_mov, con el signo lateral σ ∈ {±1} que lo
        minimiza): si fue DERIVADO del movimiento, el desfase es ≈ 0 (< `desfase_min_grados`).
    (ii) Con ê = v̂ × n̂_spin, la sd de ã·ê dentro de lanzador×forma debe superar `var_min_ms2` (m/s²): si es ≈ 0 el eje
        no aporta información independiente del movimiento.
    (iii) Circularidad: R² de (sen θ, cos θ) de SpinAxis sobre las columnas de movimiento (sen θ_mov, cos θ_mov) dentro
        de lanzador×forma. Si SpinAxis sale del movimiento es ≈ 1 (≥ `r2_max`); con un eje medido con su propio ruido
        queda bien por debajo (sintética: ≈ 0.53 medido contra ≈ 0.99 inferido).
    **Máscara de validez** por fila: SpinAxis finito; `v_barra`, `a_tilde` finitos; ‖v̄‖ > 0; ‖perp‖ (= l_perp) > 1e-6
    m/s² (una perp exactamente paralela a v̂ es ruido numérico y no informa). Si tras aplicarla quedan < `n_min_evaluable`
    filas o < `fraccion_min_evaluable` de la entrada, el eje se declara **no evaluable** (inferido para efectos de la
    compuerta: G2.3b queda n/e, se usa solo G2.3a).
    """
    from .sintetico import direccion_magnus
    spin_axis_deg = np.asarray(spin_axis_deg, dtype=float)
    a_tilde = np.asarray(a_tilde, dtype=float)
    v_barra = np.asarray(v_barra, dtype=float)
    n_entrada = len(spin_axis_deg)
    v_norma = np.linalg.norm(v_barra, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        v_hat_todas = v_barra / v_norma[:, None]
    valido = (np.isfinite(spin_axis_deg) & np.isfinite(v_norma) & (v_norma > 0)
              & np.all(np.isfinite(a_tilde), axis=1) & np.all(np.isfinite(v_barra), axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        a_par_todas = np.einsum("ij,ij->i", a_tilde, v_hat_todas)
    perp_todas = a_tilde - a_par_todas[:, None] * v_hat_todas
    l_perp_todas = np.linalg.norm(perp_todas, axis=1)
    valido &= np.isfinite(l_perp_todas) & (l_perp_todas > 1e-6)
    n_evaluado = int(valido.sum())
    base = {"umbral_desfase_grados": desfase_min_grados, "umbral_sd_ms2": var_min_ms2, "umbral_r2": r2_max,
            "n_entrada": n_entrada, "n_evaluado": n_evaluado, "n_descartado": n_entrada - n_evaluado,
            "umbral_n_min": n_min_evaluable, "umbral_fraccion": fraccion_min_evaluable}
    if n_evaluado < n_min_evaluable or n_evaluado < fraccion_min_evaluable * max(n_entrada, 1):
        return {"medido": False, "no_evaluable": True, "signo_lateral": 0, "desfase_rms_grados": float("nan"),
                "sd_a_por_e_dentro_jk_ms2": float("nan"), "r2_circularidad": float("nan"), **base,
                "veredicto": ("SpinAxis NO EVALUABLE (muestra válida insuficiente tras filtrar NaN y perpendiculares "
                              "degeneradas); fail-closed → inferido, G2.3b sobre datos reales n/e")}
    v_hat = v_hat_todas[valido]
    perp = perp_todas[valido]
    sa = spin_axis_deg[valido]
    at = a_tilde[valido]
    gj = np.asarray(grupos_jk)[valido]
    n_mov = perp / l_perp_todas[valido][:, None]
    mejor = None
    for sg in (1, -1):
        theta_mov = np.degrees(np.arctan2(n_mov[:, 0] / sg, -n_mov[:, 2])) % 360.0
        difs = _circ_dif(sa, theta_mov) ** 2
        desv = float(np.sqrt(np.mean(difs))) if np.all(np.isfinite(difs)) else float("nan")
        if mejor is None or (np.isfinite(desv) and (not np.isfinite(mejor[0]) or desv < mejor[0])):
            mejor = (desv, sg)
    desv, signo = mejor
    th_mov = np.radians(np.degrees(np.arctan2(n_mov[:, 0] / signo, -n_mov[:, 2])) % 360.0)
    th_obs = np.radians(sa)
    r2 = _r2_dentro(np.column_stack([np.sin(th_obs), np.cos(th_obs)]),
                    np.column_stack([np.sin(th_mov), np.cos(th_mov)]), gj)
    e_hat = np.cross(v_hat, direccion_magnus(sa, v_hat, signo))
    z = np.einsum("ij,ij->i", at, e_hat)
    _, gi = np.unique(gj, return_inverse=True)
    media = (np.bincount(gi, z) / np.maximum(np.bincount(gi), 1))[gi]
    sd_z = float(np.std(z - media))
    # Fail-closed: cualquier NaN en los tres criterios ⇒ inferido/no evaluable.
    criterios_nan = not (np.isfinite(desv) and np.isfinite(sd_z) and np.isfinite(r2))
    inferido = criterios_nan or desv < desfase_min_grados or sd_z < var_min_ms2 or r2 >= r2_max
    out = {"medido": (not inferido), "no_evaluable": bool(criterios_nan), "signo_lateral": int(signo),
           "desfase_rms_grados": desv, "sd_a_por_e_dentro_jk_ms2": sd_z, "r2_circularidad": r2, **base}
    if criterios_nan:
        out["veredicto"] = ("SpinAxis NO EVALUABLE (algún criterio no finito); fail-closed → inferido, G2.3b sobre "
                            "datos reales n/e")
    elif inferido:
        out["veredicto"] = "SpinAxis INFERIDO del movimiento: el único detector es G2.3a (Deming)"
    else:
        out["veredicto"] = "SpinAxis medido: se usa el detector ê"
    return out


def c_g_detector_e(spin_axis_deg: np.ndarray, a_tilde: np.ndarray, v_barra: np.ndarray, juego_i: np.ndarray,
                   grupos_jk: np.ndarray, juegos: np.ndarray, en_referencia: np.ndarray, signo_lateral: int,
                   grupos_norm: np.ndarray | None = None) -> dict:
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
    if grupos_norm is None:
        ajuste = np.nanmean(c_crudo[en_referencia])
        return {"c_g": c_crudo - ajuste, "c_g_crudo": c_crudo, "sxx": sxx}
    gn = np.asarray(grupos_norm)
    etiquetas = np.unique(gn[gn >= 0])
    medias = {int(lab): float(np.nanmean(c_crudo[en_referencia & (gn == lab)])) for lab in etiquetas
              if (en_referencia & (gn == lab)).any()}
    fallback = float(np.nanmean(list(medias.values()))) if medias else float(np.nanmean(c_crudo[en_referencia]))
    aj = np.array([medias.get(int(a), fallback) for a in gn])
    return {"c_g": c_crudo - aj, "c_g_crudo": c_crudo, "sxx": sxx}


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
                       q: float = 0.05, min_parques: int = 2, max_p: int = 14000,
                       contraste: str = "loo", df_tipo: str = "pustejovsky_tipton") -> dict:
    """ĉ_ê por parque con t cluster-robust, control FDR Benjamini–Hochberg al nivel `q` (ADR-018).

    Modelo: ã·ê = c_parque·(g·ê) + β_{j,k} + ε sobre todos los lanzamientos con parque (id de F0 o parque latente),
    con dummies de parque interactuadas con x = g·ê y dummies de lanzador×forma como nuisance. El SE **conglomera por
    `conglomerado`** — ADR-018 recomienda LANZADOR (todos sus juegos y parques), nivel más agregado con correlación
    (Cameron y Miller 2015).

    `contraste`:
      - `"loo"` (ADR-018, default): h_p = c_p − mean(c_q : q ≠ p ∧ cubeta=cubeta(p)). Lineal en {c}: la covarianza
        CR2 entre los contrastes es exacta. Requiere ≥ 2 parques por cubeta.
      - `"mediana"` (ADR-017): h_p = c_p − mediana(c_q : cubeta=cubeta(p)); el parque mediano (impar) no se evalúa.

    `df_tipo`:
      - `"pustejovsky_tipton"` (ADR-018, default): df Satterthwaite con Σ_c s_c⁴ por contraste (aproximación conservadora
        de Pustejovsky y Tipton 2018, J. Bus. Econ. Stat.); p-value t de dos colas.
      - `"normal"` (compat): z-test con la normal.

    Devuelve una fila por parque y el método. Fila evaluable: `c_hat`, `c_centrado`, `se`, `z`, `df`, `p`, `rechaza_bh`.
    """
    from scipy import stats

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
    if p_tot > max_p:
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
        if contraste == "loo":
            m = len(idx)
            for i in idx:
                r = np.zeros(n_p)
                for j in idx:
                    r[j] = -1.0 / (m - 1)
                r[i] = 1.0
                evaluables.append((i, c, r))
        elif contraste == "mediana":
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
        else:
            raise ValueError(f"contraste desconocido: {contraste!r}")
    if evaluables:
        C = np.zeros((len(evaluables), p_tot))
        for k, (_, _, r) in enumerate(evaluables):
            C[k, :n_p] = r
        if minv is not None:
            var, var4 = _var_cr2_componentes(X, minv, e[:, None], cong, C @ minv)
            var, var4 = var[:, 0], var4[:, 0]
        else:
            # CR0 fallback: no hay componentes por A_c; df = (grupos − 1) por simplicidad.
            var = np.einsum("ki,ij,kj->k", C[:, :n_p], cov_b, C[:, :n_p])
            var4 = None
        se = np.sqrt(var)
        cen = np.array([r @ beta for _, _, r in evaluables])
        with np.errstate(invalid="ignore", divide="ignore"):
            tst = np.where(se > 0, cen / se, 0.0)
        if df_tipo == "pustejovsky_tipton" and var4 is not None:
            with np.errstate(invalid="ignore", divide="ignore"):
                df = np.where(var4 > 0, var * var / var4, np.inf)
            pv = np.where(se > 0, 2.0 * stats.t.sf(np.abs(tst), df), 1.0)
        elif df_tipo == "normal" or var4 is None:
            n_cong = len(np.unique(cong))
            df = np.full(len(cen), max(n_cong - 1, 1), dtype=float)
            pv = np.where(se > 0, special.erfc(np.abs(tst) / math.sqrt(2.0)), 1.0)
        else:
            raise ValueError(f"df_tipo desconocido: {df_tipo!r}")
        rech = benjamini_hochberg(pv, q)
        for (i, c, _), ce, s_, zz, dfi, pp, rr in zip(evaluables, cen, se, tst, df, pv, rech, strict=True):
            filas_out.append({"parque": str(p_u[i]), "cubeta": str(c), "c_hat": float(beta[i]), "c_centrado": float(ce),
                              "se": float(s_), "z": float(zz), "df": float(dfi), "p": float(pp),
                              "rechaza_bh": bool(rr), "evaluable": True})
    return {"parques": filas_out, "metodo_se": metodo, "q": q, "n_parques": int(n_p),
            "contraste": contraste, "df_tipo": df_tipo}


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
