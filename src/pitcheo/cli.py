"""CLI de pitcheo. Un subcomando por fase del ROADMAP; ningún módulo importa cli.

    pitcheo f00_0   inspección de los tres formatos crudos + perfil vs diccionario
    pitcheo f00     ingesta, limpieza (ADR-002 a 007) y QA por identidades I1-I10
    pitcheo f02     densidad del aire por juego desde la trayectoria (Props. 1, 2′, 3′)
    pitcheo f01, f03 ... f11                                   (pendientes)

Mismo patrón que `dtcoach` en Historia-de-un-entrenador.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from .config import Config

# Fases todavía no implementadas: subcomando -> (etiqueta ROADMAP, pista).
_PENDIENTES = {
    "f01": "F1 — Pre-registro de hipótesis",
    "f03": "F3 — Invariantes, eficiencia de giro y operador T",
    "f04": "F4 — Variable objetivo: pesos lineales, cadena de conteos, carry",
    "f05": "F5 — Arsenal, agrupamiento por forma y auditoría de fugas",
    "f06": "F6 — Modelos: Stuff+, Pitching+ y Location+",
    "f07": "F7 — Validación fuera de muestra",
    "f08": "F8 — Efecto altitud y veredictos H1-H6",
    "f09": "F9 — Agregación, perfil ideal y recomendaciones",
    "f10": "F10 — Dashboard simulador",
    "f11": "F11 — Reporte final",
}


def _json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


# ----------------------------------------------------------------------
def cmd_f00_0(a, cfg):
    """Inspección de los tres formatos crudos y perfil del parquet canónico."""
    from . import io

    base = Path(a.base) if a.base else None
    if a.sintetico:
        from .sintetico import escribir_tres_formatos, generar
        sc = cfg["sintetico"]
        destino = base or (cfg.ruta("interim") / "sintetico" / "stuff_model_df")
        print(f"generando {a.sintetico} juegos sintéticos en {destino}.* ...", flush=True)
        df = generar(a.sintetico, cfg["seed"], sc.get("cubetas"),
                     sc["n_lanzadores"], sc["n_bateadores"], sc["n_receptores"],
                     sc["n_lanzadores_nucleo"], tuple(sc["anios"]), sc["innings_por_juego"])
        escribir_tres_formatos(df, destino)
        base = destino

    if base is not None:
        parquet, pkl, rds = (base.with_suffix(e) for e in (".parquet", ".pkl", ".rds"))
    else:
        parquet, pkl, rds = cfg.ruta("raw_parquet"), cfg.ruta("raw_pkl"), cfg.ruta("raw_rds")

    if not Path(parquet).exists():
        sys.exit(f"No existe el parquet canónico {parquet}. En local debe estar en data/raw/ "
                 "(fuera de git); aquí usa `pitcheo f00_0 --sintetico N`.")

    t0 = time.time()
    dicc = io.leer_diccionario(cfg.ruta("diccionario"))
    tol = float(cfg["f00_0"]["tol_numerica"])
    max_u = int(cfg["f00_0"]["max_unicos"])

    tam = {
        "parquet": Path(parquet).stat().st_size,
        "pkl": Path(pkl).stat().st_size if Path(pkl).exists() else None,
        "rds": Path(rds).stat().st_size if Path(rds).exists() else None,
    }
    comparacion = io.comparar_formatos(parquet, pkl, rds, tol)
    perfil = io.perfilar_parquet(parquet, dicc, max_u)
    conteos = _conteos(parquet)

    gates = _evaluar_gates(comparacion, perfil)
    segundos = round(time.time() - t0, 1)

    # Con datos sintéticos NUNCA se escribe en reports/: ahí viven los reportes reales de la corrida local.
    rep_dir = (Path(parquet).parent / "reports") if a.sintetico else cfg.ruta("reportes")
    rep_dir.mkdir(parents=True, exist_ok=True)
    _json({"tamanos": tam, "comparacion": comparacion, "perfil": perfil,
           "conteos": conteos, "gates": gates, "segundos": segundos},
          rep_dir / "fase_00_0.json")
    md = _reporte_md(tam, comparacion, perfil, conteos, gates)
    (rep_dir / "FASE_00_0.md").write_text(md, encoding="utf-8")

    log_dir = (rep_dir / "logs") if a.sintetico else cfg.ruta("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    (log_dir / f"f00_0_{stamp}.log").write_text(
        json.dumps({"conteos": conteos, "gates": gates, "tamanos": tam, "segundos": segundos},
                   indent=2, ensure_ascii=False), encoding="utf-8")

    print(md)
    print(f"\nreporte -> {rep_dir / 'FASE_00_0.md'}  ({segundos}s)")
    if not all(g["ok"] for g in gates.values()):
        print("\n[COMPUERTA FALLIDA] ver el Bloque para el orquestador en el reporte.")
        sys.exit(2)


def _conteos(parquet) -> dict:
    from .io import leer_parquet_perezoso
    lf = leer_parquet_perezoso(parquet)
    cols = set(lf.collect_schema().names())
    ag = [pl.len().alias("filas")]
    for c, alias in (("PitchUID", "pitchuid_unicos"), ("game_anon_id", "juegos"),
                     ("pitcher_anon_id", "lanzadores"), ("batter_anon_id", "bateadores")):
        if c in cols:
            ag.append(pl.col(c).n_unique().alias(alias))
    r = lf.select(ag).collect().to_dicts()[0]
    extra = {}
    if "year" in cols:
        extra["year"] = sorted(lf.select("year").unique().collect().to_series().to_list())
    if "altitude_category" in cols:
        extra["altitude_category"] = (lf.group_by("altitude_category").agg(pl.len().alias("n"))
                                      .sort("n", descending=True).collect().to_dicts())
    return {**r, **extra}


def _evaluar_gates(comparacion: dict, perfil: dict) -> dict:
    """G00.1 PitchUID único y mismos IDs; G00.2 equivalencia 2-4; G00.3 columnas."""
    comps = comparacion.get("comparaciones", {})
    presentes = [c for c in comps.values() if c.get("estado") == "comparado"]
    g1 = all(c.get("pitchuid", {}).get("comparables", False) for c in presentes) if presentes else False
    g2 = all(c.get("equivalentes", False) for c in presentes) if presentes else False
    faltantes = perfil.get("faltantes", [])
    g3 = not faltantes
    return {
        "G00.1": {"ok": bool(g1), "detalle": "PitchUID único y mismos IDs en los formatos comparables"},
        "G00.2": {"ok": bool(g2), "detalle": "equivalencia (criterio 2-4) en todas las columnas comparadas"},
        "G00.3": {"ok": bool(g3), "detalle": f"columnas del diccionario ausentes: {faltantes or 'ninguna'}"},
    }


def _reporte_md(tam, comparacion, perfil, conteos, gates) -> str:
    def sz(x):
        return "—" if x is None else f"{x / 1e6:.2f} MB"
    L = ["# FASE 00.0 — Inspección de los tres formatos crudos", "",
         "## Tamaños en disco", "",
         f"- parquet: {sz(tam['parquet'])}", f"- pkl: {sz(tam['pkl'])}", f"- rds: {sz(tam['rds'])}", "",
         "## Equivalencia de formatos (criterio 1-4, ROADMAP §4-F0.0)", ""]
    for nombre, c in comparacion.get("comparaciones", {}).items():
        est = c.get("estado")
        if est != "comparado":
            L.append(f"- **{nombre}**: {est}" + (f" ({c.get('error', '')})" if est == "error_carga" else ""))
            continue
        puid = c.get("pitchuid", {})
        difs = {k: v for k, v in c.get("por_columna", {}).items() if v.get("estado") != "igual"}
        L.append(f"- **{nombre}**: equivalentes={c.get('equivalentes')} · "
                 f"PitchUID comparable={puid.get('comparables')} · "
                 f"columnas distintas={len(difs)}"
                 + (f" ({', '.join(f'{k}:{v.get('n_dif')}' for k, v in list(difs.items())[:8])})" if difs else ""))
    L += ["", "## Perfil del parquet contra el diccionario", "",
          f"- filas: {perfil.get('n_filas'):,}",
          f"- columnas no documentadas: {perfil.get('no_documentadas') or 'ninguna'}",
          f"- columnas del diccionario ausentes: {perfil.get('faltantes') or 'ninguna'}", ""]
    incumple = []
    for nombre, info in perfil.get("columnas", {}).items():
        if info.get("cumple_rango") is False:
            incumple.append(f"{nombre} (rango: {info.get('fuera_de_rango')} fuera)")
        if info.get("cumple_valores") is False:
            incumple.append(f"{nombre} (valores: {info.get('valores_fuera')})")
    L.append(f"- incumplimientos de unit_or_values: {incumple or 'ninguno'}")
    L += ["", "## Alcance del dataset", "",
          f"- filas: {conteos.get('filas'):,} · PitchUID únicos: {conteos.get('pitchuid_unicos'):,}",
          (f"- juegos: {conteos.get('juegos')} · lanzadores: {conteos.get('lanzadores')} · "
           f"bateadores: {conteos.get('bateadores')}"),
          f"- year: {conteos.get('year')}",
          f"- altitude_category: {conteos.get('altitude_category')}", ""]
    L += ["## Bloque para el orquestador — F00.0", "",
          "- Modelo(s) usado(s): Sonnet (andamiaje) / Opus (revisión)",
          "- Compuertas: " + " | ".join(
              f"{k} {'✅' if v['ok'] else '❌'}" for k, v in gates.items()),
          (f"- Cifras clave: {conteos.get('filas'):,} lanzamientos, {conteos.get('juegos')} juegos, "
           f"{conteos.get('lanzadores')} lanzadores"),
          "- Desviaciones respecto al ROADMAP: ninguna",
          "- Mejora posible detectada: ninguna",
          "- Riesgo de empeorar: ninguno",
          "- Rama / PR / commit de resultados locales: fase00_0 / (pendiente) / (pendiente)",
          "- Log: reports/logs/f00_0_<fecha>.log", "",
          ("> Si G00.1 o G00.2 fallan, el **orquestador** elige la fuente canónica "
           "(el código NUNCA elige por su cuenta)."), ""]
    return "\n".join(L)


def cmd_f00(a, cfg):
    """F0: lee el parquet canónico, limpia (ADR-002 a 007), corre I1-I10 y evalúa G0.1-G0.6."""
    from . import fase00

    out = Path(a.out) if a.out else None
    parquet = cfg.ruta("raw_parquet")
    if a.sintetico:
        from .sintetico import escribir_tres_formatos, generar
        sc = cfg["sintetico"]
        out = out or (cfg.ruta("interim") / "sintetico")
        print(f"generando {a.sintetico} juegos sintéticos en {out}/raw ...", flush=True)
        df = generar(a.sintetico, cfg["seed"], sc.get("cubetas"), sc["n_lanzadores"], sc["n_bateadores"],
                     sc["n_receptores"], sc["n_lanzadores_nucleo"], tuple(sc["anios"]), sc["innings_por_juego"])
        escribir_tres_formatos(df, out / "raw" / "stuff_model_df")
        parquet = out / "raw" / "stuff_model_df.parquet"
    if not parquet.exists():
        sys.exit(f"No existe el parquet canónico {parquet}. En local debe estar en data/raw/ "
                 "(fuera de git); aquí usa `pitcheo f00 --sintetico N`.")
    res = fase00.correr(
        cfg, parquet,
        salida_pitches=(out / "pitches.parquet") if out else cfg.ruta("pitches"),
        rep_dir=(out / "reports") if out else cfg.ruta("reportes"),
        log_dir=(out / "reports" / "logs") if out else cfg.ruta("logs"),
        fig_dir=(out / "figuras" / "f00") if out else cfg.ruta("figuras") / "f00")
    if a.aplicar and not a.sintetico and (res.get("calibracion_elegida") or res.get("mecanismo_outs")):
        r = fase00.aplicar_config(cfg.archivo, res["calibracion_elegida"], res["mecanismo_outs"],
                                  res["perdida_ignorable"])
        print(f"config actualizado ({cfg.archivo.name}): {r}" if r["cambio"] else "config ya coincide con lo medido")
    print(f"\nreporte -> {res['reporte']}")
    if not res["ok"]:
        print("\n[COMPUERTA FALLIDA] ver el Bloque para el orquestador en el reporte.")
        sys.exit(2)


def cmd_f02(a, cfg):
    """F2: densidad del aire por juego (Props. 1, 2′, 2″), compuertas G2.1–G2.4 y reporte, por etapas (ADR-019).

    `--etapa escala|sintetica|real|todo` (default todo = sintetica + real). Salida: 0 ok; 2 compuerta fallida o fase
    detenida (la equivalencia de Prop. 2″ no pasa); 130/143 si se interrumpió (los workers de loky se terminan).
    """
    from . import fase02, recursos

    recursos.instalar_senales()
    if a.n_jobs:
        cfg.setdefault("recursos", {})["n_jobs"] = a.n_jobs
    usar_cache = False if a.sin_cache else None
    out = Path(a.out) if a.out else None
    rep_dir = (out / "reports") if out else cfg.ruta("reportes")
    log_dir = (out / "reports" / "logs") if out else cfg.ruta("logs")
    etapa = a.etapa
    if a.escala and etapa == "todo":
        etapa = "escala"
    if etapa == "cerrar":
        sys.exit(fase02.correr_cerrar(cfg, rep_dir))
    if etapa == "escala":
        n = a.escala or 635000
        destino = rep_dir / "f02_escala.json"
        if a.reusar and fase02.escala_vigente(destino):
            print(f"prueba de escala vigente (mismo hash de código): se reutiliza {destino}")
            return
        res = fase02.prueba_escala(n, cfg)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        fase02._json(res, destino)
        print(f"\nprueba de escala -> {destino}")
        return
    sint = None
    if etapa == "sintetica":
        res = fase02.correr_sintetica(cfg, rep_dir, log_dir, usar_cache)
        print(f"\nreporte -> {res['reporte']}")
        if not res["ok"]:
            print("\n[COMPUERTA SINTÉTICA FALLIDA] ver docs/discrepancias/D02c.md; sin ajustar umbrales ni semillas.")
            sys.exit(2)
        return
    if etapa == "real":
        # con --out la sintética puede no estar ahí: se lee entonces la del repo (reports/f02_sintetica.json)
        rep_sint = rep_dir if (rep_dir / "f02_sintetica.json").exists() else cfg.ruta("reportes")
        try:
            sint = fase02.cargar_sintetica(cfg["f02"], rep_sint)
        except (FileNotFoundError, RuntimeError) as exc:
            sys.exit(f"[etapa real] {exc}")
    if a.sintetico:
        from .sintetico import generar_fisica
        out = out or (cfg.ruta("interim") / "sintetico")
        sc = cfg["f02"]["sintetica"]
        print(f"generando {a.sintetico} juegos sintéticos con física exacta ...", flush=True)
        df, _ = generar_fisica(a.sintetico, sc["lanzamientos_por_juego"], cfg["seed"], beta_D=sc.get("beta_D", 0.0),
                               beta_L=sc.get("beta_L", 0.0),
                               n_jobs=recursos.n_jobs_seguro(cfg))
        rep_dir = (out / "reports")
        log_dir = (out / "reports" / "logs")
    else:
        ruta = cfg.ruta("pitches")
        if not ruta.exists():
            sys.exit(f"No existe {ruta} (salida de F0). En local córrelo con `bash scripts/fases/f00.sh`; "
                     "aquí usa `pitcheo f02 --sintetico N`.")
        df = fase02.cargar_pitches(ruta, cfg["f02"].get("columna_parque"))
    res = fase02.correr(
        cfg, df,
        ruta_densidad=(out / "densidad_juego.parquet") if out else cfg.ruta("densidad_juego"),
        rep_dir=rep_dir, log_dir=log_dir,
        fig_dir=(out / "figuras" / "f2") if out else cfg.ruta("figuras") / "f2",
        sint=sint, usar_cache=usar_cache)
    print(f"\nreporte -> {res['reporte']}")
    if res.get("detenido"):
        print("\n[FASE DETENIDA] la equivalencia de Prop. 2″ no pasa: G2.2–G2.4 quedan en bruto con 🔎 (ADR-019).")
        sys.exit(2)
    if not res["ok"]:
        print("\n[COMPUERTA FALLIDA] ver el Bloque para el orquestador en el reporte.")
        sys.exit(2)


def cmd_pendiente(a, cfg):
    etq = _PENDIENTES[a.cmd]
    print(f"[pendiente] `{a.cmd}` corresponde a {etq}.")
    print("Esta fase todavía no está implementada (F0.0 es la entrega actual).")


# ----------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="pitcheo", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    sp = ap.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("f00_0", help="inspección de los tres formatos crudos")
    s.add_argument("--base", default=None, help="base sin extensión de los 3 archivos (default: config.rutas.raw_*)")
    s.add_argument("--sintetico", type=int, default=0, metavar="N",
                   help="genera N juegos sintéticos y los escribe en 3 formatos antes de inspeccionar")
    s.set_defaults(f=cmd_f00_0)

    s = sp.add_parser("f00", help="ingesta, limpieza (ADR-002 a 007) y QA por identidades")
    s.add_argument("--sintetico", type=int, default=0, metavar="N",
                   help="genera N juegos sintéticos (3 formatos) y corre F0 sobre ellos")
    s.add_argument("--aplicar", action="store_true",
                   help="escribe en config/default.yaml lo que midió F0: el y_p y el signo de PlateLocSide (ADR-014) y "
                        "qa.mecanismo_outs y qa.perdida_ignorable (ADR-016, G0.9 y G0.8′)")
    s.add_argument("--out", default=None,
                   help="redirige pitches, reportes, logs y figuras a este directorio (con --sintetico: "
                        "data/interim/sintetico)")
    s.set_defaults(f=cmd_f00)

    s = sp.add_parser("f02", help="densidad del aire por juego desde la trayectoria (Props. 1, 2′, 3′)")
    s.add_argument("--sintetico", type=int, default=0, metavar="N",
                   help="genera N juegos sintéticos con física exacta y corre F2 sobre ellos (no escribe en reports/)")
    s.add_argument("--etapa", choices=["escala", "sintetica", "real", "cerrar", "todo"], default="todo",
                   help="etapa a correr (ADR-019/020): escala | sintetica | real (usa f02_sintetica.json) | "
                        "cerrar (PR+squash+tag si gates reales ✅) | todo (sintetica + real)")
    s.add_argument("--escala", type=int, default=0, metavar="N",
                   help="atajo de --etapa escala: genera ≈N lanzamientos sintéticos, corre el análisis y reporta tiempo y RAM")
    s.add_argument("--reusar", action="store_true",
                   help="con --etapa escala: salta la corrida si reports/f02_escala.json tiene el mismo hash de código")
    s.add_argument("--sin-cache", action="store_true", help="ignora y no escribe la caché de la sintética (reports/cache/)")
    s.add_argument("--n-jobs", type=int, default=0, metavar="N",
                   help="workers de joblib (default recursos.n_jobs = 3; se acota a los núcleos físicos; nunca -1)")
    s.add_argument("--out", default=None, help="redirige densidad_juego, reportes, logs y figuras a este directorio")
    s.set_defaults(f=cmd_f02)

    for nombre, etq in _PENDIENTES.items():
        sp.add_parser(nombre, help=etq).set_defaults(f=cmd_pendiente)

    a = ap.parse_args(argv)
    cfg = Config.load(a.config)
    a.f(a, cfg)


if __name__ == "__main__":
    main()
