"""Limpieza de F0: ADR-002 a ADR-007 exactamente como están en ROADMAP §1.1.

Tres pasos, siempre en este orden:

1. `normalizar_tipos`: flags a bool, enteros a Int64, numéricas a Float64 (NaN -> nulo;
   tokens "NA", "None", "" -> nulo, criterio 4 de F0.0). Lo que no se pueda convertir
   NO se fuerza: va a la tabla "sin regla".
2. `verificar_categorias`: todo valor de una columna inventariada que no esté en
   `config/categorias.yaml` va a la tabla "sin regla" y la fase falla (G0.5).
3. `aplicar_adr`: columnas nuevas `familia`, `es_sweeper`, `pitcher_throws_r`,
   `batter_side_r`, `pitch_call_h`, `evento_terminal`, `altitude_category_h`,
   `excluir_modelo`, `motivo_exclusion`. Las columnas crudas se conservan.

`limpiar` encadena los tres y devuelve `(df | None, reporte)`; si hay valores sin regla
devuelve `None` (no se produce un parquet a medias) y el reporte los lista.

Nada de esto usa outcomes: son inventarios de etiquetas y reglas de limpieza.
"""
from __future__ import annotations

from pathlib import Path

import polars as pl
import yaml

from .io import ColSpec

# Tokens que cuentan como nulo al homologar (criterio 4 de ROADMAP §4-F0.0).
_TOKENS_NULO = {"", "na", "nan", "none", "null", "<na>"}
_TOKENS_BOOL = {"true": 1.0, "false": 0.0, "1": 1.0, "0": 0.0, "1.0": 1.0, "0.0": 0.0}


def cargar_categorias(ruta: str | Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------
# 1. Tipos
# --------------------------------------------------------------------------
def _a_float(s: pl.Series) -> tuple[pl.Series, dict]:
    """Convierte a Float64. Devuelve (serie, info) con tokens inválidos agregados."""
    info = {"nan_a_nulo": 0, "tokens_nulos": 0, "invalidos": {}}
    if s.dtype == pl.Utf8:
        limpio = s.str.strip_chars()
        es_token = limpio.str.to_lowercase().is_in(list(_TOKENS_NULO)).fill_null(False)
        info["tokens_nulos"] = int((es_token & s.is_not_null()).sum())
        f = limpio.cast(pl.Float64, strict=False)
        malo = f.is_null() & s.is_not_null() & ~es_token
        if malo.any():
            vc = limpio.filter(malo).value_counts().sort("count", descending=True).head(20)
            info["invalidos"] = {str(r[0]): int(r[1]) for r in vc.iter_rows()}
        f = pl.select(pl.when(es_token).then(None).otherwise(f)).to_series()
    else:
        f = s.cast(pl.Float64, strict=False)
    if f.dtype.is_float():
        n_nan = int(f.is_nan().sum())
        if n_nan:
            info["nan_a_nulo"] = n_nan
            f = f.fill_nan(None)
    return f, info


def normalizar_tipos(df: pl.DataFrame, specs: list[ColSpec]) -> tuple[pl.DataFrame, dict, list[dict]]:
    """Flags a bool, enteros a Int64, numéricas a Float64. Devuelve (df, conversiones, problemas)."""
    conversiones: dict = {}
    problemas: list[dict] = []
    nuevas: list[pl.Series] = []
    for s in specs:
        if s.nombre not in df.columns:
            continue
        col = df[s.nombre]
        if not (s.es_booleana or s.es_numerica):
            continue
        origen = str(col.dtype)
        if s.es_booleana:
            if col.dtype == pl.Boolean:
                continue
            if col.dtype == pl.Utf8:
                mapeo = col.str.strip_chars().str.to_lowercase().replace_strict(
                    _TOKENS_BOOL, default=None, return_dtype=pl.Float64)
                f, info = mapeo, {"nan_a_nulo": 0, "tokens_nulos": 0, "invalidos": {}}
                crudos = col.filter(mapeo.is_null() & col.is_not_null())
                if crudos.len():
                    vc = crudos.value_counts().head(20)
                    info["invalidos"] = {str(r[0]): int(r[1]) for r in vc.iter_rows()}
            else:
                f, info = _a_float(col)
            fuera = f.filter(f.is_not_null() & ~f.is_in([0.0, 1.0]))
            invalidos = dict(info["invalidos"])
            if fuera.len():
                for r in fuera.value_counts().head(20).iter_rows():
                    invalidos[str(r[0])] = int(r[1])
            if invalidos:
                for v, n in invalidos.items():
                    problemas.append({"columna": s.nombre, "valor": f"no es 0/1: {v}", "n": n})
                continue
            nueva = (f == 1.0).alias(s.nombre)
            nuevas.append(nueva)
            conversiones[s.nombre] = {"de": origen, "a": "Boolean", **_resumir(info)}
        elif s.es_entera:
            f, info = _a_float(col)
            if info["invalidos"]:
                for v, n in info["invalidos"].items():
                    problemas.append({"columna": s.nombre, "valor": f"no numérico: {v}", "n": n})
                continue
            nonint = f.filter(f.is_not_null() & ((f - f.round()).abs() > 0))
            if nonint.len():
                for r in nonint.value_counts().head(20).iter_rows():
                    problemas.append({"columna": s.nombre, "valor": f"no entero: {r[0]}", "n": int(r[1])})
                continue
            if col.dtype != pl.Int64:
                nuevas.append(f.cast(pl.Int64).alias(s.nombre))
                conversiones[s.nombre] = {"de": origen, "a": "Int64", **_resumir(info)}
        else:  # numérica real
            if col.dtype == pl.Float64 and not col.is_nan().any():
                continue
            f, info = _a_float(col)
            if info["invalidos"]:
                for v, n in info["invalidos"].items():
                    problemas.append({"columna": s.nombre, "valor": f"no numérico: {v}", "n": n})
                continue
            nuevas.append(f.alias(s.nombre))
            conversiones[s.nombre] = {"de": origen, "a": "Float64", **_resumir(info)}
    if nuevas:
        df = df.with_columns(nuevas)
    return df, conversiones, problemas


def _resumir(info: dict) -> dict:
    return {k: v for k, v in info.items() if k != "invalidos" and v}


# --------------------------------------------------------------------------
# 2. Inventario de categorías
# --------------------------------------------------------------------------
def verificar_categorias(df: pl.DataFrame, cat: dict) -> list[dict]:
    """Valores de columnas inventariadas que NO tienen regla en config/categorias.yaml."""
    out: list[dict] = []
    for col, info in cat["columnas"].items():
        if col not in df.columns:
            out.append({"columna": col, "valor": "<columna ausente>", "n": df.height})
            continue
        s = df[col].cast(pl.Utf8)
        permitidos = set(info["valores"])
        vc = s.drop_nulls().value_counts()
        for v, n in vc.iter_rows():
            if v not in permitidos:
                out.append({"columna": col, "valor": v, "n": int(n)})
        n_nulos = int(s.null_count())
        if n_nulos and not info.get("permite_nulos", False):
            out.append({"columna": col, "valor": "<nulo>", "n": n_nulos})
    return sorted(out, key=lambda r: (r["columna"], -r["n"]))


# --------------------------------------------------------------------------
# 3. ADR-002 a 007
# --------------------------------------------------------------------------
def _frac(n: int, total: int) -> float:
    return round(100.0 * n / total, 4) if total else 0.0


def _mano_lanzador(df: pl.DataFrame, f00: dict) -> tuple[pl.DataFrame, dict]:
    """ADR-003, lanzador: moda del lanzador (>= umbral) -> signo de RelSide aprendido -> descartar."""
    u = float(f00["umbral_moda"])
    u_rel = float(f00["umbral_relside"])
    d = df.with_columns(
        pl.col("PitcherThrows").cast(pl.Utf8).replace_strict(
            {"Right": True, "Left": False}, default=None, return_dtype=pl.Boolean).alias("_p_def"))

    stats = (d.filter(pl.col("_p_def").is_not_null() & pl.col("pitcher_anon_id").is_not_null())
             .group_by("pitcher_anon_id")
             .agg(pl.col("_p_def").cast(pl.Int64).sum().alias("_n_r"), pl.len().alias("_n"))
             .with_columns((pl.col("_n_r") / pl.col("_n")).alias("_sh_r"))
             .with_columns(pl.when(pl.col("_sh_r") >= u).then(True)
                           .when((1 - pl.col("_sh_r")) >= u).then(False)
                           .otherwise(None).alias("_p_moda"))
             .select("pitcher_anon_id", "_p_moda"))
    d = d.join(stats, on="pitcher_anon_id", how="left", maintain_order="left")

    # El signo de RelSide se APRENDE de las filas con mano definida (no se supone).
    base = d.filter(pl.col("_p_def").is_not_null() & pl.col("RelSide").is_not_null()
                    & (pl.col("RelSide") != 0))
    n_base = base.height
    acc_pos = float(base.select(((pl.col("RelSide") > 0) == pl.col("_p_def")).mean()).item()) if n_base else 0.0
    derecha_positivo = acc_pos >= 0.5
    acc = acc_pos if derecha_positivo else 1.0 - acc_pos
    regla_activa = n_base > 0 and acc >= u_rel
    valido_rel = pl.col("RelSide").is_not_null() & (pl.col("RelSide") != 0)
    pred_rel = (pl.col("RelSide") > 0) if derecha_positivo else (pl.col("RelSide") < 0)

    faltante = pl.col("_p_def").is_null()
    por_moda = faltante & pl.col("_p_moda").is_not_null()
    por_rel = faltante & pl.col("_p_moda").is_null() & valido_rel & pl.lit(regla_activa)
    d = d.with_columns(
        pl.coalesce(pl.col("_p_def"), pl.col("_p_moda"),
                    pl.when(valido_rel & pl.lit(regla_activa)).then(pred_rel)).alias("pitcher_throws_r"),
        por_moda.alias("_i_moda"), por_rel.alias("_i_rel"))
    n = d.height
    n_falt = int(d["_p_def"].is_null().sum())
    n_moda, n_rel = int(d["_i_moda"].sum()), int(d["_i_rel"].sum())
    n_desc = int(d["pitcher_throws_r"].is_null().sum())
    rep = {
        "filas_mano_indefinida": n_falt, "pct_mano_indefinida": _frac(n_falt, n),
        "imputadas_por_moda": n_moda, "imputadas_por_relside": n_rel,
        "descartadas": n_desc, "pct_descartadas": _frac(n_desc, n),
        "relside": {"derecha_es_signo_positivo": bool(derecha_positivo),
                    "concordancia": round(acc, 6), "filas_base": n_base,
                    "umbral": u_rel, "regla_activa": bool(regla_activa)},
    }
    return d.drop("_p_def", "_p_moda", "_i_moda", "_i_rel"), rep


def _mano_bateador(df: pl.DataFrame, f00: dict) -> tuple[pl.DataFrame, dict]:
    """ADR-003, bateador: Switch -> opuesta al lanzador; Undefined -> moda (>= umbral) u opuesta."""
    u = float(f00["umbral_moda"])
    a = float(f00["umbral_lado_ambos"])
    lado = pl.col("BatterSide").cast(pl.Utf8)
    d = df.with_columns(
        pl.coalesce(
            lado.replace_strict({"Right": True, "Left": False}, default=None, return_dtype=pl.Boolean),
            pl.when(lado == "Switch").then(~pl.col("pitcher_throws_r"))).alias("_b1"),
        (lado == "Switch").alias("_es_switch"))

    stats = (d.filter(pl.col("_b1").is_not_null() & pl.col("batter_anon_id").is_not_null())
             .group_by("batter_anon_id")
             .agg(pl.col("_b1").cast(pl.Int64).sum().alias("_n_r"), pl.len().alias("_n"))
             .with_columns((pl.col("_n_r") / pl.col("_n")).alias("_sh_r"))
             .select("batter_anon_id", "_sh_r"))
    d = d.join(stats, on="batter_anon_id", how="left", maintain_order="left")
    sh = pl.col("_sh_r")
    resuelto = (pl.when(sh >= u).then(True)
                .when((1 - sh) >= u).then(False)
                .when((sh >= a) & ((1 - sh) >= a)).then(~pl.col("pitcher_throws_r"))
                .otherwise(None))
    falta = pl.col("_b1").is_null()
    d = d.with_columns(
        pl.coalesce(pl.col("_b1"), pl.when(sh.is_not_null()).then(resuelto)).alias("batter_side_r"),
        falta.alias("_falta"))
    n = d.height
    indef = lado.is_in(["Undefined"]) | lado.is_null()
    n_switch = int(d["_es_switch"].sum())
    n_switch_ok = int((d["_es_switch"] & d["_b1"].is_not_null()).sum())
    n_indef = int(d.select(indef.sum()).item())
    n_imp = int((d["_falta"] & d["batter_side_r"].is_not_null()).sum())
    n_desc = int(d["batter_side_r"].is_null().sum())
    rep = {
        "switch": n_switch, "switch_resueltos_opuesta": n_switch_ok,
        "filas_indefinidas": n_indef, "pct_indefinidas": _frac(n_indef, n),
        "indefinidas_imputadas": n_imp, "descartadas": n_desc, "pct_descartadas": _frac(n_desc, n),
    }
    return d.drop("_b1", "_es_switch", "_sh_r", "_falta"), rep


def _altitud_por_juego(df: pl.DataFrame, cat: dict) -> tuple[pl.DataFrame, dict]:
    """ADR-005 (a): nulos de cubeta se imputan por juego si la cubeta es constante en el juego."""
    alt = pl.col("altitude_category").cast(pl.Utf8)
    por_juego = (df.filter(pl.col("game_anon_id").is_not_null() & alt.is_not_null())
                 .group_by("game_anon_id")
                 .agg(alt.n_unique().alias("_n_val"), alt.first().alias("_val")))
    d = df.join(por_juego, on="game_anon_id", how="left", maintain_order="left")
    imputable = alt.is_null() & (pl.col("_n_val") == 1)
    d = d.with_columns(
        pl.coalesce(alt, pl.when(imputable).then(pl.col("_val"))).alias("altitude_category_h"))
    n = d.height
    nulos = int(d["altitude_category"].null_count())
    imputadas = int(d.select(imputable.sum()).item())
    juegos_total = df["game_anon_id"].n_unique()
    juegos_con = por_juego.height
    juegos_incons = int((por_juego["_n_val"] > 1).sum())
    sin_cubeta = d.filter(pl.col("altitude_category_h").is_null())
    rep = {
        "filas_nulas_crudas": nulos, "pct_nulas_crudas": _frac(nulos, n),
        "imputadas_por_juego": imputadas,
        "filas_sin_cubeta": sin_cubeta.height, "pct_sin_cubeta": _frac(sin_cubeta.height, n),
        "juegos_total": int(juegos_total), "juegos_con_cubeta": int(juegos_con),
        "juegos_sin_cubeta": int(juegos_total - juegos_con),
        "juegos_con_mas_de_una_cubeta": juegos_incons,
    }
    return d.drop("_n_val", "_val"), rep


def _evento_terminal(cat: dict) -> pl.Expr:
    """ADR-007: prioridad KorBB -> HitByPitch -> bola en juego. Lo demás: no terminal (nulo)."""
    et = cat["evento_terminal"]
    korbb = pl.col("KorBB").cast(pl.Utf8)
    pch = pl.col("pitch_call_h").cast(pl.Utf8)
    pr = pl.col("play_result").cast(pl.Utf8)

    def mapear(expr, mapa):
        return expr.replace_strict(mapa, default=None, return_dtype=pl.Utf8)

    return (pl.when(korbb.is_in(list(et["korbb"]))).then(mapear(korbb, et["korbb"]))
            .when(pch.is_in(list(et["pitch_call_h"]))).then(mapear(pch, et["pitch_call_h"]))
            .when((pch == "InPlay") & pr.is_in(list(et["en_juego"]))).then(mapear(pr, et["en_juego"]))
            .otherwise(None))


def tabla_evento(df: pl.DataFrame) -> pl.DataFrame:
    """Frecuencias play_result x pitch_call_h x KorBB con el evento asignado (agregado)."""
    return (df.group_by(pl.col("play_result").cast(pl.Utf8), pl.col("pitch_call_h").cast(pl.Utf8),
                        pl.col("KorBB").cast(pl.Utf8), pl.col("evento_terminal").cast(pl.Utf8))
            .agg(pl.len().alias("n"))
            .sort("n", descending=True))


def incoherencias(df: pl.DataFrame, cat: dict) -> list[dict]:
    """Combinaciones raras entre play_result, pitch_call_h y KorBB. Se REPORTAN, no fallan."""
    et = cat["evento_terminal"]
    pr, pch = pl.col("play_result").cast(pl.Utf8), pl.col("pitch_call_h").cast(pl.Utf8)
    kb = pl.col("KorBB").cast(pl.Utf8)
    reglas = {
        "resultado de bola en juego sin pitch_call_h=InPlay":
            pr.is_in(et["resultados_bip"]) & (pch != "InPlay"),
        "pitch_call_h=InPlay con play_result sin regla de bola en juego (-> no terminal)":
            (pch == "InPlay") & ~pr.is_in(list(et["en_juego"])),
        "play_result=Strikeout con KorBB distinto de Strikeout": (pr == "Strikeout") & (kb != "Strikeout"),
        "play_result=Walk con KorBB distinto de Walk": (pr == "Walk") & (kb != "Walk"),
        "play_result=HitByPitch con pitch_call_h distinto de HitByPitch":
            (pr == "HitByPitch") & (pch != "HitByPitch"),
        "KorBB terminal con pitch_call_h=Undefined": kb.is_in(list(et["korbb"])) & (pch == "Undefined"),
    }
    n = df.height
    out = []
    for nombre, expr in reglas.items():
        c = int(df.select(expr.sum()).item())
        out.append({"regla": nombre, "n": c, "pct": _frac(c, n)})
    return out


def _banderas(d: pl.DataFrame, motivos: dict, col_bool: str, col_motivo: str) -> tuple[pl.DataFrame, dict]:
    """Bandera booleana + motivo (varios separados por ';'; nulo si ninguno) y su resumen agregado."""
    n = d.height
    d = d.with_columns(pl.concat_str(
        [pl.when(e).then(pl.lit(m)) for m, e in motivos.items()], separator=";", ignore_nulls=True
    ).alias(col_motivo))
    d = d.with_columns(
        (pl.col(col_motivo) != "").alias(col_bool),
        pl.when(pl.col(col_motivo) == "").then(None).otherwise(pl.col(col_motivo)).alias(col_motivo))
    por_motivo = {m: int(d.select(e.sum()).item()) for m, e in motivos.items()}
    total = int(d[col_bool].sum())
    return d, {"por_motivo": {m: {"n": c, "pct": _frac(c, n)} for m, c in por_motivo.items()},
               "total": total, "pct_total": _frac(total, n)}


def _desenlace_exprs(cat: dict) -> list[pl.Expr]:
    """ADR-011: es_swing, es_whiff, es_contacto, es_foul, es_bip desde pitch_call_h (Undefined -> nulo)."""
    pch = pl.col("pitch_call_h").cast(pl.Utf8)
    indef = pch.is_in(cat["pitch_call_h"]["excluir"])
    return [pl.when(indef).then(None).otherwise(pch.is_in(clases)).alias(col)
            for col, clases in cat["desenlace"].items() if col.startswith("es_")]


def tabla_medias_entradas(df: pl.DataFrame, inconsistente: int = 4) -> pl.DataFrame:
    """Una fila por media entrada (juego, entrada, mitad) con sus outs y los criterios A y B (ADR-012).

    - outs: suma de OutsOnPlay.   - tiene_estado_2: algún lanzamiento con Outs = 2 antes del lanzamiento.
    - final: la última media entrada del juego en el dato (no hay una posterior).
    - **A (estricto):** outs = 3.
    - **B (amplio):** hay estado previo Outs = 2, existe una media entrada posterior del juego
      (no es la final) y no es inconsistente (outs < `inconsistente`).
    Las de >= `inconsistente` outs se excluyen de ambos.
    """
    g = (df.filter(pl.col("game_anon_id").is_not_null() & pl.col("Inning").is_not_null()
                   & pl.col("Top/Bottom").is_not_null())
         .group_by("game_anon_id", "Inning", pl.col("Top/Bottom").cast(pl.Utf8).alias("mitad"))
         .agg(pl.col("OutsOnPlay").cast(pl.Float64).sum().cast(pl.Int64).alias("outs"),
              (pl.col("Outs").cast(pl.Float64) == 2).any().alias("tiene_estado_2"),
              pl.len().alias("n_lanz")))
    g = g.with_columns((pl.col("Inning") * 2 + (pl.col("mitad") == "Bottom").cast(pl.Int64)).alias("orden"))
    g = g.with_columns((pl.col("orden") == pl.col("orden").max().over("game_anon_id")).alias("final"))
    return g.with_columns(
        (pl.col("outs") == 3).alias("A"),
        (pl.col("tiene_estado_2") & ~pl.col("final") & (pl.col("outs") < inconsistente)).alias("B"))


def marcar_media_entrada(d: pl.DataFrame, inconsistente: int = 4) -> tuple[pl.DataFrame, dict]:
    """Columnas media_entrada_A y media_entrada_B por lanzamiento (ADR-012) y su resumen agregado."""
    t = tabla_medias_entradas(d, inconsistente)
    claves = ["game_anon_id", "Inning", "mitad"]
    d = (d.with_columns(pl.col("Top/Bottom").cast(pl.Utf8).alias("mitad"))
         .join(t.select(*claves, pl.col("A").alias("media_entrada_A"), pl.col("B").alias("media_entrada_B")),
               on=claves, how="left", maintain_order="left")
         .with_columns(pl.col("media_entrada_A").fill_null(False), pl.col("media_entrada_B").fill_null(False))
         .drop("mitad"))
    no_fin = t.filter(~pl.col("final"))
    rep = {
        "medias_entradas": t.height, "finales": int(t["final"].sum()), "no_finales": no_fin.height,
        "A": int(t["A"].sum()), "pct_A": _frac(int(t["A"].sum()), t.height),
        "B_no_finales": int(no_fin["B"].sum()), "pct_B_no_finales": _frac(int(no_fin["B"].sum()), no_fin.height),
        "inconsistentes": int((t["outs"] >= inconsistente).sum()),
        "distribucion_outs": {str(k): int(v) for k, v in t.group_by("outs").len().sort("outs").iter_rows()},
    }
    return d, rep


def aplicar_adr(df: pl.DataFrame, cat: dict, f00: dict) -> tuple[pl.DataFrame, dict]:
    """ADR-002 a 007. Devuelve el DataFrame con las columnas nuevas y el reporte agregado."""
    n = df.height
    rep: dict = {}

    # ADR-002 familia -----------------------------------------------------
    fam = cat["familia"]
    apt = pl.col("AutoPitchType").cast(pl.Utf8)
    d = df.with_columns(
        apt.replace_strict(fam["mapa"], default=None, return_dtype=pl.Utf8).alias("familia"),
        apt.is_in(fam["sweeper"]).alias("es_sweeper"))
    vc = d.group_by("familia").agg(pl.len().alias("n")).sort("n", descending=True)
    rep["ADR-002"] = {"familias": {r[0]: int(r[1]) for r in vc.iter_rows()},
                      "exc": int((d["familia"] == "EXC").sum()),
                      "sweepers": int(d["es_sweeper"].sum())}

    # ADR-004 PitchCall ---------------------------------------------------
    pc = cat["pitch_call_h"]
    d = d.with_columns(pl.col("PitchCall").cast(pl.Utf8)
                       .replace_strict(pc["mapa"], default=None, return_dtype=pl.Utf8).alias("pitch_call_h"))
    n_foul = int(d.select(pl.col("PitchCall").cast(pl.Utf8).is_in(
        [k for k, v in pc["mapa"].items() if v == "Foul"]).sum()).item())
    n_undef = int(d.select(pl.col("pitch_call_h").is_in(pc["excluir"]).sum()).item())
    rep["ADR-004"] = {"foul_unificados": n_foul, "undefined_excluidos": n_undef,
                      "pct_undefined": _frac(n_undef, n)}

    # ADR-011 desenlace desde pitch_call_h (partición exacta; Undefined queda en nulo) -------
    d = d.with_columns(_desenlace_exprs(cat))
    rep["ADR-011"] = {c: int(d[c].sum()) for c in cat["desenlace"] if c.startswith("es_") and c in d.columns}

    # ADR-003 mano --------------------------------------------------------
    d, rep_p = _mano_lanzador(d, f00)
    d, rep_b = _mano_bateador(d, f00)
    rep["ADR-003"] = {"lanzador": rep_p, "bateador": rep_b}

    # ADR-005 altitud -----------------------------------------------------
    d, rep["ADR-005"] = _altitud_por_juego(d, cat)

    # ADR-007 evento terminal --------------------------------------------
    d = d.with_columns(_evento_terminal(cat).alias("evento_terminal"))
    vc = d.group_by("evento_terminal").agg(pl.len().alias("n")).sort("n", descending=True)
    rep["ADR-007"] = {"eventos": {str(r[0]) if r[0] is not None else "NO_TERMINAL": int(r[1])
                                  for r in vc.iter_rows()}}

    # ADR-006 Outs + exclusiones -----------------------------------------
    validos = [float(x) for x in cat["outs_validos"]]
    outs_mal = ~pl.col("Outs").cast(pl.Float64).is_in(validos).fill_null(False)
    n_outs_mal = int(d.select(outs_mal.sum()).item())
    rep["ADR-006"] = {"outs_invalidos": n_outs_mal, "pct": _frac(n_outs_mal, n),
                      "outs_nulos": int(d["Outs"].null_count())}
    pch = pl.col("pitch_call_h").cast(pl.Utf8)
    motivos_modelo = {
        "ADR-002:EXC": pl.col("familia") == "EXC",
        "ADR-003:lanzador": pl.col("pitcher_throws_r").is_null(),
        "ADR-003:bateador": pl.col("batter_side_r").is_null(),
        "ADR-004:Undefined": pch.is_in(pc["excluir"]),
        "ADR-006:Outs": outs_mal,
        "ADR-013:pitcher_id_nulo": pl.col("pitcher_anon_id").is_null(),   # un "lanzador fantasma" en GroupKFold
    }
    # excluir_cadena: solo lo que invalida la transición del conteo (la mano o el ID no la afectan).
    motivos_cadena = {
        "ADR-004:Undefined": pch.is_in(pc["excluir"]),
        "ADR-006:Outs": outs_mal,
        "ADR-013:InPlay_sin_resultado": (pch == "InPlay") & pl.col("play_result").cast(pl.Utf8).is_in(
            cat["exclusion_cadena"]["inplay_sin_resultado"]),
    }
    d, exc_modelo = _banderas(d, motivos_modelo, "excluir_modelo", "motivo_exclusion")
    d, exc_cadena = _banderas(d, motivos_cadena, "excluir_cadena", "motivo_cadena")
    rep["exclusiones"] = {"modelo": exc_modelo, "cadena": exc_cadena}

    # ADR-012 completitud de media entrada (A estricto / B amplio) ---------------
    if {"Inning", "Top/Bottom", "OutsOnPlay", "Outs", "game_anon_id"} <= set(d.columns):
        d, rep["ADR-012"] = marcar_media_entrada(d, int(cat.get("outs_inconsistente", 4)))

    # Enums de las columnas derivadas ------------------------------------
    d = d.with_columns(
        pl.col("familia").cast(pl.Enum(fam["orden"])),
        pl.col("pitch_call_h").cast(pl.Enum(pc["orden"])),
        pl.col("evento_terminal").cast(pl.Enum(cat["evento_terminal"]["orden"])),
        pl.col("altitude_category_h").cast(pl.Enum(cat["columnas"]["altitude_category"]["valores"])))
    return d, rep


def a_enum(df: pl.DataFrame, cat: dict) -> pl.DataFrame:
    """Columnas crudas inventariadas -> Enum de polars (ya verificadas: no hay valores sin regla)."""
    return df.with_columns(
        [pl.col(c).cast(pl.Utf8).cast(pl.Enum(info["valores"])) for c, info in cat["columnas"].items()
         if c in df.columns])


# --------------------------------------------------------------------------
def limpiar(df: pl.DataFrame, specs: list[ColSpec], cat: dict, f00: dict) -> tuple[pl.DataFrame | None, dict]:
    """Normaliza tipos, verifica el inventario y aplica ADR-002 a 007.

    Devuelve `(df_limpio, reporte)`. Si hay valores sin regla, `df_limpio` es None.
    """
    rep: dict = {"filas_entrada": df.height}
    d, rep["conversiones"], problemas = normalizar_tipos(df, specs)
    sin_regla = problemas + verificar_categorias(d, cat)
    rep["sin_regla"] = sin_regla
    if sin_regla:
        return None, rep
    d, rep_adr = aplicar_adr(d, cat, f00)
    rep.update(rep_adr)
    d = a_enum(d, cat)
    rep["tabla_evento"] = tabla_evento(d).to_dicts()
    rep["incoherencias"] = incoherencias(d, cat)
    rep["ids_nulos"] = {c: int(d[c].null_count()) for c in
                        ("pitcher_anon_id", "batter_anon_id", "catcher_anon_id", "game_anon_id")
                        if c in d.columns}
    rep["filas_salida"] = d.height
    return d, rep
