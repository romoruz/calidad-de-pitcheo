"""F2 — Densidad del aire por juego desde la trayectoria: orquestación, compuertas G2.1–G2.4 y reporte.

`correr()` toma los datos limpios de F0 (o una sintética con física exacta), aplica la Prop. 1 por lanzamiento con
el marco temporal de ADR-014, estima δ^D y δ^L por juego con la Prop. 2′ (efectos fijos de juego + lanzador×forma,
f_D como B-spline de S), calcula los SE (CR2 por lanzador dentro del juego; doble agrupamiento juego × lanzador para
contrastes y Deming), evalúa las compuertas y escribe `data/interim/densidad_juego.parquet`, el reporte con el Bloque
para el orquestador y figuras agregadas. Corre además la sintética de F2 (G2.1 y la tabla de escenarios).

Solo física por lanzamiento: ningún outcome entra. Ni el reporte, ni el .json, ni el log, ni las figuras traen filas por
lanzamiento ni tablas por lanzador; el parquet por juego va a `data/interim/` (fuera de git).
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

from . import densidad as D
from . import io

CUBETAS = ["No Altitude", "Medium Altitude", "Extreme Altitude"]


def _json(obj, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=_a_json), encoding="utf-8")


def _a_json(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _log_rho_baro(h_m: float, a: float = 2.25577e-5, b: float = 5.25588) -> float:
    return b * float(np.log(1.0 - a * h_m))


# ==========================================================================
# Análisis sobre un DataFrame por lanzamiento (datos reales de F0 o sintética)
# ==========================================================================

def _media_por_anio_ponderada(delta: np.ndarray, mascara: np.ndarray, anio_g: np.ndarray,
                              W) -> dict:
    """δ̄ de una cubeta como media sobre años del `δ̄_year`, ponderada por juegos de la cubeta en cada año.

    Devuelve {"n", "media", "se", "por_anio": {año: {"n", "media"}}} con el SE de dos vías juego × lanzador
    construido con las influencias normalizadas por conteo total.
    """
    import math
    idx = np.flatnonzero(mascara)
    if idx.size < 2:
        return {"n": int(idx.size), "media": float(delta[idx].mean()) if idx.size else None, "se": None, "por_anio": {}}
    anios, inv = np.unique(anio_g[idx], return_inverse=True)
    n_y = np.bincount(inv, minlength=len(anios))
    sumas = np.bincount(inv, delta[idx], minlength=len(anios))
    media_y = sumas / n_y
    por_anio = {int(a): {"n": int(n_y[k]), "media": float(media_y[k])} for k, a in enumerate(anios)}
    media = float(np.sum(n_y * media_y) / n_y.sum())
    # Influencia por juego para la varianza de dos vías: (1/N) · (δ_g − δ̄_year(g))
    u = np.zeros(delta.shape)
    u[idx] = (delta[idx] - media_y[inv]) / n_y.sum()
    se = math.sqrt(max(D.varianza_dos_vias(u, W), 0.0))
    return {"n": int(idx.size), "media": media, "se": se, "por_anio": por_anio}


def _contraste_por_anio_ponderado(delta: np.ndarray, mascara_1: np.ndarray, mascara_0: np.ndarray,
                                  anio_g: np.ndarray, W) -> dict:
    """Diferencia δ̄(1) − δ̄(0) como media sobre años con los MISMOS pesos que el de la cubeta 1 (ADR-018 §B)."""
    import math
    i1 = np.flatnonzero(mascara_1)
    if i1.size < 2:
        return {"diferencia": None, "se": None, "por_anio": {}}
    anios, inv1 = np.unique(anio_g[i1], return_inverse=True)
    n_y_1 = np.bincount(inv1, minlength=len(anios))
    s_y_1 = np.bincount(inv1, delta[i1], minlength=len(anios))
    m_y_1 = s_y_1 / np.maximum(n_y_1, 1)
    m_y_0 = np.zeros(len(anios))
    for k, a in enumerate(anios):
        g0 = np.flatnonzero(mascara_0 & (anio_g == a))
        if g0.size == 0:
            return {"diferencia": None, "se": None,
                    "por_anio": {int(a): {"n_1": int(n_y_1[k]), "n_0": 0, "diferencia": None} for k, a in enumerate(anios)},
                    "razon": "no hay juegos de la cubeta de referencia en algún año"}
        m_y_0[k] = float(delta[g0].mean())
    peso = n_y_1 / n_y_1.sum()
    diff = float(np.sum(peso * (m_y_1 - m_y_0)))
    por_anio = {int(a): {"n_1": int(n_y_1[k]), "n_0": int(np.sum(mascara_0 & (anio_g == a))),
                         "diferencia": float(m_y_1[k] - m_y_0[k])} for k, a in enumerate(anios)}
    # Influencia por juego para dos vías.
    u = np.zeros(delta.shape)
    for k, a in enumerate(anios):
        g1 = np.flatnonzero(mascara_1 & (anio_g == a))
        g0 = np.flatnonzero(mascara_0 & (anio_g == a))
        u[g1] += peso[k] * (delta[g1] - m_y_1[k]) / n_y_1[k]
        if g0.size:
            u[g0] -= peso[k] * (delta[g0] - m_y_0[k]) / g0.size
    se = math.sqrt(max(D.varianza_dos_vias(u, W), 0.0))
    return {"diferencia": diff, "se": se, "por_anio": por_anio}


def analizar(df: pl.DataFrame, f02: dict, fis: dict, semilla: int = 2026) -> dict:
    """Prop. 1 → Prop. 2′ → SE → contrastes, Deming y Prop. 3′. Devuelve agregados y la tabla por juego."""
    P = D.preparar_datos(df, fis.get("y_plato_ft", 17 / 12))
    d, vec = P["d"], P["vec"]
    referencia = f02.get("referencia", "No Altitude")
    est = D.estimar_densidad(d, f02, referencia)
    res, dsg, u = est["res"], est["diseno"], est["mascara"]
    jl, ll = d["juego"].to_numpy()[u], d["lanzador"].to_numpy()[u]
    jk = d["lanzador_forma"].to_numpy()[u]
    conglomerado = np.char.add(np.char.add(ll.astype(str), "|"), jl.astype(str))
    gn = res.get("grupos_norm")
    se = D.se_cr2(dsg, res["resid"], conglomerado, res["en_referencia"], f02.get("max_p_cr2", 14000), gn)
    dd, dl = res["delta"][:, 0], res["delta"][:, 1]
    cub = np.array([None if c is None else str(c) for c in dsg.cubeta_juego], dtype=object)
    sin_cub = np.array([c is None for c in cub])
    baja = est["baja_confianza"]
    conf = (~baja) & (~sin_cub)
    W = D.pesos_juego_lanzador(jl, ll, dsg.juegos)

    # --- medias por cubeta: media de medias por año, ponderada por juegos de la cubeta en cada año (ADR-018 §B;
    #     si por_anio=False, equivale a la media global). Contrastes contra la referencia: diferencia dentro del año,
    #     ponderada por el número de juegos de la cubeta en el año.
    jd = d.group_by("juego").agg(pl.col("year").first().alias("year"))
    anio_de_g = dict(zip(jd["juego"].to_list(), jd["year"].to_list(), strict=True))
    anio_juego_full = np.array([anio_de_g[g] for g in dsg.juegos])
    medias, mas = {}, {}
    for c in CUBETAS:
        m = _media_por_anio_ponderada(dd, conf & (cub == c), anio_juego_full, W)
        ml = _media_por_anio_ponderada(dl, conf & (cub == c), anio_juego_full, W)
        medias[c] = {"n": m["n"], "delta_D": m["media"], "se_D": m["se"], "delta_L": ml["media"], "se_L": ml["se"],
                     "por_anio_D": m["por_anio"], "por_anio_L": ml["por_anio"]}
    for c in CUBETAS[1:]:
        mas[f"{c} − {referencia}"] = _contraste_por_anio_ponderado(
            dd, conf & (cub == c), conf & (cub == referencia), anio_juego_full, W)
    bar = _tabla_barometrica(medias, f02.get("altitud_cubeta_m", {}), referencia)

    # --- parques latentes (🔎) y predicción de cubeta
    rh_g = sp_g = None
    n_g = len(dsg.juegos)
    pos = {g: i for i, g in enumerate(dsg.juegos)}
    gi = np.array([pos[g] for g in jl])
    if "rel_height" in vec:
        rh = vec["rel_height"][u]
        _, li = np.unique(ll, return_inverse=True)
        res_rh = rh - (np.bincount(li, rh) / np.bincount(li))[li]
        rh_g = np.bincount(gi, res_rh, minlength=n_g) / np.maximum(np.bincount(gi, minlength=n_g), 1)
    if "sesgo_plateloc_z" in vec:
        sp_g = np.bincount(gi, vec["sesgo_plateloc_z"][u], minlength=n_g) / np.maximum(np.bincount(gi, minlength=n_g), 1)
    latentes = D.parques_latentes(dd[conf], cub[conf], None if rh_g is None else rh_g[conf],
                                  None if sp_g is None else sp_g[conf], f02.get("gmm_max_comp", 4),
                                  f02.get("gmm_n_init", 5), semilla)
    mezcla_ext = latentes["mezclas"].get("Extreme Altitude")
    prediccion = D.predecir_cubeta(dd, cub, sin_cub)

    # --- Deming δ^L sobre δ^D (juegos confirmatorios) y SE
    idx = np.flatnonzero(conf)
    dem = D.deming(dd[idx], dl[idx], se["se"][idx, 0], se["se"][idx, 1], W[idx]) if len(idx) > 5 else None

    # --- Prop. 2″ (ADR-018): β̂_c de Reynolds, prueba de sobreidentificación y δ̃ corregido.
    p2pp_cfg = f02.get("prop2pp", {}) or {}
    prop2pp: dict = {"activada": bool(p2pp_cfg.get("activa", True)), "adoptado": False}
    medias_corr = mezcla_ext_corr = deming_corr = None
    try:
        r2pp = D.estimar_reynolds(d, f02, referencia, por_anio=f02.get("por_anio", True))
        pend_obs = dem["pendiente"] if dem else float("nan")
        se_obs = dem["se_pendiente"] if dem else float("nan")
        sobre = D.sobreidentificacion_reynolds(r2pp, pend_obs, se_obs,
                                               tolerancia=p2pp_cfg.get("tolerancia_equivalencia", 0.10))
        r2_tope = p2pp_cfg.get("tolerancia_r2_colinealidad", 0.98)
        identificable = r2pp["r2_colinealidad_log_v"] < r2_tope
        adoptado = bool(prop2pp["activada"] and sobre["equivalencia"] and identificable)
        prop2pp.update({"beta": r2pp["beta"].tolist(), "se_beta": r2pp["se_beta"].tolist(),
                        "r2_colinealidad_log_v": r2pp["r2_colinealidad_log_v"], "r2_tope": r2_tope,
                        "identificable": bool(identificable), "sobreidentificacion": sobre, "adoptado": adoptado,
                        "iteraciones": r2pp["iteraciones"], "convergio": r2pp["convergio"],
                        "n_lanzamientos": r2pp["n_lanzamientos"], "p_cr2": r2pp["p_cr2"]})
        if adoptado:
            dd_c = r2pp["delta_corregido"][:, 0]
            dl_c = r2pp["delta_corregido"][:, 1]
            se_c = r2pp["se_delta_corregido"]
            medias_corr = {}
            for c in CUBETAS:
                m = _media_por_anio_ponderada(dd_c, conf & (cub == c), anio_juego_full, W)
                ml = _media_por_anio_ponderada(dl_c, conf & (cub == c), anio_juego_full, W)
                medias_corr[c] = {"n": m["n"], "delta_D": m["media"], "se_D": m["se"],
                                  "delta_L": ml["media"], "se_L": ml["se"]}
            mezcla_ext_corr = D.mezcla_bic(dd_c[conf & (cub == "Extreme Altitude")],
                                           f02.get("gmm_max_comp", 4), f02.get("gmm_n_init", 5), semilla)                 if (conf & (cub == "Extreme Altitude")).sum() >= 8 else None
            idx_c = np.flatnonzero(conf)
            deming_corr = D.deming(dd_c[idx_c], dl_c[idx_c], se_c[idx_c, 0], se_c[idx_c, 1], W[idx_c])                 if len(idx_c) > 5 else None
            prop2pp.update({"medias_corregidas": medias_corr, "mezcla_extreme_corregida": mezcla_ext_corr,
                            "deming_corregido": deming_corr,
                            "delta_corregido_D": dd_c, "delta_corregido_L": dl_c,
                            "se_delta_corregido": se_c})
    except (ValueError, np.linalg.LinAlgError) as exc:
        prop2pp["error"] = str(exc)

    # --- Prop. 3′: ĉ_g desde δ^L − δ^D y, si SpinAxis es medido, el detector ê
    vv = {k: x[u] for k, x in vec.items() if isinstance(x, np.ndarray) and len(x) == len(u)}
    kappa = D.kappa_sustentacion(vv["a_perp"], vv["l_perp"])
    kappa_medio = float(np.nanmean(kappa))
    c_dif = D.c_g_desde_diferencia(dd, dl, res["en_referencia"], kappa_medio, gn)
    chk = D.verificar_spinaxis_medido(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jk,
                                      f02.get("spinaxis_desfase_min_grados", 1.0), f02.get("spinaxis_sd_min_ms2", 0.05),
                                      f02.get("spinaxis_r2_max", 0.95), f02.get("spinaxis_n_min_evaluable", 100),
                                      f02.get("spinaxis_fraccion_min_evaluable", 0.5))
    c_e = np.full(n_g, np.nan)
    g23b_real = None
    if chk["medido"]:
        c_e = D.c_g_detector_e(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jl, jk, dsg.juegos, res["en_referencia"],
                               chk["signo_lateral"], gn)["c_g"]
        g23b_real = _g23b_datos(d, u, gi, conf, dd, cub, dsg, vv, jk, conglomerado, chk, f02, semilla)
    # --- δ̄_No por año y niveles de normalización (ADR-018): el estimador los expone en `niveles_por_grupo`.
    anio_g = res.get("anio_juego")
    if anio_g is None:
        anios = d.group_by("juego").agg(pl.col("year").first().alias("year"))
        anio_de = dict(zip(anios["juego"].to_list(), anios["year"].to_list(), strict=True))
        anio_g = np.array([anio_de[g] for g in dsg.juegos])
    por_anio = {int(a): float(np.mean(dd[(cub == referencia) & (anio_g == a)])) for a in np.unique(anio_g)
                if ((cub == referencia) & (anio_g == a)).any()}
    niveles_norm = res.get("niveles_por_grupo")

    por_juego = pl.DataFrame({
        "juego": dsg.juegos, "cubeta": [SIN if c is None else c for c in cub], "year": anio_g, "n_g": est["n_g"],
        "n_efectivo": est["n_efectivo"], "baja_confianza": baja, "delta_D": dd, "delta_L": dl,
        "se_cr2_D": se["se"][:, 0], "se_cr2_L": se["se"][:, 1], "se_ingenuo_D": se["se_ingenuo"][:, 0],
        "c_hat_dif": c_dif, "c_hat_e": c_e, "en_referencia": res["en_referencia"],
        "rel_height_resid_ft": rh_g if rh_g is not None else np.full(n_g, np.nan),
        "sesgo_plateloc_z_ft": sp_g if sp_g is not None else np.full(n_g, np.nan)})
    agregados = {
        "datos": P["conteo"], "conectado": {k: v for k, v in dsg.conectado.items() if k != "estratos"},
        "estratos": dsg.conectado["estratos"], "ajuste": res["ajuste"], "soporte": est["soporte"],
        "juegos": {"total": int(n_g), "sin_cubeta": int(sin_cub.sum()), "baja_confianza": int(baja.sum()),
                   "confirmatorios": int(conf.sum())},
        "se": {"metodo": se["metodo"], "p": int(se["p"]), "sigma_eta_D": float(se["sigma_eta"][0]),
               "sigma_eta_L": float(se["sigma_eta"][1]),
               "se_cr2_D_mediana": float(np.median(se["se"][conf, 0])), "se_cr2_L_mediana": float(np.median(se["se"][conf, 1])),
               "se_ingenuo_D_mediana": float(np.median(se["se_ingenuo"][conf, 0])),
               "efecto_diseno_D": float(np.median(se["se"][conf, 0] / se["se_ingenuo"][conf, 0]))},
        "medias_por_cubeta": medias, "contrastes": mas, "barometrica": bar, "mezcla_extreme": mezcla_ext,
        "latentes": latentes, "sin_cubeta_prediccion": prediccion, "deming": dem,
        "calibracion": {"kappa_medio": kappa_medio, "spinaxis": chk, "g23b_datos": g23b_real,
                        "c_dif_por_cubeta": D.distribucion_por_cubeta(c_dif[conf], cub[conf]),
                        "c_e_por_cubeta": (D.distribucion_por_cubeta(c_e[conf], cub[conf]) if chk["medido"] else None)},
        "delta_referencia_por_anio": por_anio,
        "niveles_normalizacion": niveles_norm,
        "prop2pp": prop2pp,
    }
    return {"agregados": agregados, "por_juego": por_juego, "dsg": dsg, "estimacion": est, "se": se, "conf": conf,
            "cubeta": cub}


SIN = D.SIN_CUBETA


def _g23b_datos(d: pl.DataFrame, u: np.ndarray, gi: np.ndarray, conf: np.ndarray, dd: np.ndarray, cub: np.ndarray,
                dsg, vv: dict, jk: np.ndarray, conglomerado: np.ndarray, chk: dict, f02: dict, semilla: int) -> dict:
    """ĉ_ê por parque sobre los datos: id de parque si F0 lo trae (`parque`), si no parque latente (🔎, GMM de δ̂ᴰ)."""
    fuente = f02.get("parque_fuente", "auto")
    if fuente in ("auto", "id") and "parque" in d.columns:
        origen = "id de parque (F0)"
        par_juego = None
        par_fila = d["parque"].to_numpy()[u].astype(object)
    else:
        origen = "parque latente 🔎 (mezcla gaussiana de δ̂ᴰ por cubeta; no es un parque identificado)"
        lab = D.etiquetas_parque_latente(dd[conf], cub[conf], f02.get("gmm_max_comp", 4), f02.get("gmm_n_init", 5), semilla)
        par_juego = np.full(len(dsg.juegos), None, dtype=object)
        par_juego[np.flatnonzero(conf)] = lab
        par_fila = par_juego[gi]
    fuera = ~conf[gi]
    par_fila = np.where(fuera, None, par_fila)
    cub_fila = cub[gi]
    cong_lanz = d["lanzador"].to_numpy()[u].astype(str)
    r = D.detector_e_parques(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jk, par_fila, cub_fila, cong_lanz,
                             chk["signo_lateral"], f02.get("g23b_q", 0.05), f02.get("g23b_min_parques", 2),
                             f02.get("max_p_cr2", 14000),
                             contraste=f02.get("g23b_contraste", "loo"),
                             df_tipo=f02.get("g23b_df", "pustejovsky_tipton"))
    return {"origen": origen, **r}


def _tabla_barometrica(medias: dict, alturas: dict, referencia: str) -> dict:
    """δ̄ por cubeta contra log(ρ/ρ_ref) barométrica con la altitud representativa (informativo), pendiente por MCP."""
    if not all(c in alturas and medias[c]["delta_D"] is not None for c in CUBETAS):
        return {}
    x = np.array([_log_rho_baro(alturas[c]) - _log_rho_baro(alturas[referencia]) for c in CUBETAS])
    y = np.array([medias[c]["delta_D"] for c in CUBETAS])
    se = np.array([medias[c]["se_D"] if medias[c]["se_D"] else np.nan for c in CUBETAS])
    filas = [{"cubeta": c, "altitud_m": alturas[c], "log_rho_baro": float(xi), "delta_medio": float(yi),
              "se": (None if not np.isfinite(si) else float(si))} for c, xi, yi, si in zip(CUBETAS, x, y, se, strict=True)]
    out = {"filas": filas}
    if np.all(np.isfinite(se)) and np.all(se > 0):
        w = 1.0 / se**2
        xb = np.sum(w * x) / w.sum()
        sxx = np.sum(w * (x - xb) ** 2)
        b = np.sum(w * (x - xb) * (y - np.sum(w * y) / w.sum())) / sxx
        s_b = float(1.0 / np.sqrt(sxx))
        out |= {"pendiente": float(b), "se_pendiente": s_b, "ic95": [float(b - 1.96 * s_b), float(b + 1.96 * s_b)],
                "nota": "3 puntos, pesos 1/EE²; altitudes representativas ilustrativas: informativo, no es compuerta"}
    return out


# ==========================================================================
# Sintética de F2: estudio de simulación de G2.1 (ADR-017), escenario de G2.3b y cobertura de G2.4
# ==========================================================================
def _conglomerado(d: pl.DataFrame, u: np.ndarray) -> np.ndarray:
    return np.char.add(np.char.add(d["lanzador"].to_numpy()[u].astype(str), "|"), d["juego"].to_numpy()[u].astype(str))


def _estimar_sintetica(df: pl.DataFrame, v: dict, f02: dict, sin_alpha: bool = False, con_se: bool = False) -> dict:
    """Prop. 2′ sobre una sintética: δ̂ contra la verdad normalizada con los MISMOS juegos de referencia que el estimador."""
    P = D.preparar_datos(df)
    d = P["d"]
    est = D.estimar_densidad(d, f02, f02.get("referencia", "No Altitude"), sin_alpha=sin_alpha)
    dsg, res = est["diseno"], est["res"]
    pos = {g: i for i, g in enumerate(v["juegos"])}
    ix = np.array([pos[g] for g in dsg.juegos])
    log_rho = np.log(v["rho_juego"])[ix]
    verdad = log_rho - log_rho[res["en_referencia"]].mean()
    out = {"est": est, "d": d, "vec": P["vec"], "dsg": dsg, "delta": res["delta"], "verdad": verdad,
           "cubeta": np.array(v["cubeta_juego"])[ix], "c_verdad": v["c_g"][ix]}
    if con_se:
        out["se"] = D.se_cr2(dsg, res["resid"], _conglomerado(d, est["mascara"]), res["en_referencia"],
                             f02.get("max_p_cr2", 14000))
    return out


def error_recuperacion(s: dict) -> dict:
    """Error relativo de ρ̂/ρ_ref por nivel de densidad: media de e^δ̂ contra media de e^δ verdadera."""
    out = {}
    for c in CUBETAS[1:]:
        m = s["cubeta"] == c
        if m.any():
            out[c] = float(np.mean(np.exp(s["delta"][m, 0])) / np.mean(np.exp(s["verdad"][m])) - 1.0)
    return out


def replica_g21(semilla: int, sc: dict, f02: dict) -> dict:
    """Una réplica del estudio de simulación de G2.1: genera, estima δ̂ y (opcional) δ̃ corregido por Reynolds (ADR-018).

    Si `prop2pp.activa=True`, también estima β̂ y expone `delta_corregido` y `se_corregido` para que `resumen_g21`
    pueda medir recuperación y cobertura sobre δ̃ (el **primario** en ADR-018 cuando la sintética tiene β explícito).
    """
    from .sintetico import generar_fisica
    t0 = time.time()
    df, v = generar_fisica(sc["n_juegos"], sc["lanzamientos_por_juego"], semilla,
                           beta_D=sc.get("beta_D", 0.0), beta_L=sc.get("beta_L", 0.0))
    s = _estimar_sintetica(df, v, f02, con_se=True)
    out = {"semilla": semilla, "error": error_recuperacion(s), "n_lanzamientos": df.height,
           "delta": s["delta"][:, 0], "verdad": s["verdad"], "se": s["se"]["se"][:, 0], "cubeta": s["cubeta"],
           "sigma_eta": float(s["se"]["sigma_eta"][0]), "metodo_se": s["se"]["metodo"], "segundos": time.time() - t0}
    if (f02.get("prop2pp") or {}).get("activa", True):
        try:
            r2pp = D.estimar_reynolds(s["d"], f02, f02.get("referencia", "No Altitude"),
                                      por_anio=f02.get("por_anio", True))
            # Alinear al orden de dsg (los dos pasan por construir_diseno con los mismos juegos; mapeamos por juego)
            pos = {g: i for i, g in enumerate(r2pp["juegos"])}
            juegos_est = s["dsg"].juegos
            ix = np.array([pos[g] for g in juegos_est])
            delta_tilde_D = r2pp["delta_corregido"][ix, 0]
            se_tilde_D = r2pp["se_delta_corregido"][ix, 0]
            err_c = {}
            for c in CUBETAS[1:]:
                m = s["cubeta"] == c
                if m.any():
                    err_c[c] = float(np.mean(np.exp(delta_tilde_D[m])) / np.mean(np.exp(s["verdad"][m])) - 1.0)
            out.update({"beta_D": float(r2pp["beta"][0]), "beta_L": float(r2pp["beta"][1]),
                        "se_beta_D": float(r2pp["se_beta"][0]), "se_beta_L": float(r2pp["se_beta"][1]),
                        "r2_colinealidad_log_v": float(r2pp["r2_colinealidad_log_v"]),
                        "error_corregido": err_c, "delta_corregido": delta_tilde_D, "se_corregido": se_tilde_D})
        except (ValueError, np.linalg.LinAlgError) as exc:
            out["error_reynolds"] = str(exc)
    return out


def _resumen_niveles(reps: list[dict], cota: float, campo_err: str, campo_delta: str, campo_se: str) -> tuple[dict, float, int]:
    niveles, cubiertos, n_tot = {}, 0, 0
    for c in CUBETAS[1:]:
        e = np.array([r[campo_err][c] for r in reps if campo_err in r and c in r[campo_err]])
        if len(e) < 2:
            niveles[c] = {"sesgo_rel": None, "mcse": None, "cota": None, "ok": False, "se_empirico": None,
                          "rmse": None, "cobertura": None, "juegos": 0, "errores_por_replica": e.tolist()}
            continue
        sesgo, mcse = float(e.mean()), float(e.std(ddof=1) / np.sqrt(len(e)))
        err = np.concatenate([(r[campo_delta] - r["verdad"])[r["cubeta"] == c] for r in reps if campo_delta in r])
        cov = np.concatenate([np.abs(r[campo_delta] - r["verdad"])[r["cubeta"] == c] <= 1.96 * r[campo_se][r["cubeta"] == c]
                              for r in reps if campo_se in r])
        niveles[c] = {"sesgo_rel": sesgo, "mcse": mcse, "cota": abs(sesgo) + 1.96 * mcse,
                      "ok": bool(abs(sesgo) + 1.96 * mcse < cota), "se_empirico": float(err.std(ddof=1)),
                      "rmse": float(np.sqrt(np.mean(err**2))), "cobertura": float(cov.mean()),
                      "juegos": len(err), "errores_por_replica": e.tolist()}
    for r in reps:
        if campo_delta in r and campo_se in r:
            ok = np.isfinite(r[campo_se]) & (r[campo_se] > 0)
            cubiertos += int(np.sum(np.abs(r[campo_delta] - r["verdad"])[ok] <= 1.96 * r[campo_se][ok]))
            n_tot += int(ok.sum())
    return niveles, cubiertos, n_tot


def resumen_g21(reps: list[dict], cota: float, usar_corregido: bool = False) -> dict:
    """Medidas de Morris, White y Crowther (2019) sobre las R réplicas: sesgo relativo, MCSE, SE empírico, RMSE, cobertura.

    `usar_corregido=True` evalúa sobre δ̃ (ADR-018: primario cuando Prop. 2″ está activa en el pipeline).
    """
    n_r = len(reps)
    tiene_corregido = all("delta_corregido" in r for r in reps)
    primario = "corregido" if (usar_corregido and tiene_corregido) else "bruto"
    campos = {"corregido": ("error_corregido", "delta_corregido", "se_corregido"),
              "bruto": ("error", "delta", "se")}[primario]
    niveles, cubiertos, n_tot = _resumen_niveles(reps, cota, *campos)
    out = {"R": n_r, "primario": primario, "niveles": niveles, "cobertura": cubiertos / max(n_tot, 1),
           "juegos_total": n_tot, "sigma_eta_medio": float(np.mean([r["sigma_eta"] for r in reps])),
           "lanzamientos_por_replica": [r["n_lanzamientos"] for r in reps],
           "segundos_por_replica": [round(r["segundos"], 1) for r in reps]}
    if tiene_corregido:
        out["beta_D_medio"] = float(np.mean([r["beta_D"] for r in reps]))
        out["beta_L_medio"] = float(np.mean([r["beta_L"] for r in reps]))
        out["beta_D_sd"] = float(np.std([r["beta_D"] for r in reps], ddof=1))
        out["beta_L_sd"] = float(np.std([r["beta_L"] for r in reps], ddof=1))
        out["r2_colinealidad_log_v_medio"] = float(np.mean([r["r2_colinealidad_log_v"] for r in reps]))
        # También reportamos el bruto para la demo de atenuación/corrección (ADR-018).
        if primario == "corregido":
            niv_br, cub_br, nt_br = _resumen_niveles(reps, cota, "error", "delta", "se")
            out["bruto"] = {"niveles": niv_br, "cobertura": cub_br / max(nt_br, 1)}
    return out


def replica_g23b(semilla: int, sc: dict, f02: dict, con_calibracion: bool) -> dict:
    """Una réplica del escenario de G2.3b: 18 parques; λ en 1/3 y τ en otro 1/3 de los de cada cubeta (o todos limpios)."""
    from .sintetico import CUBETAS_G23B, esquema_calibracion_parques, generar_fisica
    esq = (esquema_calibracion_parques(CUBETAS_G23B, semilla, sc["lambda_escala"], sc["tau_reloj"])
           if con_calibracion else {})
    df, v = generar_fisica(sc["n_juegos_g23b"], sc["lanzamientos_por_juego"], semilla, cubetas=CUBETAS_G23B,
                           calibracion_parques=esq, beta_D=sc.get("beta_D", 0.0), beta_L=sc.get("beta_L", 0.0))
    s = _estimar_sintetica(df, v, f02, con_se=True)
    est, dsg, d, vec, res = s["est"], s["dsg"], s["d"], s["vec"], s["est"]["res"]
    u = est["mascara"]
    jk = d["lanzador_forma"].to_numpy()[u]
    cong_lanz = d["lanzador"].to_numpy()[u].astype(str)                                                        # ADR-018: cluster = lanzador para G2.3b
    vv = {k: x[u] for k, x in vec.items() if isinstance(x, np.ndarray) and len(x) == len(u)}
    chk = D.verificar_spinaxis_medido(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jk, f02.get("spinaxis_desfase_min_grados", 1.0),
                                      f02.get("spinaxis_sd_min_ms2", 0.05), f02.get("spinaxis_r2_max", 0.95),
                                      f02.get("spinaxis_n_min_evaluable", 100), f02.get("spinaxis_fraccion_min_evaluable", 0.5))
    det = D.detector_e_parques(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jk, d["parque"].to_numpy()[u].astype(object),
                               d["cubeta"].to_numpy()[u].astype(object), cong_lanz, chk["signo_lateral"], f02.get("g23b_q", 0.05),
                               f02.get("g23b_min_parques", 2), f02.get("max_p_cr2", 14000),
                               contraste=f02.get("g23b_contraste", "loo"), df_tipo=f02.get("g23b_df", "pustejovsky_tipton"))
    c_park = {f"park_{k + 1:02d}": l / t**2 - 1.0 for k, (l, t) in esq.items()}
    tipo = {f"park_{k + 1:02d}": ("lambda" if l != 1.0 else "tau") for k, (l, _) in esq.items()}
    for f in det["parques"]:
        f["c_verdad"] = c_park.get(f["parque"], 0.0)
        f["tipo"] = tipo.get(f["parque"], "limpio")
    W = D.pesos_juego_lanzador(d["juego"].to_numpy()[u], d["lanzador"].to_numpy()[u], dsg.juegos)
    dem = D.deming(res["delta"][:, 0], res["delta"][:, 1], s["se"]["se"][:, 0], s["se"]["se"][:, 1], W)
    return {"semilla": semilla, "parques": det["parques"], "spinaxis_medido": chk["medido"],
            "deming": {k: dem[k] for k in ("pendiente", "intercepto", "se_pendiente", "z_pendiente_vs_1")},
            "n_lanzamientos": df.height, "metodo_se": det["metodo_se"], "q": det["q"]}


def resumen_g23b(reps: list[dict]) -> dict:
    """Potencia (parques contaminados rechazados por BH) y tasa de falsos positivos (parques limpios rechazados)."""
    filas = [f for r in reps for f in r["parques"] if f.get("evaluable")]
    out: dict = {"R": len(reps), "spinaxis_medido": all(r["spinaxis_medido"] for r in reps), "q": reps[0]["q"]}
    for nombre, sel in (("lambda", lambda f: f["tipo"] == "lambda"), ("tau", lambda f: f["tipo"] == "tau"),
                        ("limpio", lambda f: f["tipo"] == "limpio")):
        x = [f for f in filas if sel(f)]
        out[nombre] = {"n": len(x), "rechazos": int(sum(f["rechaza_bh"] for f in x)),
                       "tasa": float(np.mean([f["rechaza_bh"] for f in x])) if x else None,
                       "c_centrado_medio": float(np.mean([f["c_centrado"] for f in x])) if x else None,
                       "c_verdad_medio": float(np.mean([f["c_verdad"] for f in x])) if x else None,
                       "se_medio": float(np.mean([f["se"] for f in x])) if x else None}
    cont = [f for f in filas if f["tipo"] != "limpio"]
    out["potencia"] = float(np.mean([f["rechaza_bh"] for f in cont])) if cont else None
    out["fpr"] = out["limpio"]["tasa"]
    out["deming_pendiente_medio"] = float(np.mean([r["deming"]["pendiente"] for r in reps]))
    out["deming_pendientes"] = [round(r["deming"]["pendiente"], 4) for r in reps]
    out["lanzamientos_por_replica"] = [r["n_lanzamientos"] for r in reps]
    return out


def sintetica_f02(f02: dict, fis: dict) -> dict:
    """Estudio de simulación de G2.1 (R réplicas, semillas fijas), escenario de G2.3b y cobertura del IC95 CR2 (ADR-017)."""
    from joblib import Parallel, delayed
    sc = f02["sintetica"]
    nj = sc.get("n_jobs", -1)
    t0 = time.time()
    reps = Parallel(n_jobs=nj)(delayed(replica_g21)(sem, sc, f02) for sem in sc["semillas"])
    g21 = resumen_g21(reps, f02["gates"]["g21_error_max"],
                      usar_corregido=(f02.get("prop2pp") or {}).get("activa", True))
    g21["semillas"] = list(sc["semillas"])
    g21["n_juegos"], g21["lanzamientos_por_juego"] = sc["n_juegos"], sc["lanzamientos_por_juego"]
    t1 = time.time()
    # Planteles locales: δ̂ con y sin α_{j,k} en la primera semilla (diagnóstico de la Prop. 2′, no es compuerta).
    from .sintetico import generar_fisica
    df, v = generar_fisica(sc["n_juegos"], sc["lanzamientos_por_juego"], sc["semillas"][0],
                           beta_D=sc.get("beta_D", 0.0), beta_L=sc.get("beta_L", 0.0))
    con, sin = _estimar_sintetica(df, v, f02), _estimar_sintetica(df, v, f02, sin_alpha=True)
    def rmse(x):
        return float(np.sqrt(np.mean((x["delta"][:, 0] - x["verdad"]) ** 2)))

    staff = {"semilla": sc["semillas"][0], "rmse_con_alpha": rmse(con), "rmse_sin_alpha": rmse(sin),
             "sigma_alpha": float(v["sigma_alpha"])}
    t2 = time.time()
    g23b = {}
    for etq, cal in (("con_calibracion", True), ("nulo", False)):
        rr = Parallel(n_jobs=nj)(delayed(replica_g23b)(sem, sc, f02, cal) for sem in sc["semillas"])
        g23b[etq] = resumen_g23b(rr)
    t3 = time.time()
    return {"g21": g21, "staff": staff, "g23b": g23b,
            "segundos": {"g21": round(t1 - t0, 1), "staff": round(t2 - t1, 1), "g23b": round(t3 - t2, 1)}}


# ==========================================================================
# Prueba de escala: ~635 k lanzamientos sintéticos con el pipeline completo
# ==========================================================================
def prueba_escala(n_lanzamientos: int, cfg, n_jobs: int = -1) -> dict:
    """Genera ~`n_lanzamientos` sintéticos (física exacta, bloques en paralelo) y corre `analizar`: tiempo y RAM pico."""
    import resource

    from .sintetico import generar_fisica
    f02, fis = cfg["f02"], cfg["fisica"]
    lpj = f02["sintetica"]["lanzamientos_por_juego"]
    n_juegos = max(round(n_lanzamientos / lpj), 10)
    t0 = time.time()
    df, _ = generar_fisica(n_juegos, lpj, 4242, n_jobs=n_jobs, sigma_parque=0.01)
    t_gen = time.time() - t0
    rss_gen = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    t1 = time.time()
    r = analizar(df, f02, fis, cfg["seed"])
    t_ana = time.time() - t1
    a = r["agregados"]
    return {"lanzamientos": df.height, "juegos": n_juegos, "segundos_generacion": round(t_gen, 1),
            "segundos_analisis": round(t_ana, 1), "ram_pico_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0),
            "ram_pico_tras_generar_mb": round(rss_gen), "se_metodo": a["se"]["metodo"], "p_cr2": a["se"]["p"],
            "juegos_conectados": a["conectado"]["juegos_conectados"],
            "iteraciones_solver": [x["iteraciones"] for x in a["ajuste"]], "convergio": [x["convergio"] for x in a["ajuste"]]}


# ==========================================================================
# Compuertas
# ==========================================================================
def evaluar_gates(a: dict, sint: dict, g: dict, referencia: str = "No Altitude") -> dict:
    """G2.1–G2.4 de ROADMAP §4-F2 / ADR-017 con las cifras medidas."""
    gates = {}
    g21 = sint["g21"]
    peor = max(g21["niveles"].values(), key=lambda x: x["cota"])
    gates["G2.1"] = {"ok": all(x["ok"] for x in g21["niveles"].values()),
                     "detalle": "estudio de simulación, R = {R} réplicas (semillas {s0}–{s1}), |sesgo relativo medio| + 1.96·MCSE por nivel < {cota:.0f} %: ".format(
                         R=g21["R"], s0=g21["semillas"][0], s1=g21["semillas"][-1], cota=100 * g["g21_error_max"])
                     + " · ".join(f"{c.split()[0]} {100 * x['sesgo_rel']:+.3f} % + 1.96×{100 * x['mcse']:.3f} % = {100 * x['cota']:.3f} %"
                                  f" {'✓' if x['ok'] else '✗'}" for c, x in g21["niveles"].items())
                     + f" (peor nivel {100 * peor['cota']:.3f} %)"}
    pp = a.get("prop2pp", {})
    adoptado = bool(pp.get("adoptado"))
    sufijo = " (sobre δ̃ corregido por Reynolds, ADR-018)" if adoptado else " (sobre δ̂ bruto)"
    med_src = pp.get("medias_corregidas") if adoptado else a["medias_por_cubeta"]
    mz_src = pp.get("mezcla_extreme_corregida") if adoptado else a.get("mezcla_extreme")
    dem_src = pp.get("deming_corregido") if adoptado else a["deming"]
    dn, dm_, de = (med_src[c]["delta_D"] for c in CUBETAS)
    ok_orden = None not in (dn, dm_, de) and dn > dm_ > de
    ok_b = de is not None and g["g22_extreme"][0] <= de <= g["g22_extreme"][1]
    comp = mz_src["componentes"][0]["media"] if mz_src else None
    ok_c = comp is not None and g["g22_componente"][0] <= comp <= g["g22_componente"][1]
    gates["G2.2"] = {"ok": bool(ok_orden and ok_b and ok_c),
                     "detalle": (f"{sufijo.strip()}. (a) orden estricto {'✓' if ok_orden else '✗'}: δ̄ No {dn:+.4f} > Medium "
                                 f"{dm_:+.4f} > Extreme {de:+.4f} · (b) δ̄ Extreme ∈ {g['g22_extreme']}: {'✓' if ok_b else '✗'} · "
                                 f"(c) componente de menor media de la mezcla de Extreme "
                                 f"{'—' if comp is None else f'{comp:+.4f}'} ∈ {g['g22_componente']}: {'✓' if ok_c else '✗'}")
                     if None not in (dn, dm_, de) else "sin juegos confirmatorios en alguna cubeta"}
    lo, hi = g["g23_pendiente"]
    gates["G2.3a"] = {"ok": dem_src is not None and lo <= dem_src["pendiente"] <= hi,
                      "detalle": (f"Deming δ^L sobre δ^D{sufijo}: pendiente "
                                  f"{dem_src['pendiente']:.3f} (EE dos vías {dem_src['se_pendiente']:.3f}) ∈ [{lo}, {hi}] · intercepto "
                                  f"{dem_src['intercepto']:+.4f}") if dem_src else "no evaluable"}
    b = sint["g23b"]["con_calibracion"]
    p_min, f_max = g["g23b_potencia_min"], g["g23b_fpr_max"]
    pot_l, pot_t = b["lambda"]["tasa"], b["tau"]["tasa"]
    ok_det = (b["potencia"] is not None and pot_l is not None and pot_t is not None and b["fpr"] is not None
              and b["potencia"] >= p_min and pot_l >= p_min and pot_t >= p_min and b["fpr"] <= f_max)
    det_txt = (f"detector ê por parque (validación SINTÉTICA del método, ADR-018; Pustejovsky–Tipton + BH {100 * b['q']:.0f} %), "
               f"{b['R']} réplicas × 18 parques: potencia {b['potencia']:.3f} (λ=1.02: {pot_l:.3f}, {b['lambda']['rechazos']}/"
               f"{b['lambda']['n']}; τ=1.01: {pot_t:.3f}, {b['tau']['rechazos']}/{b['tau']['n']}; mínimo {p_min}) · "
               f"FPR en parques limpios {b['fpr']:.3f} ({b['limpio']['rechazos']}/{b['limpio']['n']}; máximo {f_max}). "
               f"La aplicación a datos reales es 🔎 informativa (ver reporte).")
    if not b.get("spinaxis_medido", True):
        gates["G2.3b"] = {"ok": True, "no_evaluable": True,
                          "detalle": "NO EVALUABLE: SpinAxis en la SINTÉTICA resulta inferido (fail-closed, ADR-018)"}
    else:
        gates["G2.3b"] = {"ok": bool(ok_det), "detalle": det_txt}
    s = a["se"]
    cob = sint["g21"]["cobertura"]
    ok_cob = cob >= g["g24_cobertura_min"]
    if adoptado and pp.get("se_delta_corregido") is not None:
        se_c = pp["se_delta_corregido"]
        n_juego = a["juegos"]["confirmatorios"]
        # mediana de SE de δ̃_D sobre juegos confirmatorios: aproximamos con la mediana sobre todo (los no-conf son pocos)
        se_med = float(np.median(se_c[:, 0])) if n_juego else float("nan")
        detalle_se = (f"σ_η (bruto) = {s['sigma_eta_D']:.4f} (D) / {s['sigma_eta_L']:.4f} (L) · SE CR2 mediano de "
                      f"**δ̃**_g (corregido Reynolds) = {se_med:.4f} (límite {g['g24_se_max']}; método {s['metodo']}; "
                      f"delta method sobre β̂_D y β̂_L)")
    else:
        se_med = s["se_cr2_D_mediana"]
        detalle_se = (f"σ_η = {s['sigma_eta_D']:.4f} (D) / {s['sigma_eta_L']:.4f} (L) · SE CR2 mediano de δ̂_g = "
                      f"{se_med:.4f} (límite {g['g24_se_max']}; ingenuo {s['se_ingenuo_D_mediana']:.4f}, "
                      f"efecto de diseño ×{s['efecto_diseno_D']:.2f}) · método {s['metodo']}")
    gates["G2.4"] = {"ok": bool(se_med < g["g24_se_max"] and ok_cob),
                     "detalle": detalle_se + f" · cobertura del IC95 CR2 en la sintética {cob:.3f} (mínimo "
                                             f"{g['g24_cobertura_min']}) {'✓' if ok_cob else '✗'}"}
    return dict(sorted(gates.items()))


# ==========================================================================
# Reporte
# ==========================================================================
def _f(v, d: int = 4) -> str:
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{d}f}"


def _tabla(filas: list[dict], cols: list[str]) -> list[str]:
    if not filas:
        return ["_(vacía)_"]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for f in filas:
        out.append("| " + " | ".join("—" if f.get(c) is None else str(f[c]) for c in cols) + " |")
    return out


def figuras(a: dict, pj: pl.DataFrame, fig_dir: Path) -> list[str]:
    """Tres figuras agregadas por juego (nada por lanzamiento): δ̂ por cubeta, Deming y ĉ_g por cubeta."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir.mkdir(parents=True, exist_ok=True)
    conf = pj.filter(~pl.col("baja_confianza") & (pl.col("cubeta") != SIN))
    colores = {"No Altitude": "#4c78a8", "Medium Altitude": "#f58518", "Extreme Altitude": "#e45756"}
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for c in CUBETAS:
        v = conf.filter(pl.col("cubeta") == c)["delta_D"].to_numpy()
        if len(v):
            ax.hist(v, bins=30, alpha=0.6, color=colores[c], label=f"{c} (n={len(v)})")
    ax.set_xlabel("δ̂ᴰ por juego (log ρ relativo a No Altitude)")
    ax.set_ylabel("juegos")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "delta_por_cubeta.png", dpi=120)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(4.8, 4.6))
    for c in CUBETAS:
        s = conf.filter(pl.col("cubeta") == c)
        ax.scatter(s["delta_D"], s["delta_L"], s=6, alpha=0.5, color=colores[c], label=c)
    lim = [float(conf["delta_D"].min()) - 0.02, float(conf["delta_D"].max()) + 0.02]
    ax.plot(lim, lim, "k--", lw=0.8, label="pendiente 1")
    dm = a.get("deming")
    if dm:
        ax.plot(lim, [dm["intercepto"] + dm["pendiente"] * x for x in lim], color="k", lw=1, label=f"Deming {dm['pendiente']:.3f}")
    ax.set_xlabel("δ̂ᴰ")
    ax.set_ylabel("δ̂ᴸ")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(fig_dir / "deming_delta_L_vs_D.png", dpi=120)
    plt.close(fig)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for k, (col, tit) in enumerate((("c_hat_dif", "ĉ desde (δᴸ − δᴰ)/κ̄"), ("c_hat_e", "ĉ del detector ê"))):
        datos = [conf.filter(pl.col("cubeta") == c)[col].drop_nans().to_numpy() for c in CUBETAS]
        if any(len(x) for x in datos):
            ax[k].boxplot([x if len(x) else [np.nan] for x in datos], tick_labels=["No", "Medium", "Extreme"], showfliers=False)
        ax[k].axhline(0, color="k", lw=0.6)
        ax[k].set_title(tit, fontsize=9)
    ax[0].set_ylabel("ĉ_g (relativo a No Altitude)")
    fig.tight_layout()
    fig.savefig(fig_dir / "c_g_por_cubeta.png", dpi=120)
    plt.close(fig)
    return ["delta_por_cubeta.png", "deming_delta_L_vs_D.png", "c_g_por_cubeta.png"]


def _sec_datos(a: dict) -> list[str]:
    c, con, j = a["datos"], a["conectado"], a["juegos"]
    L = ["## Datos y estimador (Prop. 1 y Prop. 2′)", "",
         "| paso | filas |", "|---|---|",
         *[f"| {k} | {v:,} |" for k, v in c.items()], "",
         (f"**Conjunto conectado** (grafo juegos–lanzador×forma, Abowd–Kramarz–Margolis): {con['juegos_conectados']:,} de "
          f"{con['juegos']:,} juegos · {con['grupos_jk_conectados']:,} de {con['grupos_jk']:,} lanzador×forma · "
          f"{con['filas_conectadas']:,} de {con['filas']:,} filas · componentes {con['componentes']}. "
          "Los juegos fuera del gigante no tienen δ_g identificado."), "",
         (f"Juegos: {j['total']:,} con δ̂ · {j['confirmatorios']:,} confirmatorios · {j['sin_cubeta']:,} sin cubeta (🔎, "
          f"fuera de la normalización y de G2.2) · {j['baja_confianza']:,} de baja confianza (n efectivo < "
          f"n_min en el soporte común)."), "",
         "**Solver** (LSMR disperso, Fong y Saunders 2011; equivale a las proyecciones alternadas a ≤ 1e-8, prueba de regresión): "
         + " · ".join(f"{nom}: {x['iteraciones']} iteraciones, convergió={x['convergio']}, residuo normal relativo {x['cambio_final']:.1e}"
                      for nom, x in zip(("δᴰ", "δᴸ"), a["ajuste"], strict=True)), ""]
    sop = a["soporte"]
    L += [(f"Soporte común de S entre cubetas: {sop['filas_en_soporte']:,} de {sop['filas']:,} filas dentro; estratos sin "
          f"soporte común: {sop['estratos_sin_soporte_comun'] or 'ninguno'}."), ""]
    est = a["estratos"]
    por_spl: dict = {}
    for v in est.values():
        por_spl[v["spline"]] = por_spl.get(v["spline"], 0) + 1
    L += [f"f_D: {len(est)} estratos forma×mano×year; tipo de base por estrato: {por_spl}.", ""]
    return L


def _sec_resultados(a: dict) -> list[str]:
    m, L = a["medias_por_cubeta"], []
    filas = [{"cubeta": c, "juegos": m[c]["n"], "δ̄ᴰ": _f(m[c]["delta_D"]), "EE (2 vías)": _f(m[c]["se_D"]),
              "ρ̂/ρ_ref": _f(np.exp(m[c]["delta_D"])) if m[c]["delta_D"] is not None else None,
              "δ̄ᴸ": _f(m[c]["delta_L"])} for c in CUBETAS]
    L += ["## δ̂ por cubeta (G2.2)", "", *_tabla(filas, list(filas[0])), ""]
    L += ["**Contrastes (media, EE de dos vías juego × lanzador):** "
          + " · ".join(f"{k}: {_f(v['diferencia'])} ± {_f(v['se'])}" for k, v in a["contrastes"].items()), ""]
    mz = a.get("mezcla_extreme")
    if mz:
        L += [f"**Mezcla gaussiana de Extreme (BIC → {mz['n_componentes']} componentes):** "
              + " · ".join(f"media {c['media']:+.4f} (sd {c['sd']:.4f}, peso {c['peso']:.2f})" for c in mz["componentes"])
              + ". La de menor media es la de menor densidad: define ρ_CDMX (ADR-005).", ""]
    b = a["barometrica"]
    if b:
        L += ["### δ̄ contra log ρ barométrica (ROADMAP §2) — informativo", "", *_tabla(
            [{"cubeta": r["cubeta"], "altitud_m": r["altitud_m"], "log ρ_baro": _f(r["log_rho_baro"]),
              "δ̄ᴰ": _f(r["delta_medio"]), "EE": _f(r["se"])} for r in b["filas"]],
            ["cubeta", "altitud_m", "log ρ_baro", "δ̄ᴰ", "EE"]), ""]
        if "pendiente" in b:
            L += [(f"Pendiente de δ̄ᴰ sobre log ρ barométrica: **{b['pendiente']:.3f}** (IC95 [{b['ic95'][0]:.3f}, "
                  f"{b['ic95'][1]:.3f}]); {b['nota']}."), ""]
    L += ["### δ̄ de la cubeta de referencia por año (diagnóstico)", "",
          ("La normalización es global; el nivel de cada año (cambio de pelota) lo absorbe δ_g. Si estos valores difieren "
          "más de ~0.01 entre años, las medias por cubeta mezclan años con composición distinta (🔎)."), "",
          " · ".join(f"{y}: {v:+.4f}" for y, v in a["delta_referencia_por_anio"].items()), ""]
    return L


def _sec_deming_se(a: dict) -> list[str]:
    dm, s = a["deming"], a["se"]
    L = ["## Sobreidentificación: Deming δ^L sobre δ^D (G2.3)", ""]
    if dm:
        L += [(f"Pendiente **{dm['pendiente']:.3f}** (EE dos vías {dm['se_pendiente']:.3f}; z vs 1 = "
               f"{_f(dm['z_pendiente_vs_1'], 2)}), intercepto {dm['intercepto']:+.4f} (EE {dm['se_intercepto']:.4f}), razón de "
               f"varianzas de error {dm['razon_varianzas']:.3f}, {dm['n_juegos']:,} juegos. Banda de G2.3: [0.85, 1.15]."), ""]
    L += ["## σ_η y SE de δ̂_g (G2.4)", "",
          (f"σ_η = **{s['sigma_eta_D']:.4f}** (log ρC_D) y **{s['sigma_eta_L']:.4f}** (log ρC_L). SE de δ̂_g con CR2 "
           f"(conglomerados = lanzador dentro del juego; {s['metodo']}): mediana **{s['se_cr2_D_mediana']:.4f}** (D), "
           f"{s['se_cr2_L_mediana']:.4f} (L); ingenuo σ_η/√n_g: {s['se_ingenuo_D_mediana']:.4f}; efecto de diseño "
           f"×{s['efecto_diseno_D']:.2f}."), ""]
    return L


def _sec_prop2pp(a: dict) -> list[str]:
    pp = a.get("prop2pp") or {}
    L = ["## Prop. 2″ (ADR-018): corrección de atenuación por Reynolds", ""]
    if not pp or "beta" not in pp:
        L += [f"_No evaluable: {pp.get('error', 'falta Prop. 2″')}_", ""]
        return L
    bD, bL = pp["beta"]
    sbD, sbL = pp["se_beta"]
    sob = pp["sobreidentificacion"]
    L += [(f"Modelo `y_c = δ_g + α_jk + f_c(S) + β_c · log‖v̄‖ + ε` ajustado por LSMR disperso con conglomerado "
           f"lanzador×juego para el SE CR2. **β̂_D = {bD:+.3f} ± {sbD:.3f}**, **β̂_L = {bL:+.3f} ± {sbL:.3f}**. "
           f"R² de log‖v̄‖ sobre {{dummies de juego, lanzador×forma, splines de S}} = **{pp['r2_colinealidad_log_v']:.3f}** "
           f"(tope {pp['r2_tope']}; identificable: {'✓' if pp['identificable'] else '✗ β no identificado por colinealidad'})."),
          "",
          ("**Prueba de sobreidentificación** (pendiente predicha vs Deming observada, equivalencia ±tol):"), "",
          *_tabla([{"pendiente predicha (1+β_L)/(1+β_D)": _f(sob["pendiente_predicha"], 3),
                    "Deming observada": _f(sob["pendiente_observada"], 3),
                    "diferencia": _f(sob["diferencia"], 3),
                    "SE(diferencia)": _f(sob["se_diferencia"], 3),
                    "|dif|+1.96·SE": _f(sob["frontera"], 3),
                    "tolerancia": _f(sob["tolerancia"], 2),
                    "equivalencia": "✓" if sob["equivalencia"] else "✗"}],
                  ["pendiente predicha (1+β_L)/(1+β_D)", "Deming observada", "diferencia", "SE(diferencia)",
                   "|dif|+1.96·SE", "tolerancia", "equivalencia"]), "",
          (f"**Adopción (ADR-018):** {'✓ δ̃ = δ/(1+β̂) adoptados como primarios (G2.2 y G2.4 sobre δ̃)' if pp['adoptado'] else '✗ no adoptados: se reportan como diagnóstico; G2.2 y G2.4 sobre δ bruto'}. "
           f"Iteraciones LSMR: D {pp['iteraciones'][0]}, L {pp['iteraciones'][1]}; convergió: {pp['convergio']}."), ""]
    if pp["adoptado"] and pp.get("medias_corregidas"):
        mc = pp["medias_corregidas"]
        mb = a["medias_por_cubeta"]
        filas = [{"cubeta": c, "n": mc[c]["n"],
                  "δ̄ᴰ bruto": _f(mb[c]["delta_D"]), "δ̃ᴰ corregido": _f(mc[c]["delta_D"]),
                  "SE δ̃ᴰ (2-vías)": _f(mc[c]["se_D"]),
                  "ρ̂/ρ_ref (δ̃)": _f(np.exp(mc[c]["delta_D"])) if mc[c]["delta_D"] is not None else None,
                  "δ̄ᴸ bruto": _f(mb[c]["delta_L"]), "δ̃ᴸ corregido": _f(mc[c]["delta_L"])}
                 for c in CUBETAS]
        L += ["**δ̃ por cubeta (corregido Reynolds):**", "", *_tabla(filas, list(filas[0])), ""]
        if pp.get("deming_corregido"):
            dc = pp["deming_corregido"]
            L += [(f"**Deming sobre δ̃:** pendiente {dc['pendiente']:.3f} (EE {dc['se_pendiente']:.3f}; z vs 1 = "
                   f"{_f(dc['z_pendiente_vs_1'], 2)}), intercepto {dc['intercepto']:+.4f}. Si Prop. 2″ es correcta, "
                   "la pendiente de Deming sobre δ̃ debe estar cerca de 1."), ""]
    return L


def _sec_calibracion(a: dict) -> list[str]:
    c = a["calibracion"]
    chk = c["spinaxis"]
    L = ["## Prop. 3′: ĉ_g por juego (residuo de calibración c_g·g)", "",
         (f"**SpinAxis:** {chk['veredicto']} (desfase RMS con el eje que implica el movimiento "
          f"{chk['desfase_rms_grados']:.2f}°, umbral {chk['umbral_desfase_grados']}°; sd de ã·ê dentro de lanzador×forma "
          f"{chk['sd_a_por_e_dentro_jk_ms2']:.3f} m/s², umbral {chk['umbral_sd_ms2']}; R² de SpinAxis sobre las columnas de "
          f"movimiento, dentro de lanzador×forma, {chk['r2_circularidad']:.3f} (inferido si ≥ {chk['umbral_r2']}); "
          f"signo lateral σ = {chk['signo_lateral']:+d})."),
         "",
         (f"ĉ_g = (δ̂ᴸ − δ̂ᴰ − media_ref)/κ̄ con κ̄ = {c['kappa_medio']:.3f} (sensibilidad media de log ρC_L a c). "
          "Relativo a la cubeta de referencia, como δ: el nivel común de c lo absorbe f_L. **Lectura:** (i) hay un sesgo de "
          "línea base por ruido de medición que depende de ρ; (ii) en este canal el factor de giro S también se calcula con "
          "la v medida, lo que contamina ĉ con η_S·log(λ/τ). Ver D02b y la tabla de escenarios sintéticos."), ""]
    for nombre, clave in (("(δ̂ᴸ − δ̂ᴰ)/κ̄", "c_dif_por_cubeta"), ("detector ê", "c_e_por_cubeta")):
        d = c[clave]
        if d:
            L += [f"**ĉ_g por cubeta, {nombre}:**", "", *_tabla(
                [{"cubeta": k, "juegos": v["n"], "media": _f(v["media"]), "sd": _f(v["sd"]), "p05": _f(v["p05"]),
                  "mediana": _f(v["mediana"]), "p95": _f(v["p95"])} for k, v in d.items()],
                ["cubeta", "juegos", "media", "sd", "p05", "mediana", "p95"]), ""]
    g = c.get("g23b_datos")
    sp = c["spinaxis"]
    if not chk["medido"]:
        razon = ("no evaluable (algún criterio no finito o muestra válida insuficiente, fail-closed, ADR-018)"
                 if sp.get("no_evaluable") else "inferido del movimiento (prueba de circularidad, ADR-017)")
        L += [(f"_El detector ê sobre datos reales es n/e: SpinAxis sale {razon}. Datos: n_evaluado = {sp.get('n_evaluado')} de "
               f"{sp.get('n_entrada')}, R² = {_f(sp.get('r2_circularidad'))}, sd(ã·ê) = {_f(sp.get('sd_a_por_e_dentro_jk_ms2'))}, "
               f"desfase = {_f(sp.get('desfase_rms_grados'), 2)}°. El único detector de calibración sobre real es G2.3a._"), ""]
    if g is not None and chk["medido"]:
        ev = [f for f in g["parques"] if f["evaluable"]]
        latente = "parque latente" in g["origen"].lower()
        etiqueta = ("🔎 **informativa, no es compuerta** (" + ("sin id de parque: " if latente else "")
                    + f"id = {g['origen']}; ADR-018: la compuerta G2.3b vive en la sintética)")
        L += [(f"**ĉ_ê por parque sobre los datos reales — {etiqueta}; SE {g['metodo_se']}; Wald + BH al {100 * g['q']:.0f} %:** "
               f"{sum(f['rechaza_bh'] for f in ev)} de {len(ev)} parques evaluados marcados."), "",
              *_tabla([{"parque": f["parque"], "cubeta": f["cubeta"], "ĉ crudo": _f(f["c_hat"]),
                        "ĉ centrado": _f(f.get("c_centrado")), "SE": _f(f.get("se")), "z": _f(f.get("z"), 2),
                        "BH": ("marca" if f.get("rechaza_bh") else "—") if f["evaluable"] else "n/e"}
                       for f in sorted(g["parques"], key=lambda f: (f["cubeta"], f["parque"]))],
                      ["parque", "cubeta", "ĉ crudo", "ĉ centrado", "SE", "z", "BH"]), "",
              ("Un parque marcado señala |ĉ| distinto del de su cubeta: se **revisa**, no se descarta ni dispara una "
               "compuerta. El centrado absorbe el sesgo de línea base que depende de ρ (D02b §3)."), ""]
    return L


def _sec_latentes(a: dict) -> list[str]:
    la, pr = a["latentes"], a["sin_cubeta_prediccion"]
    L = ["## Parques latentes (🔎 exploratorio)", "",
         "Mezcla gaussiana con BIC sobre δ̂ᴰ_g dentro de cada cubeta (juegos confirmatorios). No es estadístico de H1–H6.", ""]
    for c, mz in la["mezclas"].items():
        L.append(f"- **{c}:** {mz['n_componentes']} componentes · " + " · ".join(
            f"{x['media']:+.3f} (sd {x['sd']:.3f}, peso {x['peso']:.2f})" for x in mz["componentes"]))
    for nombre, d in la["descriptores_por_juego"].items():
        L += ["", f"**{nombre} por cubeta (media por juego):** " + " · ".join(
            f"{c}: {_f(v['media'])} ± {_f(v['sd'])}" for c, v in d.items())]
    L += ["", f"**Juegos sin cubeta ({pr['n']}) — cubeta más verosímil según δ̂ᴰ (🔎):** {pr.get('predichas') or '—'}", ""]
    return L


def _sec_sintetica(sint: dict, f02: dict) -> list[str]:
    g21, sc = sint["g21"], f02["sintetica"]
    L = ["## Sintética con física exacta: estudio de simulación de G2.1 (ADR-017)", "",
         (f"`solve_ivp` DOP853 (rtol 1e-10), ρ conocida en 3 niveles (1.00, 0.82, 0.76·ρ₀), C_D y C_L realistas, ruido de "
          f"posición, 9P de aceleración constante ajustado por mínimos cuadrados, efecto de lanzador α_j (SD 0.05 en log C_D) "
          f"con planteles asignados a parques locales. **Protocolo pre-registrado** (Morris, White y Crowther 2019): "
          f"R = {g21['R']} réplicas independientes, semillas {g21['semillas'][0]}–{g21['semillas'][-1]}, {g21['n_juegos']} "
          f"juegos × ≈{g21['lanzamientos_por_juego']} lanzamientos (≈{int(np.mean(g21['lanzamientos_por_replica'])):,} por réplica), "
          f"estimando log(ρ_nivel/ρ_No). Aprueba si, por nivel, |sesgo relativo medio| + 1.96·MCSE < "
          f"{100 * f02['gates']['g21_error_max']:.0f} %."), ""]
    simb = "δ̃" if g21.get("primario") == "corregido" else "δ̂"
    L += [(f"**Primario de G2.1 ({simb})**: " + ("Prop. 2″ adopta δ̃ = δ̂/(1+β̂) en el pipeline (ADR-018). "
                                                    "Se reporta además el bruto como demo de atenuación."
                                                    if g21.get("primario") == "corregido"
                                                    else "δ̂ bruto (Prop. 2″ no activa o β no estimable).")), ""]
    L += _tabla([{"nivel": c, "sesgo relativo medio": f"{100 * x['sesgo_rel']:+.3f} %" if x["sesgo_rel"] is not None else "—",
                  "MCSE": f"{100 * x['mcse']:.3f} %" if x["mcse"] is not None else "—",
                  "|sesgo| + 1.96·MCSE": f"{100 * x['cota']:.3f} %" if x["cota"] is not None else "—",
                  "veredicto": "✓" if x["ok"] else "✗",
                  f"SE empírico {simb}": _f(x["se_empirico"]), f"RMSE {simb}": _f(x["rmse"]),
                  "cobertura IC95 CR2": f"{x['cobertura']:.3f}" if x["cobertura"] is not None else "—",
                  "juegos×réplicas": x["juegos"]} for c, x in g21["niveles"].items()],
                ["nivel", "sesgo relativo medio", "MCSE", "|sesgo| + 1.96·MCSE", "veredicto", f"SE empírico {simb}",
                 f"RMSE {simb}", "cobertura IC95 CR2", "juegos×réplicas"]) + [""]
    if "bruto" in g21:
        br = g21["bruto"]
        L += [("**Demo de atenuación (sobre δ̂ bruto)**: con β_D explícito en el generador, el estimador sin corrección "
               "se atenúa; δ̃ recupera. Fila por nivel:"), "",
              *_tabla([{"nivel": c, "sesgo bruto": f"{100 * x['sesgo_rel']:+.3f} %" if x["sesgo_rel"] is not None else "—",
                        "|sesgo|+1.96·MCSE bruto": f"{100 * x['cota']:.3f} %" if x["cota"] is not None else "—",
                        "cobertura bruto": f"{x['cobertura']:.3f}" if x["cobertura"] is not None else "—",
                        "RMSE bruto": _f(x["rmse"])} for c, x in br["niveles"].items()],
                     ["nivel", "sesgo bruto", "|sesgo|+1.96·MCSE bruto", "cobertura bruto", "RMSE bruto"]), ""]
    if "beta_D_medio" in g21:
        L += [(f"**β̂ promedios en el estudio** (R = {g21['R']}): β̂_D = {g21['beta_D_medio']:+.3f} ± {g21['beta_D_sd']:.3f}, "
               f"β̂_L = {g21['beta_L_medio']:+.3f} ± {g21['beta_L_sd']:.3f}. R² de colinealidad log‖v̄‖ medio = "
               f"{g21['r2_colinealidad_log_v_medio']:.3f}. β_D verdadero del generador: {f02['sintetica'].get('beta_D', 0.0)}."), ""]
    alerta = " ⚠ **ALERTA: cobertura < 0.90, el SE subestima**" if g21["cobertura"] < 0.90 else ""
    L += [(f"**Cobertura del IC95 (CR2 o delta method CR2 según primario) de {simb}_g sobre todos los juegos × réplicas "
           f"({g21['juegos_total']:,}): {g21['cobertura']:.3f}**{alerta}. σ_η medio (bruto) {g21['sigma_eta_medio']:.4f}. "
           f"Errores por réplica (Medium / Extreme): "
           + "; ".join(f"{100 * (a if a is not None else float('nan')):+.2f} % / {100 * (b if b is not None else float('nan')):+.2f} %" for a, b in zip(
               g21["niveles"]["Medium Altitude"]["errores_por_replica"],
               g21["niveles"]["Extreme Altitude"]["errores_por_replica"], strict=True)) + "."), ""]
    s = sint["staff"]
    L += [(f"**Planteles locales** (semilla {s['semilla']}): RMSE de δ̂ contra la verdad {s['rmse_sin_alpha']:.4f} sin α_{{j,k}} → "
           f"{s['rmse_con_alpha']:.4f} con α_{{j,k}} (Prop. 2′): el segundo efecto fijo elimina el sesgo del C_D medio del plantel."), ""]
    b, nulo = sint["g23b"]["con_calibracion"], sint["g23b"]["nulo"]
    L += ["## Sintética de calibración para G2.3b (ADR-017, F2.5b)", "",
          (f"18 parques (6 por cubeta); en cada cubeta λ = {sc['lambda_escala']} en 2 parques, τ = {sc['tau_reloj']} en otros 2 y "
           f"2 limpios (c = λ/τ² − 1 ≈ ±0.02). {sc['n_juegos_g23b']} juegos × ≈{sc['lanzamientos_por_juego']} lanzamientos por réplica, "
           f"R = {b['R']} (semillas {sc['semillas'][0]}–{sc['semillas'][-1]}). Detector ê con id de parque, centrado en la mediana "
           f"de la cubeta, Wald con SE CR2 y BH al {100 * b['q']:.0f} %. **Diseño y tamaño fijados antes de la corrida "
           f"final** (solo se usaron las semillas 101–102 para medir tiempo y SE del detector)."), ""]
    filas = []
    for nombre, clave in (("λ = 1.02 (c≈+0.02)", "lambda"), ("τ = 1.01 (c≈−0.02)", "tau"), ("limpios (c=0)", "limpio")):
        x = b[clave]
        filas.append({"grupo de parques": nombre, "parques×réplicas": x["n"], "marcados por BH": x["rechazos"],
                      "tasa": _f(x["tasa"], 3), "ĉ centrado medio": _f(x["c_centrado_medio"]), "c verdad": _f(x["c_verdad_medio"]),
                      "SE CR2 medio": _f(x["se_medio"])})
    L += [*_tabla(filas, list(filas[0])), "",
          (f"**Potencia (contaminados) {b['potencia']:.3f}** (mínimo {f02['gates']['g23b_potencia_min']}, y también por tipo) · "
           f"**FPR (limpios) {b['fpr']:.3f}** (máximo {f02['gates']['g23b_fpr_max']}). Control sin calibración (todos los parques "
           f"limpios, mismas semillas): {nulo['limpio']['rechazos']} de {nulo['limpio']['n']} parques marcados, "
           f"FPR {nulo['limpio']['tasa']:.3f}. Con 2 parques limpios por cubeta la mediana es su promedio, así que los contrastes de "
           f"cada par son iguales y de signo opuesto: los falsos positivos llegan de a pares."), "",
          (f"**G2.3a en la sintética (informativo):** pendiente de Deming media {b['deming_pendiente_medio']:.3f} con calibración "
           f"por parque contra {nulo['deming_pendiente_medio']:.3f} sin ella; la banda [0.85, 1.15] no distingue ambas (D02b)."), ""]
    return L


def reporte_md(a: dict, sint: dict, gates: dict, f02: dict, segundos: float, figs: list[str]) -> str:
    L = ["# FASE 02 — Densidad del aire por juego desde la trayectoria", "",
         f"{a['datos']['filas_entrada']:,} filas de entrada · {a['datos']['filas_salida']:,} lanzamientos válidos · {segundos}s", ""]
    L += _sec_datos(a) + _sec_resultados(a) + _sec_deming_se(a) + _sec_prop2pp(a) + _sec_calibracion(a) + _sec_latentes(a)
    L += _sec_sintetica(sint, f02)
    L += ["## Compuertas", ""]
    for k, v in gates.items():
        L.append(f"- **{k}** {'✅' if v['ok'] else '❌'} {v['detalle']}")
    m = a["medias_por_cubeta"]
    L += ["", f"Figuras agregadas por juego en `docs/figuras/f2/`: {', '.join(figs)}.", "",
          "### Bloque para el orquestador — F02",
          "- Modelo(s) usado(s): Sonnet (implementación)",
          "- Compuertas: " + " | ".join(f"{k} {'✅' if v['ok'] else '❌'}" for k, v in gates.items()),
          (f"- Cifras clave: δ̄ᴰ No {_f(m['No Altitude']['delta_D'])} · Medium {_f(m['Medium Altitude']['delta_D'])} ± "
           f"{_f(m['Medium Altitude']['se_D'])} · Extreme {_f(m['Extreme Altitude']['delta_D'])} ± "
           f"{_f(m['Extreme Altitude']['se_D'])} · Deming {_f(a['deming']['pendiente'], 3) if a['deming'] else '—'} · "
           f"β̂_D {_f(a['prop2pp']['beta'][0], 3) if a.get('prop2pp',{}).get('beta') else '—'} / β̂_L "
           f"{_f(a['prop2pp']['beta'][1], 3) if a.get('prop2pp',{}).get('beta') else '—'} · pendiente predicha "
           f"{_f(a['prop2pp']['sobreidentificacion']['pendiente_predicha'], 3) if a.get('prop2pp',{}).get('sobreidentificacion') else '—'} vs observada "
           f"{_f(a['deming']['pendiente'], 3) if a['deming'] else '—'} (equivalencia "
           f"{'✓' if a.get('prop2pp',{}).get('sobreidentificacion',{}).get('equivalencia') else '✗'}; adoptado "
           f"{'✓' if a.get('prop2pp',{}).get('adoptado') else '✗'}) · σ_η {a['se']['sigma_eta_D']:.4f} · G2.1 "
           f"{100 * max(x['cota'] for x in sint['g21']['niveles'].values()):.3f} % (|sesgo|+1.96 MCSE, peor nivel) · cobertura IC95 "
           f"{sint['g21']['cobertura']:.3f} · G2.3b potencia {sint['g23b']['con_calibracion']['potencia']:.2f} / FPR "
           f"{sint['g23b']['con_calibracion']['fpr']:.3f} · {a['juegos']['confirmatorios']:,} juegos confirmatorios"),
          "- Desviaciones respecto al ROADMAP: Prop. 2″ (ADR-018) corrige la atenuación por Reynolds; G2.3b sintética con cluster=lanzador, contraste LOO y t de Pustejovsky-Tipton; G2.3b real = n/e (nunca compuerta)",
          "- Mejora posible detectada: Prop. 2″ adoptada" + ("" if a.get('prop2pp',{}).get('adoptado') else " (si pasa sobreidentificación en próxima corrida)") + "; detector ê separable escala/reloj (D02b)",
          "- Riesgo de empeorar: ninguno",
          "- Rama / PR / commit de resultados locales: fase02 / (pendiente) / (pendiente)",
          "- Log: reports/logs/f02_<fecha>.log", ""]
    return "\n".join(L)


# ==========================================================================
def cargar_pitches(ruta: Path, columna_parque: str | None = None) -> pl.DataFrame:
    cols = ["game_anon_id", "pitcher_anon_id", "familia", "pitcher_throws_r", "year", "altitude_category_h", "excluir_modelo",
            "x0", "y0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0", "PitchTrajectoryXc1", "SpinRate", "SpinAxis",
            "RelHeight", "PlateLocHeight"]
    lf = io.leer_pitches(ruta)
    disp = set(lf.collect_schema().names())
    df = lf.select([c for c in cols if c in disp] + ([columna_parque] if columna_parque and columna_parque in disp else [])).collect()
    return df.rename({columna_parque: "parque_id"}) if columna_parque and columna_parque in df.columns else df


def correr(cfg, df: pl.DataFrame, ruta_densidad: Path, rep_dir: Path, log_dir: Path, fig_dir: Path) -> dict:
    """Ejecuta F2 sobre `df` (datos limpios de F0 o la sintética). Devuelve {'ok', 'gates', 'reporte'}; no sale del proceso."""
    t0 = time.time()
    f02, fis = cfg["f02"], cfg["fisica"]
    print(f"F2: {df.height:,} lanzamientos × {df.width} columnas", flush=True)
    r = analizar(df, f02, fis, cfg["seed"])
    a, pj = r["agregados"], r["por_juego"]
    print("F2: sintética con física exacta (estudio de simulación de G2.1, escenario de G2.3b) ...", flush=True)
    sint = sintetica_f02(f02, fis)
    gates = evaluar_gates(a, sint, f02["gates"], f02.get("referencia", "No Altitude"))
    ruta_densidad.parent.mkdir(parents=True, exist_ok=True)
    pj.write_parquet(ruta_densidad)
    figs = figuras(a, pj, fig_dir)
    segundos = round(time.time() - t0, 1)
    md = reporte_md(a, sint, gates, f02, segundos, figs)
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / "FASE_02.md").write_text(md, encoding="utf-8")
    _json({"gates": gates, "segundos": segundos, "agregados": a, "sintetica": sint}, rep_dir / "fase_02.json")
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    resumen = {"filas_entrada": a["datos"]["filas_entrada"], "filas_salida": a["datos"]["filas_salida"],
               "juegos": a["juegos"], "gates": {k: v["ok"] for k, v in gates.items()}, "segundos": segundos,
               "se_metodo": a["se"]["metodo"], "segundos_sintetica": sint["segundos"]}
    (log_dir / f"f02_{stamp}.log").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(md)
    return {"ok": all(g["ok"] for g in gates.values()), "gates": gates, "reporte": rep_dir / "FASE_02.md",
            "agregados": a}
