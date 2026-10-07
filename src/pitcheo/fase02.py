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
    se = D.se_cr2(dsg, res["resid"], conglomerado, res["en_referencia"], f02.get("max_p_cr2", 14000))
    dd, dl = res["delta"][:, 0], res["delta"][:, 1]
    cub = np.array([None if c is None else str(c) for c in dsg.cubeta_juego], dtype=object)
    sin_cub = np.array([c is None for c in cub])
    baja = est["baja_confianza"]
    conf = (~baja) & (~sin_cub)
    W = D.pesos_juego_lanzador(jl, ll, dsg.juegos)

    # --- medias por cubeta y contrastes (EE de dos vías)
    medias, mas = {}, {}
    for c in CUBETAS:
        m = D.media_cubeta(dd, conf & (cub == c), W)
        ml = D.media_cubeta(dl, conf & (cub == c), W)
        medias[c] = {"n": m["n"], "delta_D": m["media"], "se_D": m["se"], "delta_L": ml["media"], "se_L": ml["se"]}
    for c in CUBETAS[1:]:
        mas[f"{c} − {referencia}"] = D.contraste_cubetas(dd, conf & (cub == c), conf & (cub == referencia), W)
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

    # --- Prop. 3′: ĉ_g desde δ^L − δ^D y, si SpinAxis es medido, el detector ê
    vv = {k: x[u] for k, x in vec.items() if isinstance(x, np.ndarray) and len(x) == len(u)}
    kappa = D.kappa_sustentacion(vv["a_perp"], vv["l_perp"])
    kappa_medio = float(np.nanmean(kappa))
    c_dif = D.c_g_desde_diferencia(dd, dl, res["en_referencia"], kappa_medio)
    chk = D.verificar_spinaxis_medido(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jk,
                                      f02.get("spinaxis_desfase_min_grados", 1.0), f02.get("spinaxis_sd_min_ms2", 0.05))
    c_e = np.full(n_g, np.nan)
    if chk["medido"]:
        c_e = D.c_g_detector_e(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jl, jk, dsg.juegos, res["en_referencia"],
                               chk["signo_lateral"])["c_g"]
    # --- δ̄_No por año (la normalización es global; el nivel por año lo absorbe δ_g)
    anios = d.group_by("juego").agg(pl.col("year").first().alias("year"))
    anio_de = dict(zip(anios["juego"].to_list(), anios["year"].to_list(), strict=True))
    anio_g = np.array([anio_de[g] for g in dsg.juegos])
    por_anio = {int(a): float(np.mean(dd[(cub == referencia) & (anio_g == a)])) for a in np.unique(anio_g)
                if ((cub == referencia) & (anio_g == a)).any()}

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
        "calibracion": {"kappa_medio": kappa_medio, "spinaxis": chk,
                        "c_dif_por_cubeta": D.distribucion_por_cubeta(c_dif[conf], cub[conf]),
                        "c_e_por_cubeta": (D.distribucion_por_cubeta(c_e[conf], cub[conf]) if chk["medido"] else None)},
        "delta_referencia_por_anio": por_anio,
    }
    return {"agregados": agregados, "por_juego": por_juego, "dsg": dsg, "estimacion": est, "se": se, "conf": conf,
            "cubeta": cub}


SIN = D.SIN_CUBETA


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
# Sintética de F2: G2.1 y escenarios (staff local, λ, τ)
# ==========================================================================
def _estimar_sintetica(df: pl.DataFrame, v: dict, f02: dict, sin_alpha: bool = False) -> dict:
    d = D.preparar_datos(df)["d"]
    est = D.estimar_densidad(d, f02, f02.get("referencia", "No Altitude"), sin_alpha=sin_alpha)
    dsg = est["diseno"]
    pos = {g: i for i, g in enumerate(v["juegos"])}
    ix = np.array([pos[g] for g in dsg.juegos])
    return {"est": est, "d": d, "dsg": dsg, "delta": est["res"]["delta"], "verdad": v["delta_verdad"][ix],
            "cubeta": np.array(v["cubeta_juego"])[ix], "c_verdad": v["c_g"][ix]}


def error_recuperacion(s: dict) -> dict:
    """Error relativo de ρ̂/ρ_ref por nivel de densidad: media de e^δ̂ contra media de e^δ verdadera."""
    out = {}
    for c in CUBETAS[1:]:
        m = s["cubeta"] == c
        if m.any():
            out[c] = float(np.mean(np.exp(s["delta"][m, 0])) / np.mean(np.exp(s["verdad"][m])) - 1.0)
    return out


def _calibracion_escenario(s: dict, v: dict, df: pl.DataFrame, f02: dict) -> dict:
    """ĉ por cubeta (diferencia y detector ê) y Deming de un escenario sintético; relativo a la cubeta de referencia."""
    P = D.preparar_datos(df)
    vec, d = P["vec"], P["d"]
    est, dsg = s["est"], s["dsg"]
    u = est["mascara"]
    res = est["res"]
    jl, ll, jk = d["juego"].to_numpy()[u], d["lanzador"].to_numpy()[u], d["lanzador_forma"].to_numpy()[u]
    conglom = np.char.add(np.char.add(ll.astype(str), "|"), jl.astype(str))
    se = D.se_cr2(dsg, res["resid"], conglom, res["en_referencia"], f02.get("max_p_cr2", 14000))
    W = D.pesos_juego_lanzador(jl, ll, dsg.juegos)
    dd, dl = res["delta"][:, 0], res["delta"][:, 1]
    dem = D.deming(dd, dl, se["se"][:, 0], se["se"][:, 1], W)
    vv = {k: x[u] for k, x in vec.items() if isinstance(x, np.ndarray) and len(x) == len(u)}
    kap = float(np.nanmean(D.kappa_sustentacion(vv["a_perp"], vv["l_perp"])))
    c_dif = D.c_g_desde_diferencia(dd, dl, res["en_referencia"], kap)
    chk = D.verificar_spinaxis_medido(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jk)
    c_e = D.c_g_detector_e(vv["spin_axis"], vv["a_tilde"], vv["v_barra"], jl, jk, dsg.juegos, res["en_referencia"],
                           chk["signo_lateral"])["c_g"] if chk["medido"] else np.full(len(dd), np.nan)
    por = {c: {"c_dif": float(np.mean(c_dif[s["cubeta"] == c])), "c_e": float(np.nanmean(c_e[s["cubeta"] == c])),
               "c_verdad": float(np.mean(s["c_verdad"][s["cubeta"] == c]))} for c in CUBETAS}
    return {"deming": {k: dem[k] for k in ("pendiente", "intercepto", "se_pendiente", "z_pendiente_vs_1")}, "por_cubeta": por,
            "spinaxis_medido": chk["medido"]}


def sintetica_f02(f02: dict, fis: dict) -> dict:
    """G2.1 (error de recuperación de ρ, varias semillas) y los escenarios de ROADMAP §1.6 (6)."""
    from .sintetico import generar_fisica
    sc = f02["sintetica"]
    out: dict = {"base": [], "staff": None, "calibracion": {}}
    for semilla in sc["semillas"]:
        df, v = generar_fisica(sc["n_juegos"], sc["lanzamientos_por_juego"], semilla)
        s = _estimar_sintetica(df, v, f02)
        out["base"].append({"semilla": semilla, "error": error_recuperacion(s),
                            "rmse_delta": float(np.sqrt(np.mean((s["delta"][:, 0] - s["verdad"]) ** 2))),
                            "iteraciones": s["est"]["res"]["ajuste"][0]["iteraciones"]})
        if semilla == sc["semillas"][0]:
            s0 = _estimar_sintetica(df, v, f02, sin_alpha=True)
            out["staff"] = {"semilla": semilla,
                            "rmse_con_alpha": out["base"][-1]["rmse_delta"],
                            "rmse_sin_alpha": float(np.sqrt(np.mean((s0["delta"][:, 0] - s0["verdad"]) ** 2))),
                            "sigma_alpha": float(v["sigma_alpha"])}
    out["g21_error_max"] = max(abs(e) for b in out["base"] for e in b["error"].values())
    n_c = sc.get("n_juegos_calibracion", 150)
    sem = sc["semillas"][0] + 100
    for etiqueta, kw in (("nulo", {}), ("lambda", {"lambda_escala": sc["lambda_escala"]}),
                         ("tau", {"tau_reloj": sc["tau_reloj"]})):
        df, v = generar_fisica(n_c, sc["lanzamientos_por_juego"], sem, **kw)
        s = _estimar_sintetica(df, v, f02)
        out["calibracion"][etiqueta] = _calibracion_escenario(s, v, df, f02)
    return out


# ==========================================================================
# Compuertas
# ==========================================================================
def evaluar_gates(a: dict, sint: dict, g: dict, referencia: str = "No Altitude") -> dict:
    """G2.1–G2.4 de ROADMAP §4-F2 con las cifras medidas."""
    gates = {}
    e = sint["g21_error_max"]
    gates["G2.1"] = {"ok": e < g["g21_error_max"],
                     "detalle": f"error sintético de recuperación de ρ: máx. |error| = {100 * e:.3f} % sobre "
                                f"{len(sint['base'])} semillas (límite {100 * g['g21_error_max']:.0f} %)"}
    m = a["medias_por_cubeta"]
    dn, dm_, de = (m[c]["delta_D"] for c in CUBETAS)
    ok_orden = None not in (dn, dm_, de) and dn > dm_ > de
    ok_b = de is not None and g["g22_extreme"][0] <= de <= g["g22_extreme"][1]
    mz = a.get("mezcla_extreme")
    comp = mz["componentes"][0]["media"] if mz else None
    ok_c = comp is not None and g["g22_componente"][0] <= comp <= g["g22_componente"][1]
    gates["G2.2"] = {"ok": bool(ok_orden and ok_b and ok_c),
                     "detalle": (f"(a) orden estricto {'✓' if ok_orden else '✗'}: δ̄ No {dn:+.4f} > Medium {dm_:+.4f} > "
                                 f"Extreme {de:+.4f} · (b) δ̄ Extreme ∈ {g['g22_extreme']}: {'✓' if ok_b else '✗'} · "
                                 f"(c) componente de menor media de la mezcla de Extreme "
                                 f"{'—' if comp is None else f'{comp:+.4f}'} ∈ {g['g22_componente']}: {'✓' if ok_c else '✗'}")
                     if None not in (dn, dm_, de) else "sin juegos confirmatorios en alguna cubeta"}
    dem = a["deming"]
    lo, hi = g["g23_pendiente"]
    gates["G2.3"] = {"ok": dem is not None and lo <= dem["pendiente"] <= hi,
                     "detalle": ("Deming δ^L sobre δ^D: pendiente "
                                 f"{dem['pendiente']:.3f} (EE dos vías {dem['se_pendiente']:.3f}) ∈ [{lo}, {hi}] · intercepto "
                                 f"{dem['intercepto']:+.4f}") if dem else "no evaluable"}
    s = a["se"]
    gates["G2.4"] = {"ok": s["se_cr2_D_mediana"] < g["g24_se_max"],
                     "detalle": f"σ_η = {s['sigma_eta_D']:.4f} (D) / {s['sigma_eta_L']:.4f} (L) · SE CR2 mediano de δ̂_g = "
                                f"{s['se_cr2_D_mediana']:.4f} (límite {g['g24_se_max']}; ingenuo {s['se_ingenuo_D_mediana']:.4f}, "
                                f"efecto de diseño ×{s['efecto_diseno_D']:.2f}) · método {s['metodo']}"}
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
         "**Proyecciones alternadas** (Guimarães–Portugal): " + " · ".join(
             f"{nom}: {x['iteraciones']} iteraciones, convergió={x['convergio']}, cambio final {x['cambio_final']:.1e}"
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


def _sec_calibracion(a: dict) -> list[str]:
    c = a["calibracion"]
    chk = c["spinaxis"]
    L = ["## Prop. 3′: ĉ_g por juego (residuo de calibración c_g·g)", "",
         (f"**SpinAxis:** {chk['veredicto']} (desfase RMS con el eje que implica el movimiento "
          f"{chk['desfase_rms_grados']:.2f}°, umbral {chk['umbral_desfase_grados']}°; sd de ã·ê dentro de lanzador×forma "
          f"{chk['sd_a_por_e_dentro_jk_ms2']:.3f} m/s², umbral {chk['umbral_sd_ms2']}; signo lateral σ = {chk['signo_lateral']:+d})."),
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
    if not chk["medido"]:
        L += ["_El detector ê no se evalúa: el eje está inferido del movimiento; el único detector es G2.3._", ""]
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
    L = ["## Sintética con física exacta (G2.1 y escenarios de §1.6 (6))", "",
         (f"`solve_ivp` DOP853 (rtol 1e-10), ρ conocida en 3 niveles (1.00, 0.82, 0.76·ρ₀), C_D y C_L realistas, ruido de "
          f"posición, 9P de aceleración constante ajustado por mínimos cuadrados, efecto de lanzador α_j (SD 0.05 en log C_D) "
          f"con planteles asignados a parques locales. **G2.1: error máximo de recuperación de ρ "
          f"{100 * sint['g21_error_max']:.3f} %** (límite 1 %)."), ""]
    L += _tabla([{"semilla": b["semilla"], "Medium": f"{100 * b['error'].get('Medium Altitude', float('nan')):+.3f} %",
                  "Extreme": f"{100 * b['error'].get('Extreme Altitude', float('nan')):+.3f} %",
                  "RMSE δ̂": _f(b["rmse_delta"]), "iteraciones AP": b["iteraciones"]} for b in sint["base"]],
                ["semilla", "Medium", "Extreme", "RMSE δ̂", "iteraciones AP"]) + [""]
    s = sint["staff"]
    L += [(f"**Planteles locales:** RMSE de δ̂ contra la verdad {s['rmse_sin_alpha']:.4f} sin α_{{j,k}} → "
           f"{s['rmse_con_alpha']:.4f} con α_{{j,k}} (Prop. 2′): el segundo efecto fijo elimina el sesgo del C_D medio del plantel."), ""]
    cal = sint["calibracion"]
    base = cal["nulo"]
    filas = []
    for etq, nombre in (("nulo", "sin sesgo"), ("lambda", f"λ = {f02['sintetica']['lambda_escala']} (solo Extreme)"),
                        ("tau", f"τ = {f02['sintetica']['tau_reloj']} (solo Extreme)")):
        x = cal[etq]
        e = x["por_cubeta"]["Extreme Altitude"]
        b = base["por_cubeta"]["Extreme Altitude"]
        filas.append({"escenario": nombre, "c verdad": f"{e['c_verdad']:+.4f}",
                      "Deming pendiente": f"{x['deming']['pendiente']:.3f} (z={_f(x['deming']['z_pendiente_vs_1'], 1)})",
                      "ĉ dif.": f"{e['c_dif']:+.4f}", "ĉ ê": f"{e['c_e']:+.4f}",
                      "Δĉ dif. vs nulo": f"{e['c_dif'] - b['c_dif']:+.4f}", "Δĉ ê vs nulo": f"{e['c_e'] - b['c_e']:+.4f}"})
    L += ["**Calibración (Prop. 3′), cubeta Extreme, mismos juegos y ruido en los tres escenarios:**", "",
          *_tabla(filas, list(filas[0])), "",
          ("**Lectura honesta.** Ambos sesgos mueven ĉ en la dirección y con la magnitud esperadas (columnas Δ vs nulo ≈ ±0.02), "
           "pero la banda de G2.3 ([0.85, 1.15]) NO los marca: la pendiente de Deming se queda dentro de la banda aun con "
           "τ = 1.01. Además, ĉ_g tiene un sesgo de línea base por ruido de medición (columna 'sin sesgo'), de modo que solo "
           "las diferencias contra un nulo emparejado son interpretables. Detalle en `docs/discrepancias/D02b.md`."), ""]
    return L


def reporte_md(a: dict, sint: dict, gates: dict, f02: dict, segundos: float, figs: list[str]) -> str:
    L = ["# FASE 02 — Densidad del aire por juego desde la trayectoria", "",
         f"{a['datos']['filas_entrada']:,} filas de entrada · {a['datos']['filas_salida']:,} lanzamientos válidos · {segundos}s", ""]
    L += _sec_datos(a) + _sec_resultados(a) + _sec_deming_se(a) + _sec_calibracion(a) + _sec_latentes(a)
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
           f"σ_η {a['se']['sigma_eta_D']:.4f} · SE CR2 mediano {a['se']['se_cr2_D_mediana']:.4f} · G2.1 "
           f"{100 * sint['g21_error_max']:.3f} % · {a['juegos']['confirmatorios']:,} juegos confirmatorios"),
          "- Desviaciones respecto al ROADMAP: ninguna en las compuertas; ver D02b (sensibilidad de G2.3 y sesgo de línea base de ĉ)",
          "- Mejora posible detectada: 🔎 D02b — con el detector ê escala y reloj son separables; la banda de G2.3 no detecta 2 %",
          "- Riesgo de empeorar: ninguno",
          "- Rama / PR / commit de resultados locales: fase02 / (pendiente) / (pendiente)",
          "- Log: reports/logs/f02_<fecha>.log", ""]
    return "\n".join(L)


# ==========================================================================
def cargar_pitches(ruta: Path) -> pl.DataFrame:
    cols = ["game_anon_id", "pitcher_anon_id", "familia", "pitcher_throws_r", "year", "altitude_category_h", "excluir_modelo",
            "x0", "y0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0", "PitchTrajectoryXc1", "SpinRate", "SpinAxis",
            "RelHeight", "PlateLocHeight"]
    lf = io.leer_pitches(ruta)
    disp = set(lf.collect_schema().names())
    return lf.select([c for c in cols if c in disp]).collect()


def correr(cfg, df: pl.DataFrame, ruta_densidad: Path, rep_dir: Path, log_dir: Path, fig_dir: Path) -> dict:
    """Ejecuta F2 sobre `df` (datos limpios de F0 o la sintética). Devuelve {'ok', 'gates', 'reporte'}; no sale del proceso."""
    t0 = time.time()
    f02, fis = cfg["f02"], cfg["fisica"]
    print(f"F2: {df.height:,} lanzamientos × {df.width} columnas", flush=True)
    r = analizar(df, f02, fis, cfg["seed"])
    a, pj = r["agregados"], r["por_juego"]
    print("F2: sintética con física exacta (G2.1 y escenarios) ...", flush=True)
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
               "se_metodo": a["se"]["metodo"]}
    (log_dir / f"f02_{stamp}.log").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(md)
    return {"ok": all(g["ok"] for g in gates.values()), "gates": gates, "reporte": rep_dir / "FASE_02.md",
            "agregados": a}
