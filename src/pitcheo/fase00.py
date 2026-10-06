"""F0 — Ingesta y QA por identidades: orquestación, compuertas y reporte.

`correr()` lee el parquet canónico, aplica la limpieza (ADR-002 a 007), corre las identidades,
evalúa G0.1-G0.6, escribe `data/interim/pitches.parquet` (particionado por year) y el reporte
con el Bloque para el orquestador. Si hay valores "sin regla" no se escribe el parquet: el reporte
los lista y la fase falla (G0.5).

Solo agregados (ROADMAP §6): ni el reporte, ni el .json, ni el log, ni la figura traen filas por
lanzamiento ni tablas por lanzador.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from . import io, limpieza, qa
from .config import RAIZ


def _json(obj, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


# --------------------------------------------------------------------------
# Alcance (agregado)
# --------------------------------------------------------------------------
def alcance(df: pl.DataFrame) -> dict:
    """Juegos, lanzadores y lanzamientos por year × cubeta; lanzadores por número de cubetas."""
    d = df.with_columns(pl.col("altitude_category_h").cast(pl.Utf8).fill_null("(sin cubeta)").alias("cubeta"))
    tabla = (d.group_by("year", "cubeta")
             .agg(pl.col("game_anon_id").drop_nulls().n_unique().alias("juegos"),
                  pl.col("pitcher_anon_id").drop_nulls().n_unique().alias("lanzadores"),
                  pl.len().alias("lanzamientos"))
             .sort("year", "cubeta"))
    con_cub = d.filter(pl.col("pitcher_anon_id").is_not_null() & pl.col("altitude_category_h").is_not_null())
    por_lanz = con_cub.group_by("pitcher_anon_id").agg(
        pl.col("altitude_category_h").n_unique().alias("n_cubetas"))
    dist = por_lanz.group_by("n_cubetas").len().sort("n_cubetas")
    n30 = (con_cub.group_by("pitcher_anon_id", "altitude_category_h").len()
           .filter(pl.col("len") >= 30).group_by("pitcher_anon_id").len()
           .filter(pl.col("len") >= 2).height)
    return {
        "totales": {"filas": df.height,
                    "juegos": int(df["game_anon_id"].drop_nulls().n_unique()),
                    "lanzadores": int(df["pitcher_anon_id"].drop_nulls().n_unique()),
                    "bateadores": int(df["batter_anon_id"].drop_nulls().n_unique()),
                    "years": sorted(df["year"].unique().to_list())},
        "year_x_cubeta": tabla.to_dicts(),
        "lanzadores_por_n_cubetas": {str(r[0]): int(r[1]) for r in dist.iter_rows()},
        "lanzadores_con_30_lanzamientos_en_2_o_mas_cubetas": int(n30),
    }


# --------------------------------------------------------------------------
# Compuertas
# --------------------------------------------------------------------------
def _ge(v, minimo) -> bool:
    return v is not None and v >= minimo


def evaluar_gates(rep: dict, q: dict | None, g: dict, extras: dict | None = None, fis: dict | None = None) -> dict:
    """G0.1-G0.9 de ROADMAP §4-F0 (v2.4: ADR-010 a 013; v2.5: ADR-010 enmendado y 014; v2.6: ADR-016, G0.8′ y G0.9)."""
    fis = fis or {}
    sin_regla = len(rep["sin_regla"])
    gates: dict = {"G0.5": {"ok": sin_regla == 0, "detalle": f"valores sin regla: {sin_regla}"}}
    if q is None or extras is None:
        for k, txt in (("G0.1", "I1, I2, I6′"), ("G0.2", "polinomios"), ("G0.3", "diagnóstico de 2 outs"),
                       ("G0.4", "I9"), ("G0.6", "exclusiones"), ("G0.7", "marco temporal 9P"),
                       ("G0.8′", "cota del sesgo por pérdida de datos"), ("G0.9", "mecanismo de los outs faltantes")):
            gates[k] = {"ok": False, "detalle": f"no evaluada: hay valores sin regla ({txt})"}
        return dict(sorted(gates.items()))
    i1, i2, i6 = (q[k]["cumplimiento"] for k in ("I1", "I2", "I6p"))
    hay_tabla = bool(extras.get("discrepancias_flags"))
    gates["G0.1"] = {"ok": _ge(i1, g["g01_identidades_min"]) and _ge(i2, g["g01_identidades_min"])
                     and _ge(i6, g["g01_i6p_min"]) and hay_tabla,
                     "detalle": f"I1 {_pct(i1)} · I2 {_pct(i2)} (mín. {g['g01_identidades_min']:.1%}) · "
                                f"I6′ {_pct(i6)} (mín. {g['g01_i6p_min']:.1%}) · tabla de discrepancias is_* × "
                                f"pitch_call_h: {'producida' if hay_tabla else 'FALTA'}"}

    pol = extras["polinomios"]
    if "c1_con_ts" in pol:
        gates["G0.2"] = {"ok": bool(pol["existe"]),
                         "detalle": (f"ADR-010 enmendado: permutación {pol['permutacion']} · c2 R² por pares "
                                     f"{_f(pol['r2_c2_pares_min'], 6)} y conjunta {_f(pol['r2_c2_conjunta_min'], 6)} "
                                     f"(mín. {g['g02_r2_c2_min']}) · c1 con t_s R² mín. {_f(pol['r2_c1_con_ts_min'], 6)} "
                                     f"(mín. {g['g02_r2_c1_min']}) → **{pol['decision']}**; la trayectoria canónica "
                                     "sigue siendo la de los 9P")}
    else:
        gates["G0.2"] = {"ok": False, "detalle": "no se pudo evaluar la matriz de polinomios (pocos datos)"}

    dos, cla = extras["dos_outs"]["dos_outs"], extras["dos_outs"].get("clasificacion_no_finales", {})
    gates["G0.3"] = {"ok": "n" in dos and cla.get("n") is not None,
                     "detalle": (f"diagnóstico de las {dos.get('n', 0):,} medias entradas de 2 outs producido y clasificado "
                                 f"(no finales: {cla.get('n', 0):,}): turno incompleto {cla.get('pct_turno_incompleto')} % "
                                 f"vs out faltante (sin turno incompleto) {cla.get('pct_out_faltante')} %")}
    gates["G0.4"] = {"ok": q["I9"]["cumplimiento"] == g["g04_i9"],
                     "detalle": f"I9 {_pct(q['I9']['cumplimiento'])} de {q['I9']['n']:,} juegos con cubeta"}
    em, ec = rep["exclusiones"]["modelo"], rep["exclusiones"]["cadena"]
    gates["G0.6"] = {"ok": em["pct_total"] <= 100 * g["g06_modelo_max"] and ec["pct_total"] <= 100 * g["g06_cadena_max"],
                     "detalle": f"excluir_modelo {em['pct_total']:.3f} % (máx. {g['g06_modelo_max']:.0%}) · "
                                f"excluir_cadena {ec['pct_total']:.3f} % (máx. {g['g06_cadena_max']:.1%})"}

    cal = extras["calibracion_9p"]
    if "elegida" in cal:
        el, zt = cal["elegida"], cal.get("zonetime") or {}
        es, eh = el["error_side_ft"], el["error_height_ft"]
        vals = [es["mediana"], eh["mediana"], es["p99"], eh["p99"], zt.get("mediana")]
        ok7 = (all(v is not None for v in vals) and es["mediana"] <= g["g07_mediana_ft"]
               and eh["mediana"] <= g["g07_mediana_ft"] and es["p99"] <= g["g07_p99_ft"]
               and eh["p99"] <= g["g07_p99_ft"] and zt["mediana"] <= g["g07_zonetime_s"])
        vigente = (fis.get("y_plato_ft"), fis.get("signo_plateloc_x"))
        coincide = vigente == (round(el["y_plano_ft"], 7), el["signo"]) or (
            vigente[0] is not None and abs(vigente[0] - el["y_plano_ft"]) < 1e-6 and vigente[1] == el["signo"])
        gates["G0.7"] = {"ok": bool(ok7),
                         "detalle": (f"ADR-014 con y_p = {el['y_plano_ft']:.4f} ft y signo {el['signo']:+d}: |error| "
                                     f"mediana/p99 PlateLocSide {_f(es['mediana'])}/{_f(es['p99'])} ft · PlateLocHeight "
                                     f"{_f(eh['mediana'])}/{_f(eh['p99'])} ft (máx. {g['g07_mediana_ft']}/{g['g07_p99_ft']}) · "
                                     f"|ZoneTime − (t_p − t_s)| mediana {_f(zt.get('mediana'), 5)} s "
                                     f"(máx. {g['g07_zonetime_s']}) · config vigente "
                                     f"{'coincide' if coincide else 'DIFIERE (corre `pitcheo f00 --aplicar`)'}")}
    else:
        gates["G0.7"] = {"ok": False, "detalle": "no se pudo calibrar el marco temporal de los 9P (pocos datos)"}

    mo = extras["mecanismo_outs"]
    p17, g08, g09 = mo["prop17"], mo["G08p"], mo["G09"]
    if p17.get("evaluable"):
        e, n = p17["cubeta_extrema"], p17["cubeta_base"]
        detalle = (f"Prop. 17: W(Γ=1) {_f(p17['W']['1'])} · **W(Γ=2) {_f(p17['W']['2'])}** vs "
                   f"{g['g08_k_ic']}·SE_ref = {_f(g['g08_k_ic'] * p17['SE_ref'])} y 1·SE_ref = {_f(p17['SE_ref'])} "
                   f"(κ̄ {_f(p17['kappa_bar'])}, n {e} {p17['n_extrema']:,} / {n} {p17['n_base']:,}) · r̂ {e} "
                   f"{_pct(p17['r_hat'][e])} / {n} {_pct(p17['r_hat'][n])} · "
                   f"**perdida_ignorable = {str(g08['perdida_ignorable']).lower()}**"
                   + ("" if g08["ok"] else " → **DISCREPANCIA: el ancho del conjunto identificado supera al IC95 "
                                           "muestral; no se sigue a F1**"))
    else:
        detalle = f"contraste {p17.get('cubeta_extrema')} − {p17.get('cubeta_base')} no evaluable (falta una cubeta)"
    gates["G0.8′"] = {"ok": bool(g08["ok"]), "detalle": detalle}
    ic = g09["ic95"]
    gates["G0.9"] = {"ok": True, "detalle": (
        f"θ̂ global = {_f(g09['theta_global'])} IC95 {_ic_txt(ic)} → **{g09['mecanismo']}** "
        f"(U si sup ≤ {g['g09_u_max']} · L si inf ≥ {g['g09_l_min']} · mezcla en otro caso); se reporta siempre, no falla")}
    return dict(sorted(gates.items()))


def _f(v, d: int = 4) -> str:
    return "—" if v is None else f"{v:.{d}f}"


def _pct(v) -> str:
    return "—" if v is None else f"{100 * v:.4f} %"


# --------------------------------------------------------------------------
# Reporte
# --------------------------------------------------------------------------
def _i8_tipo(tipo: str, v: dict) -> str:
    """I8 por tipo: ✓, ✗ con las medianas de |HorzBreak| por mano, o ✗ «no informativo» si alguna es < umbral."""
    if v.get("signo_opuesto"):
        return f"{tipo}=✓"
    md, mz = v.get("mediana_abs_derecho_in"), v.get("mediana_abs_zurdo_in")
    marca = " no informativo" if v.get("no_informativo") else ""
    return f"{tipo}=✗ (|HB| mediana D {_f(md, 1)} / Z {_f(mz, 1)} in{marca})"


def _tabla(filas: list[dict], cols: list[str]) -> list[str]:
    if not filas:
        return ["_(vacía)_"]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for f in filas:
        out.append("| " + " | ".join("—" if f.get(c) is None else
                                     (f"{f[c]:,}" if isinstance(f[c], int) and c != "year" else str(f[c]))
                                     for c in cols) + " |")
    return out


def _sec_adr010(pol: dict) -> list[str]:
    L = ["## ADR-010 (enmienda v2.5) — los polinomios de trayectoria son los 9P en otros ejes", ""]
    if "matriz" not in pol:
        return L + [f"_Sin datos suficientes (n = {pol.get('n')})._", ""]
    L += [(f"n = {pol['n']:,} filas. Cada celda es **R² (pendiente)** de la regresión simple de la fila "
          "(eje del polinomio) sobre la columna (eje de los 9P)."), ""]
    for fam, nombre in (("c2", "aceleración a0 (ax0, ay0, az0)"), ("c1", "velocidad v0 (vx0, vy0, vz0)"),
                        ("c0", "posición r0 (x0, y0, z0)")):
        L += [f"**{fam} del polinomio sobre {nombre}**", "", "| polinomio \\ 9P | x | y | z |", "|---|---|---|---|"]
        for P in "XYZ":
            celdas = []
            for q in "xyz":
                c = pol["matriz"][fam][P][q]
                celdas.append("—" if c["r2"] is None else f"{c['r2']:.4f} ({c['pendiente']:+.3f})")
            L.append(f"| {P} | " + " | ".join(celdas) + " |")
        L.append("")
    ts = pol["t_s"]
    L += [(f"- Permutación (elegida con **c2**, que no depende del origen de tiempo): {pol['permutacion']} · signos "
          f"{pol['signos']} · escala |2·pendiente(c2)| {({k: _f(v) for k, v in pol['escala_2c2_sobre_a0'].items()})}"),
          (f"- c2: R² por pares mín. **{_f(pol['r2_c2_pares_min'], 6)}** · regresión conjunta mín. "
          f"**{_f(pol['r2_c2_conjunta_min'], 6)}** (exigido {pol['r2_exigidos']['c2']})")]
    if ts.get("n"):
        L.append(f"- **t_s por lanzamiento** = (s·c1_X − v0)/a0 (n = {ts['n']:,}): mediana {ts['mediana_s']:.5f} s · "
                 f"IQR {ts['rango_intercuartil_s']:.5f} s · p1 {ts['p1_s']:.5f} · p99 {ts['p99_s']:.5f}  "
                 "(negativo = el polinomio arranca ANTES de y = 50 ft: en la liberación)")
        L.append("- t_s por eje (mediana, consistencia): "
                 + ", ".join(f"{e}: {_f(v, 5)}" for e, v in pol["t_s_mediana_por_eje"].items()))
    L += ["", "**c1 del polinomio sobre (v0 + a0·t_s) del eje permutado** — contra v2.4, que comparaba c1 con v0 a secas:", "",
          "| eje del polinomio | R² con t_s | pendiente | R² sin t_s (v2.4) | nota |", "|---|---|---|---|---|"]
    for P, v in pol["c1_con_ts"].items():
        L.append(f"| {P} | {_f(v['r2'], 6)} | {_f(v['pendiente'], 5)} | {_f(pol['c1_sin_ts'][P]['r2'], 4)} | "
                 + ("eje de referencia: 1 por construcción" if v["referencia"] else "prueba independiente") + " |")
    L += ["", f"- R² mín. de c1 con t_s: **{_f(pol['r2_c1_con_ts_min'], 6)}** (exigido {pol['r2_exigidos']['c1_con_ts']})",
          f"- **Decisión: `{pol['decision']}`** — " + (
              "los polinomios son los 9P en ejes permutados con el origen de tiempo en la liberación; sirven de "
              "verificación cruzada." if pol["existe"] else
              "no se cumple la enmienda: se declaran no canónicos y no se usan."),
          "", "Regresión conjunta de c2 (informativa): cada eje del polinomio sobre los tres ejes de los 9P a la vez.", "",
          "| eje del polinomio | R² | coef. sobre (x, y, z) | intercepto |", "|---|---|---|---|"]
    for P, v in pol["rotacion"]["c2"].items():
        L.append(f"| {P} | {_f(v['r2'], 6)} | ({', '.join(f'{c:+.4f}' for c in v['coef_xyz'])}) | {v['intercepto']:.4f} |")
    return L + [""]


def _sec_adr014(cal: dict, fis: dict) -> list[str]:
    L = ["## ADR-014 — marco temporal único de los 9P", ""]
    if "elegida" not in cal:
        return L + [f"_Sin datos suficientes (n = {cal.get('n')})._", ""]
    L += [("El reloj de los 9P arranca en y0 = 50 ft; `ZoneTime` y los polinomios arrancan en la liberación. El tiempo "
          "al plato t_p es la raíz de y(t_p) = y_p con los 9P (no `ZoneTime`). Se elige el plano y_p y el signo s de "
          "`PlateLocSide = s·x(t_p)` por mínimo error mediano. |error| en pies, mediana / p99:"), "",
          f"n = {cal['n']:,}", "", "| y_p (ft) | signo s | PlateLocSide | PlateLocHeight | elegida |", "|---|---|---|---|---|"]
    el = cal["elegida"]
    for c in cal["combinaciones"]:
        marca = "✅" if (c["y_plano_ft"], c["signo"]) == (el["y_plano_ft"], el["signo"]) else ""
        L.append(f"| {c['y_plano_ft']:.4f} | {c['signo']:+d} | {_f(c['error_side_ft']['mediana'])} / "
                 f"{_f(c['error_side_ft']['p99'])} | {_f(c['error_height_ft']['mediana'])} / "
                 f"{_f(c['error_height_ft']['p99'])} | {marca} |")
    zt, zc = cal.get("zonetime"), cal.get("zonetime_cruda")
    if zt:
        L += ["", (f"- **Verificación de ZoneTime** con t_s por lanzamiento: |ZoneTime − (t_p − t_s)| mediana "
              f"**{_f(zt['mediana'], 5)} s** · p99 {_f(zt['p99'], 5)} s (n = {zt['n']:,}). "
              f"Lo que se hacía mal, |ZoneTime − t_p|: mediana {_f(zc['mediana'], 5)} s.")]
    else:
        L += ["", "- ZoneTime no se pudo verificar: los polinomios no son equivalentes (no hay t_s por lanzamiento)."]
    vig = (fis.get("y_plato_ft"), fis.get("signo_plateloc_x"))
    L += [f"- Config vigente (`fisica.y_plato_ft`, `fisica.signo_plateloc_x`): y_p = {vig[0]}, s = {vig[1]}. "
          + ("Coincide con la elegida por los datos." if vig[0] is not None and abs(vig[0] - el["y_plano_ft"]) < 1e-6
             and vig[1] == el["signo"] else
             f"**Difiere** de la elegida (y_p = {el['y_plano_ft']:.7f}, s = {el['signo']:+d}): "
             "`pitcheo f00 --aplicar` la escribe en config/default.yaml."), ""]
    return L


def _sec_adr011(disc: dict) -> list[str]:
    L = ["## ADR-011 — banderas is_* del organizador vs. pitch_call_h", "",
         ("El árbol de desenlaces se define desde `pitch_call_h` (partición exacta); las `is_*` son verificación "
         "cruzada. Abajo, solo las combinaciones que **discrepan**; la tabla completa (cada combinación con su n) "
         "está en `reports/fase_00.json`."), "",
         "| derivada | bandera | n | discrepantes | % |", "|---|---|---|---|---|"]
    mal = []
    for col, v in disc.items():
        L.append(f"| {col} | {v['bandera']} | {v['n']:,} | {v['discrepantes']:,} | {v['pct_discrepantes']} |")
        mal += [f for f in v["tabla"] if f["derivada_valor"] != f["bandera_valor"]]
    return L + [""] + _tabla(sorted(mal, key=lambda f: -f["n"]),
                             ["derivada", "derivada_valor", "bandera", "bandera_valor", "pitch_call_h", "n"]) + [""]


def _ic_txt(ic, d: int = 3, escala: float = 1.0) -> str:
    return "—" if not ic else f"[{ic[0] * escala:.{d}f}, {ic[1] * escala:.{d}f}]"


def _sec_adr012_016(dos_outs: dict, mo: dict) -> list[str]:
    d2, d3, cla = dos_outs["dos_outs"], dos_outs["tres_outs"], dos_outs["clasificacion_no_finales"]
    L = ["## ADR-012 / ADR-016 — medias entradas de 2 outs registrados: out faltante", "",
         ("Sin orden de lanzamientos, un turno es **incompleto** si hay lanzamientos de un bateador de la media entrada "
          "sin ningún evento terminal (lo que dejaría un robo o un pickoff con 2 outs). Si todos sus turnos terminan, la "
          "media entrada tiene un **out faltante (sin turno incompleto)**: `OutsOnPlay` no lo cuenta (U) o se perdió con "
          "su turno (L). La Prop. 16 de más abajo los separa."), ""]
    if d2.get("n"):
        L += [(f"**Clasificación de las {cla['n']:,} medias entradas NO finales de 2 outs:** turno incompleto "
               f"{cla['turno_incompleto']:,} (**{cla['pct_turno_incompleto']} %**) · out faltante (sin turno incompleto) "
               f"{cla['out_faltante']:,} (**{cla['pct_out_faltante']} %**)."), ""]

        def cuant(g):
            c = g["lanzamientos_por_media_entrada"]
            return f"{c['mediana']:.0f} / {c['media']:.1f}"
        filas = [
            ("medias entradas", f"{d2['n']:,}", f"{d3['n']:,}"),
            ("% que es la última del juego", d2["pct_ultima_del_juego"], d3["pct_ultima_del_juego"]),
            ("lanzamientos por media entrada (mediana / media)", cuant(d2), cuant(d3)),
            ("% con ≥1 turno incompleto", d2["pct_con_turno_incompleto"], d3["pct_con_turno_incompleto"]),
            ("ponches por out registrado", _f(d2["ponches_por_out_registrado"], 3),
             _f(d3["ponches_por_out_registrado"], 3)),
        ] + [(f"eventos {e} por media entrada", d2["eventos_terminales_por_media_entrada"][e],
              d3["eventos_terminales_por_media_entrada"][e]) for e in d2["eventos_terminales_por_media_entrada"]] + [
            ("outs implicados por eventos − OutsOnPlay", d2["outs_implicados_por_eventos_menos_OutsOnPlay"],
             d3["outs_implicados_por_eventos_menos_OutsOnPlay"])]
        L += ["| métrica | 2 outs | 3 outs |", "|---|---|---|"] + [f"| {a} | {b} | {c} |" for a, b, c in filas] + [""]
    else:
        L += ["_No hay medias entradas de 2 outs._", ""]

    # ---- ADR-016: conjunto T, Prop. 16 y Prop. 17 ----
    L += ["## ADR-016 — ¿outs no contabilizados (U) o turnos perdidos (L)?", "",
          ("**Conjunto T** = medias entradas no finales, `Inning` ≤ 9, consistentes (outs registrados ≤ 3) y sin turno "
           "incompleto. `O_h` = Σ `OutsOnPlay`; **P** = {O_h = 2}; `N_h` = turnos con evento 1B, 2B, 3B, BB, HBP o ROE; "
           "**Z** = {N_h = 0}. Bajo S1 (un U exige un corredor, luego Z = 0) y S2 (L no depende de Z): "
           "r_b = p⁰_b / f_b, con f_b = P(Z | b), p⁰_b = P(P ∧ Z | b) y θ_b = r_b / P(P | b)."), "",
          "| filtro | excluye (en cascada) | no lo cumplen (solo este filtro) | quedan |", "|---|---|---|---|"]
    for p in mo["T"]["pasos"]:
        L.append(f"| {p['filtro']} | {_n(p['excluye'])} | {_n(p['excluye_solo_este'])} | {p['quedan']:,} |")
    t = mo["T"]
    L += ["", f"T: {t['medias_entradas']:,} medias entradas · |P| = {t['P']:,} · |Z| = {t['Z']:,} · |P ∧ Z| = {t['PZ']:,}", ""]

    p16 = mo["prop16"]
    L += [(f"### Prop. 16 por cubeta y global (IC95 por bootstrap de {p16['juegos']:,} juegos, "
           f"{p16['bootstrap']['n']} réplicas, semilla {p16['bootstrap']['seed']})"), "",
          "| cubeta | medias entradas | P % | f_b = Z % | p⁰_b % | **r̂_b %** [IC95] | **θ̂_b** [IC95] |",
          "|---|---|---|---|---|---|---|"]
    for r in p16["por_cubeta"] + [p16["global"]]:
        ic = r["ic95"]
        L.append(f"| {r['cubeta']} | {r['medias_entradas']:,} | {_f(r['tasa_P'] and 100 * r['tasa_P'], 2)} | "
                 f"{_f(r['f'] and 100 * r['f'], 2)} | {_f(100 * r['p0'], 3)} | "
                 f"**{_f(r['r_hat'] and 100 * r['r_hat'], 3)}** {_ic_txt(ic['r_hat'], 3, 100)} | "
                 f"**{_f(r['theta_hat'], 3)}** {_ic_txt(ic['theta_hat'])} |")
    L += [""]
    g9 = mo["G09"]
    L += [(f"**G0.9 (mecanismo):** θ̂ global = {_f(g9['theta_global'])} IC95 {_ic_txt(g9['ic95'])} → "
           f"**{g9['mecanismo']}** ({g9['regla']}). Se reporta siempre; no falla."), ""]

    p17 = mo["prop17"]
    L += ["### Prop. 17 — cota del sesgo del contraste Extreme − No", ""]
    if p17.get("evaluable"):
        e, n = p17["cubeta_extrema"], p17["cubeta_base"]
        L += [f"- m̃_b (turnos por media entrada de T_b): {e} {_f(p17['m_tilde'][e])} · {n} {_f(p17['m_tilde'][n])}",
              (f"- n_b (turnos): {e} {p17['n_extrema']:,} · {n} {p17['n_base']:,} · κ̄ (K por turno, global) = "
              f"{_f(p17['kappa_bar'], 5)}"),
              (f"- **W(Γ=1) = {_f(p17['W']['1'], 5)} · W(Γ=2) = {_f(p17['W']['2'], 5)}** · SE_ref = {_f(p17['SE_ref'], 5)} "
              f"· 3.92·SE_ref = {_f(3.92 * p17['SE_ref'], 5)} · W(Γ=2)/SE_ref = {_f(mo['G08p'].get('W_sobre_SE_ref'), 3)}"),
              (f"- **G0.8′:** {'pasa' if mo['G08p']['ok'] else 'FALLA (discrepancia, no se sigue a F1)'} · "
               f"`perdida_ignorable` = **{str(mo['G08p']['perdida_ignorable']).lower()}** "
               f"({'F8 reporta los contrastes con intervalo de Imbens–Manski' if not mo['G08p']['perdida_ignorable'] else 'W(Γ=2) ≤ SE_ref'})"),
              ""]
    else:
        L += ["_No evaluable: falta la cubeta extrema o la base._", ""]

    # ---- corroboraciones (a)-(e): informativas ----
    c = mo["corroboraciones"]
    L += ["### Corroboraciones (informativas, no son compuertas)", "",
          (f"**(a) Rodados entre los OUT_BIP con `Outs` previo ∈ {{0, 1}}** ({c['a_rodados']['definicion']}): U (doble "
          "matanza) predice más rodados en P que en T∖P; L, la misma mezcla."), ""]
    L += _tabla([{"grupo": k, "n": v["n"], "rodados": v["k"], "%": v["pct"], "IC95 Wilson %": v["ic95_wilson_pct"]}
                 for k, v in (("P", c["a_rodados"]["P"]), ("T∖P", c["a_rodados"]["T_menos_P"]))],
                ["grupo", "n", "rodados", "%", "IC95 Wilson %"]) + [""]
    L += [("**(b) Columna `Outs` (estado previo), P vs. T∖P.** U no quita lanzamientos: `Outs` es continuo y empieza en 0; "
          "L deja huecos o arranca en 1."), ""]
    L += _tabla([{"grupo": k, "medias entradas": v["n"], "% mín. Outs > 0": v["pct_min_outs_mayor_0"],
                  "% out terminal con Outs = 2": v["pct_out_con_estado_2"], "% hueco en Outs": v["pct_hueco_en_outs"]}
                 for k, v in (("P", c["b_outs_previo"]["P"]), ("T∖P", c["b_outs_previo"]["T_menos_P"]))],
                ["grupo", "medias entradas", "% mín. Outs > 0", "% out terminal con Outs = 2", "% hueco en Outs"]) + [""]
    lg = c["c_logit"]
    L += [("**(c) Logit de 1[h ∈ P]** sobre cubeta + year, sin y con factor(min(N_h, 5)); errores agrupados por juego; "
          f"OR contra {lg.get('base', '—')} (IC95). Si el OR cae al controlar por N_h, la diferencia es tráfico de "
          "corredores."), ""]
    if "error" in lg:
        L += [f"_No se pudo ajustar: {lg['error']}_", ""]
    else:
        cubs = [k for k in lg["sin_N_h"] if k != "convergio"] if "error" not in lg["sin_N_h"] else []
        filas = []
        for cb in cubs:
            fila = {"cubeta": cb}
            for etq, clave in (("OR sin N_h", "sin_N_h"), ("OR con N_h", "con_N_h")):
                v = lg[clave].get(cb)
                fila[etq] = f"{v['OR']:.3f} {_ic_txt(v['ic95'], 2)}" if v else "—"
            filas.append(fila)
        L += _tabla(filas, ["cubeta", "OR sin N_h", "OR con N_h"])
        sin_conv = [k for k in ("sin_N_h", "con_N_h") if lg[k].get("convergio") is False or "error" in lg[k]]
        if sin_conv:
            L += ["", (f"_Ajuste sin convergencia plena o con error en: {', '.join(sin_conv)} (típico si algún nivel de "
                  "N_h casi no tiene P)._")]
        L += [""]
    dd = c["d_dobles"]
    L += [(f"**(d) Jugadas con `OutsOnPlay` ≥ 2:** {dd['jugadas_con_2_o_mas_outs']:,} en {dd['juegos']:,} juegos; "
           f"a la tasa MLB de referencia ({dd['tasa_mlb_ref_por_juego']} dobles matanzas por juego, solo referencia) se "
           f"esperarían ≈ {dd['dobles_matanzas_esperadas_ref']:,.0f}: se registra el "
           f"{_f(dd['fraccion_registrada'] and 100 * dd['fraccion_registrada'], 1)} %."), ""]
    L += _tabla(dd["por_evento"], ["evento", "OutsOnPlay", "n"]) + [""]
    pe = c["e_poisson"]
    if pe.get("histograma"):
        L += [(f"**(e) |P| por juego vs. Poisson** (figura `docs/figuras/f00/P_por_juego_vs_poisson.png`): {pe['juegos']:,} "
               f"juegos · λ = {_f(pe['lambda'], 3)} · dispersión de Pearson φ = {_f(pe['dispersion_phi'], 2)} (≈ 1 = "
               f"evento de juego a tasa constante; ≫ 1 = concentrado en algunos juegos) · P(≥1) observada "
               f"{_f(pe['P_ge1']['observado'], 3)} vs Poisson {_f(pe['P_ge1']['poisson'], 3)} · P(>2) "
               f"{_f(pe['P_gt2']['observado'], 3)} vs {_f(pe['P_gt2']['poisson'], 3)}"), ""]
    else:
        L += ["**(e)** No hay suficientes juegos con P para comparar con una Poisson.", ""]

    # ---- informativas ----
    inf = mo["informativas"]
    L += ["### Tablas informativas", "",
          ("**Out faltante (sin turno incompleto) por cubeta** (antiguo G0.8, ya no es compuerta): medias entradas no "
           "finales, IC de Wilson al 95 %. Mezcla U y L; la Prop. 16 los separa."), ""]
    filas = [{"cubeta": r["cubeta"], "medias_entradas": r["medias_entradas"], "dos_outs": r["dos_outs"],
              "turno_incompleto": r["turno_incompleto"], "out_faltante": r["out_faltante"],
              "tasa_%": f"{100 * r['tasa_out_faltante']:.3f}",
              "ic95_wilson_%": f"[{100 * r['ic95_wilson'][0]:.3f}, {100 * r['ic95_wilson'][1]:.3f}]"}
             for r in inf["out_faltante_por_cubeta"]]
    L += _tabla(filas, list(filas[0]) if filas else []) + ["",
          f"Rango entre cubetas (máx − mín): {_f(inf.get('rango_pp'), 3)} pp", "", "**Por cubeta y año:**", ""]
    filas = [{"cubeta": r["cubeta"], "year": r["year"], "medias_entradas": r["medias_entradas"],
              "out_faltante": r["out_faltante"], "tasa_%": f"{100 * r['tasa_out_faltante']:.3f}",
              "ic95_wilson_%": f"[{100 * r['ic95_wilson'][0]:.3f}, {100 * r['ic95_wilson'][1]:.3f}]"}
             for r in inf["out_faltante_por_cubeta_anio"]]
    L += _tabla(filas, list(filas[0]) if filas else []) + [""]
    L += [("**Déficits de eventos** (media por media entrada de las de 3 outs − media de las de 2 outs; IC95 por bootstrap "
          "de medias entradas). Informativos: el estimador de la fracción de ponches por déficits se retiró (ADR-016: no está "
          "identificado; D01 resuelta). No se implementan pesos ω (F4)."), ""]
    for nombre, clave in (("todas las de 2 outs", "deficits_todas_las_de_2_outs"),
                          ("solo las de out faltante sin turno incompleto", "deficits_sin_turno_incompleto")):
        d = inf[clave]
        if "deficit" in d:
            L.append(f"- **{nombre}** (n = {d['n_dos']:,} vs {d['n_tres']:,}): "
                     + " · ".join(f"d_{e} = {v['estimado']:.3f} {_ic_txt(v['ic95'])}" for e, v in d["deficit"].items()))
    return L + [""]


def _n(v) -> str:
    return "—" if v is None else f"{v:,}"


def _cifras_v26(extras: dict | None) -> str:
    """Cifras de v2.6 para el Bloque: t_s, ADR-014 y ADR-016 (θ̂, r̂ por cubeta, W y reglas)."""
    if not extras:
        return ""
    ts = extras["polinomios"].get("t_s", {})
    cal = extras["calibracion_9p"]
    el, zt = cal.get("elegida") or {}, cal.get("zonetime") or {}
    mo = extras["mecanismo_outs"]
    p16, p17, g9 = mo["prop16"], mo["prop17"], mo["G09"]
    r_b = ", ".join(f"{r['cubeta']} {_pct(r['r_hat'])}" for r in p16["por_cubeta"])
    w = (f"W(Γ=2) {_f(p17['W']['2'], 5)} vs 3.92·SE_ref {_f(3.92 * p17['SE_ref'], 5)} (SE_ref {_f(p17['SE_ref'], 5)})"
         if p17.get("evaluable") else "W no evaluable")
    return (f"t_s mediana {_f(ts.get('mediana_s'), 4)} s · ADR-014 y_p {_f(el.get('y_plano_ft'), 4)} ft, signo "
            f"{el.get('signo')}, |ZoneTime−(t_p−t_s)| mediana {_f(zt.get('mediana'), 5)} s · ADR-016: θ̂ "
            f"{_f(g9['theta_global'], 3)} {_ic_txt(g9['ic95'])} → **{g9['mecanismo']}** · r̂ por cubeta: {r_b} · {w} · "
            f"perdida_ignorable {str(mo['perdida_ignorable']).lower()}")


def _secciones_v24(extras: dict, fis: dict | None = None) -> list[str]:
    """Secciones del reporte de v2.4 a v2.6: ADR-010 (enmendado), 014, 011, 012 y 016."""
    return (_sec_adr010(extras["polinomios"]) + _sec_adr014(extras["calibracion_9p"], fis or {})
            + _sec_adr011(extras["discrepancias_flags"])
            + _sec_adr012_016(extras["dos_outs"], extras["mecanismo_outs"])
            + ["**OutsOnPlay × evento_terminal** (¿cuenta el out de los ponches?)", ""]
            + _tabla(extras["dos_outs"]["outs_on_play_x_evento_terminal"], ["evento", "OutsOnPlay", "n"]) + [""])


def reporte_md(rep: dict, q: dict | None, alc: dict | None, gates: dict, escritos: dict, segundos: float,
               extras: dict | None = None, fis: dict | None = None) -> str:
    L = ["# FASE 00 — Ingesta y QA por identidades", "",
         f"Filas de entrada: {rep['filas_entrada']:,}"
         + (f" · filas de salida: {rep['filas_salida']:,}" if "filas_salida" in rep else "")
         + f" · {segundos}s", ""]
    if escritos:
        L += [f"`{escritos['ruta']}` particionado por year: "
              + ", ".join(f"{k}: {v:,}" for k, v in escritos["filas_por_year"].items()), ""]

    L += ["## Valores sin regla (G0.5)", ""]
    if rep["sin_regla"]:
        L += [("**La fase falla y NO se escribió `pitches.parquet`.** Pásale esta tabla al orquestador: "
              "ningún valor se asigna en silencio."), ""]
        L += _tabla(rep["sin_regla"], ["columna", "valor", "n"])
    else:
        L += ["Ninguno: todo valor de las columnas inventariadas tiene regla en `config/categorias.yaml`."]
    L += [""]

    L += ["## Tipos normalizados", ""]
    conv = [{"columna": c, **{k: v for k, v in i.items()}} for c, i in rep["conversiones"].items()]
    if conv:
        resumen: dict = {}
        for c in conv:
            resumen.setdefault((c["de"], c["a"]), []).append(c["columna"])
        for (de, a), cols in resumen.items():
            L.append(f"- {de} → {a}: {len(cols)} columnas (" + ", ".join(cols[:6]) + (", …" if len(cols) > 6 else "") + ")")
        raros = [c for c in conv if c.get("nan_a_nulo") or c.get("tokens_nulos")]
        for c in raros:
            L.append(f"- `{c['columna']}`: NaN→nulo {c.get('nan_a_nulo', 0):,} · tokens nulos→nulo {c.get('tokens_nulos', 0):,}")
    else:
        L.append("- Sin conversiones.")
    L += [""]

    if q is None:
        L += ["_Sin identidades, alcance ni ADR: la limpieza no corrió por los valores sin regla._", ""]
    else:
        L += ["## Identidades (ROADMAP §4-F0)", "",
              "| ID | cumplimiento | n | detalle |", "|---|---|---|---|"]
        det = {
            "I1": f"tol. {q['I1']['tolerancia_mph']} mph",
            "I2": "exacta",
            "I3": "**sustituida por G0.2 (ADR-010)**, ya no es compuerta; " + " · ".join(
                f"{e}: {_pct(v['cumplimiento'])}, 2c2/a0={_f(v['razon_mediana_2c2_sobre_a0'])}"
                for e, v in q["I3"]["por_eje"].items()),
            "I4": f"pendiente (origen) {_f(q['I4'].get('pendiente_origen'))}, con intercepto {_f(q['I4'].get('pendiente'))}, "
                  f"r={_f(q['I4'].get('correlacion'), 6)}",
            "I5": f"R={_f(q['I5'].get('R'), 6)}, espejo={q['I5'].get('espejo')}, desfase aprendido {_f(q['I5'].get('desfase_grados'), 1)}°",
            "I6p": f"suma {_pct(q['I6p']['suma'])} · contacto⇔Foul/InPlay {_pct(q['I6p']['contacto_equivale_a_foul_o_inplay'])}"
                   f" · whiff⇒StrikeSwinging {_pct(q['I6p']['whiff_implica_strike_swinging'])}",
            "I7": f"criterio A estricto (n = medias entradas); A sin la final: {_pct(q['I7'].get('sin_ultima_media_entrada'))}"
                  f"; **B (no finales): {_pct(q['I7'].get('B_no_finales'))}**; inconsistentes (≥4 outs): "
                  f"{q['I7'].get('inconsistentes')}; outs por media entrada {q['I7'].get('distribucion_outs')}",
            "I8": "tipos: " + ", ".join(_i8_tipo(t, v) for t, v in q["I8"]["tipos"].items() if v.get("evaluado"))
                  + (f" · fallas no informativas (mediana de |HorzBreak| < {q['I8']['mediana_min_in']:g} in en una mano): "
                     f"{len(q['I8']['fallas_no_informativas'])} de {len(q['I8']['fallas'])}" if q["I8"]["fallas"] else ""),
            "I9": f"juegos incoherentes: {q['I9']['juegos_incoherentes']}",
            "I10": f"violaciones: {q['I10']['violaciones']} {q['I10']['valores_invalidos']}",
        }
        nombres = {"I6p": "I6′"}
        for k, v in q.items():
            L.append(f"| {nombres.get(k, k)} | {_pct(v['cumplimiento'])} | {v['n']:,} | {det[k]} |")
        L += [""]

        a = alc["totales"]
        L += ["## Alcance del dataset (agregado)", "",
              (f"- {a['filas']:,} lanzamientos · {a['juegos']:,} juegos · {a['lanzadores']:,} lanzadores · "
              f"{a['bateadores']:,} bateadores · years {a['years']}"),
              f"- lanzadores por número de cubetas: {alc['lanzadores_por_n_cubetas']}",
              (f"- lanzadores con ≥30 lanzamientos en ≥2 cubetas (identificación intra-lanzador): "
              f"{alc['lanzadores_con_30_lanzamientos_en_2_o_mas_cubetas']:,}"), "",
              "### year × cubeta (cubeta imputada por juego, ADR-005)", ""]
        L += _tabla(alc["year_x_cubeta"], ["year", "cubeta", "juegos", "lanzadores", "lanzamientos"])
        L += ["", "## play_result × pitch_call_h × KorBB → evento terminal (ADR-007)", "",
              "Revisa que ninguna combinación inesperada tenga un evento que no debería.", ""]
        L += _tabla(rep["tabla_evento"], ["play_result", "pitch_call_h", "KorBB", "evento_terminal", "n"])
        L += ["", "### Incoherencias (se reportan, no fallan)", ""]
        L += _tabla(rep["incoherencias"], ["regla", "n", "pct"])

        L += ["", "## Imputaciones y exclusiones por ADR", ""]
        a2, a3, a4 = rep["ADR-002"], rep["ADR-003"], rep["ADR-004"]
        a5, a6 = rep["ADR-005"], rep["ADR-006"]
        pl_, pb = a3["lanzador"], a3["bateador"]
        rl = pl_["relside"]
        L += [
            f"- **ADR-002 familia:** {a2['familias']} · Sweeper (`es_sweeper`): {a2['sweepers']:,} · EXC: {a2['exc']:,}",
            (f"- **ADR-003 lanzador:** mano indefinida {pl_['filas_mano_indefinida']:,} "
            f"({pl_['pct_mano_indefinida']} %) → moda {pl_['imputadas_por_moda']:,} · signo de RelSide "
            f"{pl_['imputadas_por_relside']:,} · descartadas {pl_['descartadas']:,} ({pl_['pct_descartadas']} %). "
            f"Signo aprendido: derecha ⇔ RelSide {'> 0' if rl['derecha_es_signo_positivo'] else '< 0'}, "
            f"concordancia {rl['concordancia']:.4%} sobre {rl['filas_base']:,} filas "
            f"(umbral {rl['umbral']:.0%}, regla {'activa' if rl['regla_activa'] else 'INACTIVA'})"),
            (f"- **ADR-003 bateador:** Switch {pb['switch']:,} (resueltos con la mano opuesta: "
            f"{pb['switch_resueltos_opuesta']:,}) · Undefined/nulo {pb['filas_indefinidas']:,} "
            f"({pb['pct_indefinidas']} %) → imputados {pb['indefinidas_imputadas']:,} · "
            f"descartados {pb['descartadas']:,} ({pb['pct_descartadas']} %)"),
            (f"- **ADR-004:** {a4['foul_unificados']:,} fouls unificados · `Undefined` excluido: "
            f"{a4['undefined_excluidos']:,} ({a4['pct_undefined']} %)"),
            (f"- **ADR-005 cubeta:** nulas crudas {a5['filas_nulas_crudas']:,} ({a5['pct_nulas_crudas']} %) → imputadas por "
            f"juego {a5['imputadas_por_juego']:,} · quedan sin cubeta {a5['filas_sin_cubeta']:,} filas "
            f"({a5['pct_sin_cubeta']} %) en {a5['juegos_sin_cubeta']:,} juegos enteros nulos "
            f"(F2 les predice la cubeta, 🔎) · juegos con >1 cubeta: {a5['juegos_con_mas_de_una_cubeta']}"),
            f"- **ADR-006 Outs:** inválidos {a6['outs_invalidos']:,} ({a6['pct']} %) · nulos {a6['outs_nulos']:,}",
            f"- **ADR-007 eventos:** {rep['ADR-007']['eventos']}",
            f"- IDs nulos (informativo, no hay ADR): {rep['ids_nulos']}", "",
            f"- **ADR-011 desenlace desde pitch_call_h:** {rep.get('ADR-011')}",
            f"- **ADR-012 medias entradas:** {rep.get('ADR-012')}",
            ""]
        for nombre, clave in (("excluir_modelo (ADR-002/003/004/006 + ID de lanzador nulo, ADR-013)", "modelo"),
                              ("excluir_cadena (ADR-013: solo lo que invalida la transición del conteo)", "cadena")):
            exc = rep["exclusiones"][clave]
            L += [f"### {nombre}", ""]
            L += _tabla([{"motivo": m, "n": v["n"], "pct": v["pct"]} for m, v in exc["por_motivo"].items()],
                        ["motivo", "n", "pct"])
            L += ["", f"Total (unión, sin doble conteo): **{exc['total']:,}** lanzamientos = **{exc['pct_total']} %**.", ""]
        if extras:
            L += _secciones_v24(extras, fis)

    L += ["## Compuertas", ""]
    for k, v in gates.items():
        L.append(f"- **{k}** {'✅' if v['ok'] else '❌'} {v['detalle']}")
    L += ["", "### Bloque para el orquestador — F00",
          "- Modelo(s) usado(s): Sonnet",
          "- Compuertas: " + " | ".join(f"{k} {'✅' if v['ok'] else '❌'}" for k, v in gates.items()),
          (f"- Cifras clave: {alc['totales']['filas']:,} lanzamientos · {alc['totales']['juegos']:,} juegos · "
           f"excluir_modelo {rep['exclusiones']['modelo']['pct_total']} % · excluir_cadena "
           f"{rep['exclusiones']['cadena']['pct_total']} % · I1 {_pct(q['I1']['cumplimiento'])} · "
           f"I6′ {_pct(q['I6p']['cumplimiento'])} · I7 A {_pct(q['I7']['cumplimiento'])} / B no finales "
           f"{_pct(q['I7'].get('B_no_finales'))} · ADR-010: "
           f"{(extras or {}).get('polinomios', {}).get('decision', '—')} · {_cifras_v26(extras)}")
          if q is not None else "- Cifras clave: no disponibles (valores sin regla, ver arriba)",
          "- Desviaciones respecto al ROADMAP: ninguna (compuertas v2.6: G0.8′ y G0.9 de ADR-016)",
          "- Mejora posible detectada: ninguna",
          "- Riesgo de empeorar: ninguno",
          "- Rama / PR / commit de resultados locales: fase00 / (pendiente) / (pendiente)",
          "- Log: reports/logs/f00_<fecha>.log", ""]
    return "\n".join(L)


def figura_alcance(alc: dict, ruta: Path) -> None:
    """Dos paneles agregados: juegos por year × cubeta y lanzadores por número de cubetas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    filas = alc["year_x_cubeta"]
    years = sorted({f["year"] for f in filas})
    cubetas = sorted({f["cubeta"] for f in filas})
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    ancho = 0.8 / max(len(cubetas), 1)
    for i, c in enumerate(cubetas):
        ys = [next((f["juegos"] for f in filas if f["year"] == y and f["cubeta"] == c), 0) for y in years]
        ax[0].bar([j + i * ancho for j in range(len(years))], ys, ancho, label=c)
    ax[0].set_xticks([j + 0.4 - ancho / 2 for j in range(len(years))], [str(y) for y in years])
    ax[0].set_title("Juegos por temporada y cubeta")
    ax[0].legend(fontsize=7)
    d = alc["lanzadores_por_n_cubetas"]
    ax[1].bar(list(d), list(d.values()), color="#4c78a8")
    ax[1].set_title("Lanzadores por número de cubetas")
    ax[1].set_xlabel("cubetas distintas en las que lanzó")
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=120)
    plt.close(fig)


def figura_P_poisson(info: dict, ruta: Path) -> None:
    """Corroboración (e) de ADR-016: |P| por juego (barras) contra una Poisson con la misma media (puntos). Solo agregados."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    h = info["histograma"]
    ks = [r["k"] for r in h]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.bar(ks, [r["juegos"] for r in h], color="#4c78a8", label="observado")
    ax.plot(ks, [r["esperados_poisson"] for r in h], "o-", color="#e45756", label=f"Poisson (λ = {info['lambda']:.2f})")
    ax.set_xlabel("medias entradas de 2 outs registrados (P) por juego")
    ax.set_ylabel("juegos")
    ax.set_title(f"P por juego vs. Poisson · φ = {info['dispersion_phi']:.2f}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=120)
    plt.close(fig)


# --------------------------------------------------------------------------
def correr(cfg, parquet: Path, salida_pitches: Path, rep_dir: Path, log_dir: Path, fig_dir: Path) -> dict:
    """Ejecuta F0. Devuelve {'ok': bool, 'gates': ..., 'reporte': ruta}. No sale del proceso."""
    t0 = time.time()
    specs = io.leer_diccionario(cfg.ruta("diccionario"))
    cat = limpieza.cargar_categorias(cfg.ruta("categorias"))
    df = pl.read_parquet(parquet)
    print(f"leído {parquet.name}: {df.height:,} filas × {df.width} columnas", flush=True)

    limpio, rep = limpieza.limpiar(df, specs, cat, cfg["f00"])
    del df
    q = alc = extras = None
    escritos: dict = {}
    if limpio is not None:
        q = qa.correr_qa(limpio, cat, cfg["qa"])
        alc = alcance(limpio)
        extras = qa.correr_extras(limpio, cat, cfg["qa"], cfg["f00"]["gates"], cfg["fisica"], cfg["seed"])
        rep["identidades"], rep["alcance"], rep["extras"] = q, alc, extras
        gates = evaluar_gates(rep, q, cfg["f00"]["gates"], extras, cfg["fisica"])
        if gates["G0.5"]["ok"]:
            filas = io.escribir_particionado(limpio, salida_pitches)
            ruta = salida_pitches.relative_to(RAIZ) if salida_pitches.is_relative_to(RAIZ) else salida_pitches
            escritos = {"ruta": str(ruta), "filas_por_year": filas}
            figura_alcance(alc, fig_dir / "alcance.png")
            if extras["mecanismo_outs"]["corroboraciones"]["e_poisson"].get("histograma"):
                figura_P_poisson(extras["mecanismo_outs"]["corroboraciones"]["e_poisson"],
                                 fig_dir / "P_por_juego_vs_poisson.png")
    else:
        gates = evaluar_gates(rep, None, cfg["f00"]["gates"])

    segundos = round(time.time() - t0, 1)
    md = reporte_md(rep, q, alc, gates, escritos, segundos, extras, cfg["fisica"])
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / "FASE_00.md").write_text(md, encoding="utf-8")
    _json({"gates": gates, "segundos": segundos, "salida": escritos, **rep}, rep_dir / "fase_00.json")

    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    resumen = {"filas_entrada": rep["filas_entrada"], "filas_salida": rep.get("filas_salida"),
               "gates": {k: v["ok"] for k, v in gates.items()}, "exclusiones": rep.get("exclusiones"),
               "sin_regla": len(rep["sin_regla"]), "segundos": segundos}
    (log_dir / f"f00_{stamp}.log").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(md)
    elegida = ((extras or {}).get("calibracion_9p") or {}).get("elegida")
    mo = (extras or {}).get("mecanismo_outs") or {}
    return {"ok": all(g["ok"] for g in gates.values()), "gates": gates, "reporte": rep_dir / "FASE_00.md",
            "calibracion_elegida": elegida, "mecanismo_outs": mo.get("mecanismo_outs"),
            "perdida_ignorable": mo.get("perdida_ignorable")}


def aplicar_config(archivo: Path, elegida: dict | None = None, mecanismo: str | None = None,
                   ignorable: bool | None = None) -> dict:
    """Escribe en config/default.yaml lo que MIDIÓ F0: el plano y el signo de ADR-014 y, de ADR-016, `qa.mecanismo_outs`
    (U | L | mezcla) y `qa.perdida_ignorable` (bool), que leen F4, F6 y F8.

    Reemplaza solo esos valores (conserva el resto y los comentarios). Devuelve lo que cambió.
    """
    import re
    txt = archivo.read_text(encoding="utf-8")
    nuevo, cambios = txt, {}

    def poner(patron: str, valor: str, clave: str) -> None:
        nonlocal nuevo
        reemplazado = re.sub(patron, lambda m: f"{m.group(1)}{valor}", nuevo, count=1)
        if reemplazado != nuevo:
            cambios[clave] = valor
        nuevo = reemplazado

    if elegida:
        poner(r"(\n\s*y_plato_ft:\s*)[-+0-9.eE]+", f"{elegida['y_plano_ft']:.7f}", "y_plato_ft")
        poner(r"(\n\s*signo_plateloc_x:\s*)[-+]?\d+", str(elegida["signo"]), "signo_plateloc_x")
    if mecanismo in ("U", "L", "mezcla"):
        poner(r"(\n\s*mecanismo_outs:\s*)(?:U|L|mezcla)\b", mecanismo, "mecanismo_outs")
    if ignorable is not None:
        poner(r"(\n\s*perdida_ignorable:\s*)(?:true|false)\b", str(bool(ignorable)).lower(), "perdida_ignorable")
    if nuevo == txt:
        return {"cambio": False}
    archivo.write_text(nuevo, encoding="utf-8")
    return {"cambio": True, **cambios}
