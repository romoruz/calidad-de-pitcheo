"""F2 — inferencia: CR2 contra CR0, SpinAxis medido/inferido, G2.3b (BH, detector ê por parque), cobertura y parques latentes."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse

from pitcheo import densidad as D
from pitcheo import sintetico as N


# --------------------------------------------------------------------------
# CR2 contra CR0
# --------------------------------------------------------------------------
def _diseno_pequeno(n_clust=8, por_clust=5):
    """Regresión y = b0 + b1·x con pocos conglomerados desbalanceados en x (apalancamiento alto)."""
    rng = np.random.default_rng(0)
    cl = np.repeat(np.arange(n_clust), por_clust)
    x = rng.normal(size=n_clust * por_clust) + 2.0 * (cl == 0)       # el conglomerado 0 apalanca
    X = sparse.csr_matrix(np.column_stack([np.ones_like(x), x]))
    return X, cl.astype(str)


def test_cr2_es_insesgado_y_cr0_subestima_con_pocos_conglomerados():
    X, cl = _diseno_pequeno()
    minv = D._inversa_gram(X)
    Xd = X.toarray()
    proyector = Xd @ minv @ Xd.T
    M = np.array([[0.0, 1.0]]) @ minv                                # contraste: pendiente
    rng = np.random.default_rng(1)
    cr2, cr0, betas = [], [], []
    for _ in range(4000):
        y = rng.normal(size=Xd.shape[0])                             # errores iid homocedásticos: Σ = I
        e = y - proyector @ y
        betas.append((minv @ (Xd.T @ y))[1])
        cr2.append(D._var_cr2(X, minv, e[:, None], cl, M)[0, 0])
        score = np.array([(M @ (Xd[cl == c].T @ e[cl == c]))[0] for c in np.unique(cl)])
        cr0.append(np.sum(score**2))
    verdadera = np.var(betas)
    assert np.mean(cr2) / verdadera == pytest.approx(1.0, abs=0.06)   # CR2: insesgado bajo el modelo de trabajo
    assert np.mean(cr0) / verdadera < 0.85                            # CR0: subestima (apalancamiento sin corregir)


def test_cr2_de_se_cr2_coincide_con_el_ols_denso_en_una_sintetica_chica():
    df, _ = N.generar_fisica(20, 90, 31)
    P = D.preparar_datos(df)
    d = P["d"]
    cfg = {"n_nudos": 3, "grado": 3, "n_min_por_col": 20}
    est = D.estimar_densidad(d, cfg, "No Altitude")
    u = est["mascara"]
    cong = np.char.add(np.char.add(d["lanzador"].to_numpy()[u].astype(str), "|"), d["juego"].to_numpy()[u].astype(str))
    se = D.se_cr2(est["diseno"], est["res"]["resid"], cong, est["res"]["en_referencia"])
    assert se["metodo"] == "CR2" and np.isfinite(se["se"]).all() and (se["se"] > 0).all()
    assert np.median(se["se"][:, 0]) > np.median(se["se_ingenuo"][:, 0])      # el agrupamiento infla frente al ingenuo
    cr0 = D._cr0_aprox(est["diseno"], est["res"]["resid"], cong)
    assert cr0["se"].shape == se["se"].shape


# --------------------------------------------------------------------------
# SpinAxis: circularidad
# --------------------------------------------------------------------------
def _chequeo_spinaxis(inferido: bool) -> dict:
    df, _ = N.generar_fisica(25, 120, 41, spinaxis_inferido=inferido)
    P = D.preparar_datos(df)
    vec, d = P["vec"], P["d"]
    return D.verificar_spinaxis_medido(vec["spin_axis"], vec["a_tilde"], vec["v_barra"], d["lanzador_forma"].to_numpy())


def test_spinaxis_medido_se_distingue_del_inferido_por_el_desfase_y_el_r2():
    med, inf = _chequeo_spinaxis(False), _chequeo_spinaxis(True)
    assert med["medido"] and not inf["medido"]
    assert med["desfase_rms_grados"] > inf["desfase_rms_grados"]        # (i) solo ordena: la sintética usa v̂ de 50 ft, F2 la v̄ media
    assert med["sd_a_por_e_dentro_jk_ms2"] > 0.05 > inf["sd_a_por_e_dentro_jk_ms2"]    # (ii)
    assert med["r2_circularidad"] < 0.75 and inf["r2_circularidad"] >= 0.95            # (iii) SpinAxis sale del movimiento: circular
    assert med["signo_lateral"] == inf["signo_lateral"] == N.SIGNO_MAGNUS_X


# --------------------------------------------------------------------------
# G2.3b: Benjamini–Hochberg y detector por parque
# --------------------------------------------------------------------------
def test_bh_rechaza_segun_el_procedimiento_de_step_up():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    rech = D.benjamini_hochberg(p, 0.05)
    assert rech.tolist() == [True, True, False, False, False, False, False, False, False, False]
    assert D.benjamini_hochberg(np.array([0.9, 0.8]), 0.05).sum() == 0
    assert D.benjamini_hochberg(np.array([0.001, 0.002, 0.003]), 0.05).all()      # step-up arrastra a los de atrás
    assert D.benjamini_hochberg(np.zeros(0)).shape == (0,)


@pytest.fixture(scope="module")
def detector_pequeno():
    """6 parques por cubeta y calibración inyectada; ≈ 16 k lanzamientos."""
    esq = N.esquema_calibracion_parques(N.CUBETAS_G23B, 55)
    df, _ = N.generar_fisica(120, 130, 55, cubetas=N.CUBETAS_G23B, calibracion_parques=esq, n_jobs=2)
    P = D.preparar_datos(df)
    d, vec = P["d"], P["vec"]
    jk = d["lanzador_forma"].to_numpy()
    cong = np.char.add(np.char.add(d["lanzador"].to_numpy().astype(str), "|"), d["juego"].to_numpy().astype(str))
    chk = D.verificar_spinaxis_medido(vec["spin_axis"], vec["a_tilde"], vec["v_barra"], jk)
    r = D.detector_e_parques(vec["spin_axis"], vec["a_tilde"], vec["v_barra"], jk, d["parque"].to_numpy().astype(object),
                             d["cubeta"].to_numpy().astype(object), cong, chk["signo_lateral"])
    c_ver = {f"park_{k + 1:02d}": l / t**2 - 1 for k, (l, t) in esq.items()}
    return {"r": r, "c_ver": c_ver, "chk": chk}


def test_detector_e_recupera_c_centrado_y_marca_los_parques_contaminados(detector_pequeno):
    r, c_ver = detector_pequeno["r"], detector_pequeno["c_ver"]
    assert detector_pequeno["chk"]["medido"] and r["metodo_se"] == "CR2"
    filas = [f for f in r["parques"] if f["evaluable"]]
    assert len(filas) == 18
    err = [f["c_centrado"] - c_ver.get(f["parque"], 0.0) for f in filas]
    assert np.max(np.abs(err)) < 0.01                                   # el centrado en la mediana recupera ±0.02
    marcados = {f["parque"] for f in filas if f["rechaza_bh"]}
    cont = set(c_ver)
    assert len(marcados & cont) >= 0.8 * len(cont)                       # potencia
    assert all(f["se"] > 0 and np.isfinite(f["z"]) for f in filas)


def test_detector_e_contraste_mediana_marca_parque_mediano_como_no_evaluable():
    """Modo mediana (ADR-017, compat): con 3 parques por cubeta el de la mediana tiene contraste 0 (SE 0, p=1)."""
    df, _ = N.generar_fisica(40, 120, 9, calibracion_parques={}, n_jobs=2)         # 3 + 2 + 3 parques por defecto
    P = D.preparar_datos(df)
    d, vec = P["d"], P["vec"]
    jk = d["lanzador_forma"].to_numpy()
    cong = np.char.add(np.char.add(d["lanzador"].to_numpy().astype(str), "|"), d["juego"].to_numpy().astype(str))
    r = D.detector_e_parques(vec["spin_axis"], vec["a_tilde"], vec["v_barra"], jk, d["parque"].to_numpy().astype(object),
                             d["cubeta"].to_numpy().astype(object), cong, N.SIGNO_MAGNUS_X,
                             min_parques=3, contraste="mediana", df_tipo="normal")
    por_cub: dict = {}
    for f in r["parques"]:
        por_cub.setdefault(f["cubeta"], []).append(f)
    assert all(not f["evaluable"] for f in por_cub["Medium Altitude"])               # 2 parques < min_parques=3
    for c in ("No Altitude", "Extreme Altitude"):
        medianos = [f for f in por_cub[c] if f["evaluable"] and f["se"] == 0.0]
        assert len(medianos) == 1 and medianos[0]["p"] == 1.0 and not medianos[0]["rechaza_bh"]


def test_detector_e_loo_pt_recupera_potencia_sin_fp_en_escenario_calibrado():
    """ADR-018: con contraste LOO + cluster lanzador + t de Pustejovsky-Tipton, potencia alta y FPR bajo."""
    esq = N.esquema_calibracion_parques(N.CUBETAS_G23B, 55)
    df, _ = N.generar_fisica(150, 150, 55, cubetas=N.CUBETAS_G23B, calibracion_parques=esq, n_jobs=2)
    P = D.preparar_datos(df)
    d, vec = P["d"], P["vec"]
    jk = d["lanzador_forma"].to_numpy()
    cong_lanz = d["lanzador"].to_numpy().astype(str)
    r = D.detector_e_parques(vec["spin_axis"], vec["a_tilde"], vec["v_barra"], jk,
                             d["parque"].to_numpy().astype(object), d["cubeta"].to_numpy().astype(object),
                             cong_lanz, N.SIGNO_MAGNUS_X)
    assert r["contraste"] == "loo" and r["df_tipo"] == "pustejovsky_tipton"
    tipo = {f"park_{k + 1:02d}": ("lambda" if l != 1 else "tau") for k, (l, t) in esq.items()}
    cont = [f for f in r["parques"] if f["evaluable"] and f["parque"] in tipo]
    lim = [f for f in r["parques"] if f["evaluable"] and f["parque"] not in tipo]
    assert np.mean([f["rechaza_bh"] for f in cont]) >= 0.80                     # potencia
    assert np.mean([f["rechaza_bh"] for f in lim]) <= 0.10                      # FPR bajo con 1 réplica


def test_detector_e_sin_sesgos_no_marca_nada_con_bh():
    df, _ = N.generar_fisica(120, 130, 77, cubetas=N.CUBETAS_G23B, calibracion_parques={}, n_jobs=2)
    P = D.preparar_datos(df)
    d, vec = P["d"], P["vec"]
    jk = d["lanzador_forma"].to_numpy()
    cong = np.char.add(np.char.add(d["lanzador"].to_numpy().astype(str), "|"), d["juego"].to_numpy().astype(str))
    r = D.detector_e_parques(vec["spin_axis"], vec["a_tilde"], vec["v_barra"], jk, d["parque"].to_numpy().astype(object),
                             d["cubeta"].to_numpy().astype(object), cong, N.SIGNO_MAGNUS_X)
    assert sum(f["rechaza_bh"] for f in r["parques"] if f["evaluable"]) <= 1


# --------------------------------------------------------------------------
# Cobertura y parques latentes
# --------------------------------------------------------------------------
def test_cobertura_ic95_es_la_fraccion_dentro_de_1_96_se():
    rng = np.random.default_rng(2)
    e = rng.normal(size=20000)
    assert D.cobertura_ic95(e, np.zeros_like(e), np.ones_like(e)) == pytest.approx(0.95, abs=0.01)
    assert D.cobertura_ic95(e, np.zeros_like(e), 0.5 * np.ones_like(e)) < 0.70      # SE subestimado → cobertura baja


def test_parques_latentes_separan_dos_componentes_por_cubeta():
    rng = np.random.default_rng(3)
    delta = np.r_[rng.normal(-0.25, 0.01, 40), rng.normal(-0.20, 0.01, 40), rng.normal(0.0, 0.01, 40)]
    cub = np.array(["Extreme Altitude"] * 80 + ["No Altitude"] * 40, dtype=object)
    lab = D.etiquetas_parque_latente(delta, cub)
    assert set(lab[:80]) == {"Extreme Altitude|0", "Extreme Altitude|1"}
    bajo, alto = lab[:40], lab[40:80]                                                # una pertenencia por punto, ≥ 95 % de acierto
    assert np.mean(bajo == "Extreme Altitude|0") >= 0.95 and np.mean(alto == "Extreme Altitude|1") >= 0.95
    # índice 0 = menor media = menor densidad (ρ_CDMX, ADR-005)
    cub2 = cub.copy()
    cub2[:3] = None
    assert all(x is None for x in D.etiquetas_parque_latente(delta, cub2)[:3])
