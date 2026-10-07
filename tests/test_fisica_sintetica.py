"""F2 — física (Prop. 1), estimador de la Prop. 2′ (solvers, normalización, coarsening) y sintética con física exacta."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from pitcheo import densidad as D
from pitcheo import fisica as F
from pitcheo import recursos
from pitcheo import sintetico as N

M_SOBRE_A = F.DOS_M_SOBRE_A


@pytest.fixture(scope="module")
def muestra_5k():
    """≈5 000 lanzamientos (45 juegos × 111) con su diseño y las dos respuestas δ^D, δ^L."""
    df, v = N.generar_fisica(45, 111, 111)
    d = D.preparar_datos(df)["d"]
    jk = d["lanzador_forma"].to_numpy()
    cub = np.array([None if c is None else str(c) for c in d["cubeta"].to_list()], dtype=object)
    y = np.column_stack([d["y_D"].to_numpy(), d["y_L"].to_numpy()])
    dis = F.construir_diseno(d["juego"].to_numpy(), jk, d["S"].to_numpy(), d["estrato"].to_numpy(), cub)
    u = dis.usadas
    args = (y[u], d["juego"].to_numpy()[u], jk[u], d["S"].to_numpy()[u], d["estrato"].to_numpy()[u], cub[u])
    return {"df": df, "v": v, "d": d, "dis": dis, "args": args, "y": y[u]}


# --------------------------------------------------------------------------
# Prop. 1
# --------------------------------------------------------------------------
def test_prop1_sin_ruido_reconstruye_la_aceleracion_exactamente():
    """ã = −(ρC_D·A/2m)‖v̄‖² v̂ + (ρC_L·A/2m)‖v̄‖² n̂ con n̂ = ã_⊥/‖ã_⊥‖: identidad algebraica, error de máquina."""
    rng = np.random.default_rng(3)
    n = 50
    r0 = np.column_stack([rng.normal(0, 1, n), np.full(n, 50.0), rng.normal(6, 0.3, n)])
    v0 = np.column_stack([rng.normal(0, 3, n), rng.normal(-125, 8, n), rng.normal(-4, 3, n)])
    a = np.column_stack([rng.normal(0, 8, n), rng.normal(22, 3, n), rng.normal(-20, 8, n)])
    t_s = rng.normal(-0.036, 0.003, n)
    dm = F.descomposicion_arrastre_magnus(r0, v0, a, t_s)
    v_hat = dm["v_barra"] / dm["v_norma"][:, None]
    n_hat = dm["a_perp"] / dm["l_perp"][:, None]
    rec = (-(dm["rho_cd"] / M_SOBRE_A) * dm["v_norma"] ** 2)[:, None] * v_hat \
        + ((dm["rho_cl"] / M_SOBRE_A) * dm["v_norma"] ** 2)[:, None] * n_hat
    assert np.max(np.abs(rec - dm["a_tilde"])) < 1e-9


def test_prop1_sin_ruido_recupera_rho_en_la_sintetica_con_error_de_regla_del_punto_medio():
    """Sin ruido de posición ni heterogeneidad, δ̂ recupera log(ρ/ρ_No) con el error ≈ s²/4 ∝ ρ² (F2.2), ≲ 0.3 %."""
    df, v = N.generar_fisica(30, 90, 5, sigma_pos_m=0.0, sigma_alpha=0.0, sigma_cd_lanzamiento=0.0, sigma_clima=0.0)
    d = D.preparar_datos(df)["d"]
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20}
    est = D.estimar_densidad(d, cfg, "No Altitude")
    res, dsg = est["res"], est["diseno"]
    pos = {g: i for i, g in enumerate(v["juegos"])}
    log_rho = np.log(v["rho_juego"])[[pos[g] for g in dsg.juegos]]
    verdad = log_rho - log_rho[res["en_referencia"]].mean()
    assert np.max(np.abs(res["delta"][:, 0] - verdad)) < 3e-3


# --------------------------------------------------------------------------
# Solvers: proyecciones alternadas ≡ LSMR ≡ MCO
# --------------------------------------------------------------------------
def test_ap_lsmr_y_mco_coinciden_en_5k(muestra_5k):
    m = muestra_5k
    assert 4000 < len(m["y"]) < 6500
    ap = F.estimador_densidad_juego(*m["args"], diseno=m["dis"], solver="alternando", tol=1e-13, max_iter=20000)
    ls = F.estimador_densidad_juego(*m["args"], diseno=m["dis"], solver="lsmr")
    assert all(x["convergio"] for x in ap["ajuste"] + ls["ajuste"])
    assert np.max(np.abs(ap["delta"] - ls["delta"])) < 1e-8
    assert np.max(np.abs(ap["resid"] - ls["resid"])) < 1e-8
    X, _ = F.matriz_diseno_dispersa(m["dis"])
    for j in range(2):                                  # MCO denso exacto
        b = np.linalg.lstsq(X.toarray(), m["y"][:, j], rcond=None)[0]
        assert np.max(np.abs((m["y"][:, j] - X @ b) - ls["resid"][:, j])) < 1e-8


def test_solver_desconocido_falla_claro(muestra_5k):
    with pytest.raises(ValueError, match="solver"):
        F.estimador_densidad_juego(*muestra_5k["args"], diseno=muestra_5k["dis"], solver="magia")


# --------------------------------------------------------------------------
# Normalización y juegos sin cubeta
# --------------------------------------------------------------------------
def test_normalizacion_no_altitude_es_cero_en_ambas_respuestas(muestra_5k):
    m = muestra_5k
    est = F.estimador_densidad_juego(*m["args"], diseno=m["dis"])
    en_ref = est["en_referencia"]
    assert en_ref.any() and not en_ref.all()
    assert est["delta"][en_ref].mean(axis=0) == pytest.approx([0.0, 0.0], abs=1e-12)
    cub = np.array([str(c) for c in est["diseno"].cubeta_juego])
    assert (cub[en_ref] == "No Altitude").all()


def test_sin_cubeta_se_estiman_pero_no_entran_en_la_referencia():
    df, _ = N.generar_fisica(40, 110, 21)
    juegos = sorted(df["game_anon_id"].unique().to_list())
    sin = set(juegos[:10])                              # los "10 juegos sin cubeta" de los datos reales
    df2 = df.with_columns(pl.when(pl.col("game_anon_id").is_in(list(sin))).then(None)
                          .otherwise(pl.col("altitude_category_h")).alias("altitude_category_h"))
    d = D.preparar_datos(df2)["d"]
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20}
    est = D.estimar_densidad(d, cfg, "No Altitude")
    dsg, res = est["diseno"], est["res"]
    cub = np.array([c is None for c in dsg.cubeta_juego])
    assert cub.sum() == 10 and set(dsg.juegos[cub]) == sin
    assert np.isfinite(res["delta"][cub]).all()                       # se ajustan (🔎 predicción de cubeta)
    assert not res["en_referencia"][cub].any()                        # fuera de la normalización
    # La normalización solo depende de los juegos con cubeta: cambiar los 10 sin cubeta no mueve la referencia.
    assert res["delta"][res["en_referencia"]].mean(axis=0) == pytest.approx([0.0, 0.0], abs=1e-12)


# --------------------------------------------------------------------------
# Coarsening (soporte común y bases de f_D)
# --------------------------------------------------------------------------
def test_fallback_de_coarsening_menos_nudos_lineal_constante():
    x = np.linspace(0.15, 0.25, 400)
    _, nom = F._bloque_spline(x, 3, 3, 20)
    assert nom == "spline"                                            # 6 columnas × 20 = 120 ≤ 400
    B, nom = F._bloque_spline(x[:100], 3, 3, 20)
    assert nom.startswith("spline_") and nom.endswith("_nudos") and B.shape[1] < 6   # menos nudos
    B, nom = F._bloque_spline(x[:70], 3, 3, 20)                       # no cabe ni 1 nudo (4 col × 20 = 80 > 70)
    assert nom == "lineal" and B.shape[1] == 1
    B, nom = F._bloque_spline(x[:40], 3, 3, 20)                       # ni lineal (3 × 20 = 60 > 40)
    assert nom == "constante" and B.shape[1] == 0
    B, nom = F._bloque_spline(np.full(300, 0.2), 3, 3, 20)            # S constante: sin término
    assert nom == "constante" and B.shape[1] == 0


def test_soporte_comun_recorta_a_la_interseccion_de_rangos(muestra_5k):
    m = muestra_5k
    en, info = D.soporte_comun(m["d"].filter(pl.Series(m["dis"].usadas)), m["dis"])
    assert 0.5 < en.mean() <= 1.0 and info["filas"] == len(en)


# --------------------------------------------------------------------------
# Sintética de F2
# --------------------------------------------------------------------------
def test_serie_y_paralelo_son_deterministas_y_la_calibracion_vacia_no_cambia_nada():
    a, _ = N.generar_fisica(6, 80, 7)
    b, _ = N.generar_fisica(6, 80, 7, calibracion_parques={})
    assert a.equals(b)
    p1, _ = N.generar_fisica(6, 80, 7, n_jobs=2, bloque=100)
    p2, _ = N.generar_fisica(6, 80, 7, n_jobs=2, bloque=100)
    assert p1.equals(p2) and p1.height == a.height


def test_esquema_de_calibracion_por_parque_un_tercio_lambda_un_tercio_tau():
    esq = N.esquema_calibracion_parques(N.CUBETAS_G23B, 101)
    assert esq == N.esquema_calibracion_parques(N.CUBETAS_G23B, 101)  # determinista
    for base in (0, 6, 12):                                           # 6 parques por cubeta
        sel = {k - base: v for k, v in esq.items() if base <= k < base + 6}
        assert sum(v == (1.02, 1.0) for v in sel.values()) == 2
        assert sum(v == (1.0, 1.01) for v in sel.values()) == 2
        assert len(sel) == 4                                          # los 2 restantes quedan limpios


def test_la_verdad_de_c_por_juego_sigue_al_parque():
    esq = N.esquema_calibracion_parques(N.CUBETAS_G23B, 5)
    df, v = N.generar_fisica(40, 40, 5, cubetas=N.CUBETAS_G23B, calibracion_parques=esq)
    assert "parque_id" in df.columns
    for g, parque in enumerate(v["parque_juego"]):
        l, t = esq.get(parque, (1.0, 1.0))
        assert v["c_g"][g] == pytest.approx(l / t**2 - 1.0)
    assert set(np.round(np.unique(v["c_g"]), 4)) <= {0.0, 0.02, round(1 / 1.01**2 - 1, 4)}


# --------------------------------------------------------------------------
# Prop. 2″ (Reynolds): recuperación de β y de ρ (ADR-018)
# --------------------------------------------------------------------------
def test_sintetica_sin_beta_reproduce_bit_a_bit_la_anterior():
    """Con `beta_D=beta_L=0` el generador debe ser idéntico a antes (compat ADR-017)."""
    a, va = N.generar_fisica(8, 80, 7)
    b, vb = N.generar_fisica(8, 80, 7, beta_D=0.0, beta_L=0.0)
    assert a.equals(b) and np.array_equal(va["c_g"], vb["c_g"])
    assert vb["beta_D"] == 0.0 and vb["beta_L"] == 0.0


def test_generador_re_puro_sin_ruido_mco_recupera_beta_exactamente():
    """ADR-019 D1: C_D depende SOLO de Re (sin término aditivo en v). Sin ruido ni heterogeneidad, β̂ = β exacto."""
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20, "prop2pp": {"instrumento": False}}
    for beta in (0.0, -0.30):
        df, _ = N.generar_fisica(60, 110, 911, beta_D=beta, sigma_pos_m=0.0, sigma_alpha=0.0, sigma_cd_lanzamiento=0.0)
        r = D.estimar_reynolds(D.preparar_datos(df)["d"], cfg, "No Altitude")
        assert r["estimador"] == "MCO"
        assert abs(r["beta"][0] - beta) < 0.01                                  # si hubiera 1+0.2(v/40−1) daría ≈ −0.1 de más


def _una_replica_beta(beta, semilla):
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20, "prop2pp": {}}
    df, _ = N.generar_fisica(100, 250, semilla, beta_D=beta)
    return D.estimar_reynolds(D.preparar_datos(df)["d"], cfg, "No Altitude")


@pytest.fixture(scope="module")
def beta_con_ruido():
    """Panel de réplicas (semillas de prueba 941-945, no las del protocolo) con β_D = −0.30 y con β_D = 0."""
    from joblib import Parallel, delayed
    out = {}
    with recursos.config_paralelo(2):
        for beta, n in ((-0.30, 5), (0.0, 3)):
            rs = Parallel()(delayed(_una_replica_beta)(beta, 941 + k) for k in range(n))
            out[beta] = {"rs": rs, "beta_D": np.mean([r["beta"][0] for r in rs]), "se": np.mean([r["se_beta"][0] for r in rs]),
                         "mco": np.mean([r["beta_mco"][0] for r in rs]), "beta_L": np.mean([r["beta"][1] for r in rs]),
                         "se_L": np.mean([r["se_beta"][1] for r in rs])}
    return out


def test_beta_d_recupera_menos_030_con_2sls_sesgo_menor_que_2_se(beta_con_ruido):
    """ADR-019 G: con heterogeneidad realista el 2SLS (instrumento log RelSpeed) recupera β_D = −0.30.

    Criterio de Morris, White y Crowther (2019): el sesgo del promedio del panel es < 2·SE. (Queda un resto de ≈ +0.02/+0.03
    atribuible a que S = rω/v̄ entra como control; ver D02c. Una réplica suelta puede quedar a 2-3 SE.)"""
    c = beta_con_ruido[-0.30]
    r = c["rs"][0]
    assert r["estimador"] == "IV" and r["primera_etapa"]["F"] > 1e3
    assert abs(c["beta_D"] - (-0.30)) < 2 * c["se"]
    assert abs(c["beta_L"]) < 3 * c["se_L"]                                     # β_L = 0


def test_beta_cero_no_inventa_dependencia_de_reynolds(beta_con_ruido):
    c = beta_con_ruido[0.0]
    assert abs(c["beta_D"]) < 2 * c["se"]


def test_mco_sin_instrumento_esta_sesgado_por_endogeneidad_de_la_rapidez(beta_con_ruido):
    """Documenta ADR-019: MCO da β̂_D ≈ β − 0.24 aun sin ruido de posición (un C_D mayor frena más y baja ‖v̄‖)."""
    c = beta_con_ruido[-0.30]
    assert c["mco"] < -0.30 - 0.10
    assert abs(c["beta_D"] - (-0.30)) < abs(c["mco"] - (-0.30)) / 3             # el IV corrige la mayor parte del sesgo


def test_iv_usa_s_exogena_y_mco_cae_a_s_medida():
    """ADR-019: con RelSpeed el spline de S usa S_rel = rω/RelSpeed (exógena); sin él, S = rω/v̄ y MCO."""
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20, "prop2pp": {}}
    df, _ = N.generar_fisica(40, 100, 7, beta_D=-0.3)
    d = D.preparar_datos(df)["d"]
    assert "S_rel" in d.columns and np.all(np.isfinite(d["S_rel"].to_numpy()))
    assert np.corrcoef(d["S"].to_numpy(), d["S_rel"].to_numpy())[0, 1] > 0.95    # misma magnitud: S_rel solo cambia v̄ por v_rel
    assert D.estimar_reynolds(d, cfg, "No Altitude")["s_exogena"] is True
    cfg2 = {**cfg, "prop2pp": {"s_exogeno": False}}
    assert D.estimar_reynolds(d, cfg2, "No Altitude")["s_exogena"] is False
    sin = D.estimar_reynolds(D.preparar_datos(df.drop("RelSpeed"))["d"], cfg, "No Altitude")
    assert sin["estimador"] == "MCO" and sin["s_exogena"] is False


def test_sin_relspeed_cae_a_mco_declarado():
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20, "prop2pp": {}}
    df, _ = N.generar_fisica(40, 100, 7, beta_D=-0.3)
    r = D.estimar_reynolds(D.preparar_datos(df.drop("RelSpeed"))["d"], cfg, "No Altitude")
    assert r["estimador"] == "MCO" and r["primera_etapa"] is None


def test_estimador_reynolds_corrige_la_atenuacion_del_nivel():
    """Con β_D = −0.5 el δ̄ᴰ bruto de Extreme queda lejos de log 0.76 y el corregido (2SLS) se acerca."""
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20, "prop2pp": {}}
    df, _ = N.generar_fisica(80, 200, 51, beta_D=-0.5)
    r = D.estimar_reynolds(D.preparar_datos(df)["d"], cfg, "No Altitude")
    cub = np.array(list(r["cubeta_juego"]))
    verdad = np.log(0.76)
    bruto = r["delta"][cub == "Extreme Altitude", 0].mean()
    corregido = r["delta_corregido"][cub == "Extreme Altitude", 0].mean()
    assert abs(bruto - verdad) > 0.10 and abs(corregido - verdad) < abs(bruto - verdad) / 3


def test_sobreidentificacion_detecta_equivalencia_cuando_la_hay():
    """Con β_D=β_L=0 la pendiente predicha ≈ 1; si la Deming observada es 1.0 ± 0.03, equivalencia se aprueba."""
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20}
    df, _ = N.generar_fisica(120, 150, 123, beta_D=0.0, beta_L=0.0)
    r = D.estimar_reynolds(D.preparar_datos(df)["d"], cfg, "No Altitude")
    sobre = D.sobreidentificacion_reynolds(r, 1.0, 0.03, tolerancia=0.10)
    assert abs(sobre["pendiente_predicha"] - 1.0) < 0.1
    sobre_mala = D.sobreidentificacion_reynolds(r, 1.5, 0.02, tolerancia=0.10)
    assert not sobre_mala["equivalencia"]                                      # 0.5 fuera del margen


# --------------------------------------------------------------------------
# Normalización por año (ADR-018 §B)
# --------------------------------------------------------------------------
def test_normalizacion_por_anio_resetea_cero_por_cada_year():
    """δ̄_{No Altitude, year=y} debe ser ≈ 0 ∀ year; en modo global solo la media sobre toda la ref es 0."""
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20}
    df, _ = N.generar_fisica(90, 110, 61)
    d = D.preparar_datos(df)["d"]
    est = D.estimar_densidad(d, cfg, "No Altitude", por_anio=True)
    anio = est["res"]["anio_juego"]
    delta_D = est["res"]["delta"][:, 0]
    en_ref = est["res"]["en_referencia"]
    for y in np.unique(anio):
        m = en_ref & (anio == y)
        if m.any():
            assert abs(delta_D[m].mean()) < 1e-10                              # cada año queda en 0
    est_g = D.estimar_densidad(d, cfg, "No Altitude", por_anio=False)
    delta_g = est_g["res"]["delta"][:, 0]
    assert abs(delta_g[est_g["res"]["en_referencia"]].mean()) < 1e-10          # global queda en 0 pero por año no en general
    por_anio_global = [delta_g[en_ref & (anio == y)].mean() for y in np.unique(anio) if (en_ref & (anio == y)).any()]
    assert max(abs(x) for x in por_anio_global) > 1e-6                         # con global, los años se separan
