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


def evaluar_gates(rep: dict, q: dict | None, g: dict) -> dict:
    """G0.1-G0.6 de ROADMAP §4-F0."""
    sin_regla = len(rep["sin_regla"])
    gates: dict = {"G0.5": {"ok": sin_regla == 0,
                            "detalle": f"valores sin regla: {sin_regla}"}}
    if q is None:
        for k, txt in (("G0.1", "I1, I2, I6′"), ("G0.2", "I3"), ("G0.3", "I7"), ("G0.4", "I9"),
                       ("G0.6", "exclusiones totales")):
            gates[k] = {"ok": False, "detalle": f"no evaluada: hay valores sin regla ({txt})"}
        return dict(sorted(gates.items()))
    i1, i2, i6 = (q[k]["cumplimiento"] for k in ("I1", "I2", "I6p"))
    gates["G0.1"] = {"ok": all(_ge(v, g["g01_identidades_min"]) for v in (i1, i2, i6)),
                     "detalle": f"I1 {_pct(i1)} · I2 {_pct(i2)} · I6′ {_pct(i6)} (mín. {g['g01_identidades_min']:.1%})"}
    i3 = q["I3"]
    gates["G0.2"] = {"ok": _ge(i3["cumplimiento"], g["g02_i3_min"]),
                     "detalle": f"I3 {_pct(i3['cumplimiento'])} (mín. {g['g02_i3_min']:.0%}); razón 2·c2/a0 por eje: "
                                + ", ".join(f"{e}={_f(v['razon_mediana_2c2_sobre_a0'])}" for e, v in i3["por_eje"].items())
                                + " — si falla: documentar la convención, no forzarla"}
    gates["G0.3"] = {"ok": _ge(q["I7"]["cumplimiento"], g["g03_i7_min"]),
                     "detalle": f"I7 {_pct(q['I7']['cumplimiento'])} de {q['I7']['n']:,} medias entradas "
                                f"(mín. {g['g03_i7_min']:.0%})"}
    gates["G0.4"] = {"ok": q["I9"]["cumplimiento"] == g["g04_i9"],
                     "detalle": f"I9 {_pct(q['I9']['cumplimiento'])} de {q['I9']['n']:,} juegos con cubeta"}
    pct_exc = rep["exclusiones"]["pct_total"]
    gates["G0.6"] = {"ok": pct_exc <= 100 * g["g06_exclusiones_max"],
                     "detalle": f"exclusiones {pct_exc:.3f} % de los lanzamientos (máx. {g['g06_exclusiones_max']:.0%})"}
    return dict(sorted(gates.items()))


def _f(v, d: int = 4) -> str:
    return "—" if v is None else f"{v:.{d}f}"


def _pct(v) -> str:
    return "—" if v is None else f"{100 * v:.4f} %"


# --------------------------------------------------------------------------
# Reporte
# --------------------------------------------------------------------------
def _tabla(filas: list[dict], cols: list[str]) -> list[str]:
    if not filas:
        return ["_(vacía)_"]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for f in filas:
        out.append("| " + " | ".join("—" if f.get(c) is None else
                                     (f"{f[c]:,}" if isinstance(f[c], int) and c != "year" else str(f[c]))
                                     for c in cols) + " |")
    return out


def reporte_md(rep: dict, q: dict | None, alc: dict | None, gates: dict, escritos: dict, segundos: float) -> str:
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
            "I3": " · ".join(f"{e}: {_pct(v['cumplimiento'])}, 2c2/a0={_f(v['razon_mediana_2c2_sobre_a0'])}"
                             for e, v in q["I3"]["por_eje"].items()),
            "I4": f"pendiente (origen) {_f(q['I4'].get('pendiente_origen'))}, con intercepto {_f(q['I4'].get('pendiente'))}, "
                  f"r={_f(q['I4'].get('correlacion'), 6)}",
            "I5": f"R={_f(q['I5'].get('R'), 6)}, espejo={q['I5'].get('espejo')}, desfase aprendido {_f(q['I5'].get('desfase_grados'), 1)}°",
            "I6p": f"suma {_pct(q['I6p']['suma'])} · contacto⇔Foul/InPlay {_pct(q['I6p']['contacto_equivale_a_foul_o_inplay'])}"
                   f" · whiff⇒StrikeSwinging {_pct(q['I6p']['whiff_implica_strike_swinging'])}",
            "I7": f"n son medias entradas; sin la última de cada juego: {_pct(q['I7'].get('sin_ultima_media_entrada'))}"
                  f"; distribución de outs {q['I7'].get('distribucion_outs')}",
            "I8": "tipos: " + ", ".join(f"{t}={'✓' if v.get('signo_opuesto') else '✗'}"
                                        for t, v in q["I8"]["tipos"].items() if v.get("evaluado")),
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
            "### Exclusiones de modelos y cadena (`excluir_modelo`)", ""]
        exc = rep["exclusiones"]
        L += _tabla([{"motivo": m, "n": v["n"], "pct": v["pct"]} for m, v in exc["por_motivo"].items()],
                    ["motivo", "n", "pct"])
        L += ["", f"Total (unión, sin doble conteo): **{exc['total']:,}** lanzamientos = **{exc['pct_total']} %**.", ""]

    L += ["## Compuertas", ""]
    for k, v in gates.items():
        L.append(f"- **{k}** {'✅' if v['ok'] else '❌'} {v['detalle']}")
    L += ["", "### Bloque para el orquestador — F00",
          "- Modelo(s) usado(s): Sonnet",
          "- Compuertas: " + " | ".join(f"{k} {'✅' if v['ok'] else '❌'}" for k, v in gates.items()),
          (f"- Cifras clave: {alc['totales']['filas']:,} lanzamientos · {alc['totales']['juegos']:,} juegos · "
           f"exclusiones {rep['exclusiones']['pct_total']} % · I1 {_pct(q['I1']['cumplimiento'])} · "
           f"I3 {_pct(q['I3']['cumplimiento'])} · I7 {_pct(q['I7']['cumplimiento'])}")
          if q is not None else "- Cifras clave: no disponibles (valores sin regla, ver arriba)",
          "- Desviaciones respecto al ROADMAP: ninguna",
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
    q = alc = None
    escritos: dict = {}
    if limpio is not None:
        q = qa.correr_qa(limpio, cat, cfg["qa"])
        alc = alcance(limpio)
        rep["identidades"], rep["alcance"] = q, alc
        gates = evaluar_gates(rep, q, cfg["f00"]["gates"])
        if gates["G0.5"]["ok"]:
            filas = io.escribir_particionado(limpio, salida_pitches)
            ruta = salida_pitches.relative_to(RAIZ) if salida_pitches.is_relative_to(RAIZ) else salida_pitches
            escritos = {"ruta": str(ruta), "filas_por_year": filas}
            figura_alcance(alc, fig_dir / "alcance.png")
    else:
        gates = evaluar_gates(rep, None, cfg["f00"]["gates"])

    segundos = round(time.time() - t0, 1)
    md = reporte_md(rep, q, alc, gates, escritos, segundos)
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
    return {"ok": all(g["ok"] for g in gates.values()), "gates": gates, "reporte": rep_dir / "FASE_00.md"}
