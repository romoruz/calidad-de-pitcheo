"""F0 — Identidades que el dato debe cumplir (ROADMAP §4-F0, I1-I5, I6′, I7-I10).

Cada identidad devuelve un dict con `cumplimiento` (fracción en [0, 1]), `n` (filas o grupos
evaluados) y el detalle que haga falta. Todas son robustas a nulos: solo se evalúan las filas
donde las columnas involucradas existen (los nulos reales de SpinAxis, Extension, etc. no son
violaciones). Operan sobre el DataFrame limpio de F0 (con `pitch_call_h`), pero solo usan
columnas físicas y de conteo: ningún outcome entra a un modelo aquí.

Si I3 falla, la convención de tiempo del polinomio es distinta a la supuesta: se documenta,
no se fuerza (por eso I3 reporta también la razón mediana 2·c2/a0 por eje).
"""
from __future__ import annotations

import math

import numpy as np
import polars as pl

G_FTS2 = 32.174


def _res(cumple: int, n: int, **extra) -> dict:
    return {"cumplimiento": (cumple / n) if n else None, "n": int(n), **extra}


def i1_speeddrop(df: pl.DataFrame, tol_mph: float = 0.05) -> dict:
    """I1: SpeedDrop = RelSpeed − ZoneSpeed (tolerancia 0.05 mph)."""
    d = df.select("RelSpeed", "ZoneSpeed", "SpeedDrop").drop_nulls()
    ok = ((d["RelSpeed"] - d["ZoneSpeed"] - d["SpeedDrop"]).abs() <= tol_mph).sum()
    return _res(int(ok), d.height, tolerancia_mph=tol_mph)


def i2_conteo(df: pl.DataFrame) -> dict:
    """I2: count = f(Balls, Strikes), exacta."""
    d = df.select("count", "Balls", "Strikes").drop_nulls()
    esperado = d["Balls"].cast(pl.Int64).cast(pl.Utf8) + "-" + d["Strikes"].cast(pl.Int64).cast(pl.Utf8)
    return _res(int((d["count"].cast(pl.Utf8) == esperado).sum()), d.height)


def i3_polinomio(df: pl.DataFrame, rtol: float = 0.01, piso: float = 1.0) -> dict:
    """I3: 2·c2 = a0 por eje (1 %, con piso del denominador). Cumplimiento = el peor eje."""
    por_eje = {}
    for eje, acc in (("X", "ax0"), ("Y", "ay0"), ("Z", "az0")):
        d = df.select(f"PitchTrajectory{eje}c2", acc).drop_nulls()
        c2, a0 = d[f"PitchTrajectory{eje}c2"].to_numpy(), d[acc].to_numpy()
        ok = np.abs(2 * c2 - a0) <= rtol * np.maximum(np.abs(a0), piso)
        grande = np.abs(a0) > piso
        razon = float(np.median(2 * c2[grande] / a0[grande])) if grande.any() else None
        por_eje[eje] = {"cumplimiento": float(ok.mean()) if len(ok) else None, "n": len(ok),
                        "razon_mediana_2c2_sobre_a0": razon}
    cumpl = [v["cumplimiento"] for v in por_eje.values() if v["cumplimiento"] is not None]
    n = max((v["n"] for v in por_eje.values()), default=0)
    return {"cumplimiento": min(cumpl) if cumpl else None, "n": n, "por_eje": por_eje,
            "tolerancia_relativa": rtol, "piso": piso}


def i4_gravedad(df: pl.DataFrame, rango: tuple[float, float] = (0.95, 1.05)) -> dict:
    """I4: (IVB − VB) ≈ ½ g t_f² en pulgadas; la pendiente debe caer en [0.95, 1.05]."""
    d = df.select("VertBreak", "InducedVertBreak", "ZoneTime").drop_nulls().filter(pl.col("ZoneTime") > 0)
    if d.height < 10:
        return {"cumplimiento": None, "n": d.height}
    y = (d["InducedVertBreak"] - d["VertBreak"]).to_numpy()
    x = 0.5 * G_FTS2 * d["ZoneTime"].to_numpy() ** 2 * 12.0
    pend0 = float((x @ y) / (x @ x))                       # por el origen
    pend1, interc = (float(v) for v in np.polyfit(x, y, 1))  # con intercepto
    return {"cumplimiento": 1.0 if rango[0] <= pend0 <= rango[1] else 0.0, "n": d.height,
            "pendiente_origen": pend0, "pendiente": pend1, "intercepto_in": interc,
            "correlacion": float(np.corrcoef(x, y)[0, 1]), "rango": list(rango)}


def _tilt_a_grados(tilt: pl.Series) -> np.ndarray:
    """'H:MM' -> grados en el reloj (12:00 = 0°, 30° por hora). No parseable -> NaN."""
    partes = tilt.str.split_exact(":", 1)
    h = partes.struct.field("field_0").cast(pl.Int64, strict=False)
    m = partes.struct.field("field_1").cast(pl.Int64, strict=False)
    minutos = ((h % 12) * 60 + m).cast(pl.Float64)
    return (minutos / 720.0 * 360.0).to_numpy()


def i5_tilt_spinaxis(df: pl.DataFrame, minimo: float = 0.99) -> dict:
    """I5: Tilt <-> SpinAxis biyectivos, medido como longitud resultante circular.

    No se supone el desfase ni el sentido: R = |media exp(i(a − b))| (y con espejo
    a + b); se toma el mayor y se reporta el desfase aprendido.
    """
    d = df.select("Tilt", "SpinAxis").drop_nulls()
    if d.height < 10:
        return {"cumplimiento": None, "n": d.height}
    a = np.radians(_tilt_a_grados(d["Tilt"].cast(pl.Utf8)))
    b = np.radians(d["SpinAxis"].to_numpy())
    ok = ~np.isnan(a)
    a, b = a[ok], b[ok]
    z_dir, z_esp = np.mean(np.exp(1j * (a - b))), np.mean(np.exp(1j * (a + b)))
    espejo = abs(z_esp) > abs(z_dir)
    z = z_esp if espejo else z_dir
    r = float(abs(z))
    return {"cumplimiento": 1.0 if r > minimo else 0.0, "n": len(a), "R": r,
            "espejo": bool(espejo), "desfase_grados": float(np.degrees(np.angle(z)) % 360.0),
            "minimo": minimo, "tilt_no_parseables": int((~ok).sum())}


def i6p_flags(df: pl.DataFrame, contacto: list[str]) -> dict:
    """I6′: is_swing = is_whiff + is_contact, e is_contact ⇔ pitch_call_h ∈ {Foul, InPlay}.

    Exacta, sin las filas `Undefined`. Se reporta aparte cada mitad y la implicación vieja
    is_whiff ⇒ PitchCall = StrikeSwinging.
    """
    d = df.filter(pl.col("pitch_call_h").cast(pl.Utf8) != "Undefined").select(
        "is_swing", "is_whiff", "is_contact", "pitch_call_h", "PitchCall").drop_nulls()
    sw, wh, co = (d[c].cast(pl.Int64) for c in ("is_swing", "is_whiff", "is_contact"))
    suma = sw == (wh + co)
    cont = (co == 1) == d["pitch_call_h"].cast(pl.Utf8).is_in(contacto)
    whiff = (wh == 0) | (d["PitchCall"].cast(pl.Utf8) == "StrikeSwinging")
    return _res(int((suma & cont).sum()), d.height,
                suma=float(suma.mean()) if d.height else None,
                contacto_equivale_a_foul_o_inplay=float(cont.mean()) if d.height else None,
                whiff_implica_strike_swinging=float(whiff.mean()) if d.height else None)


def i7_outs_media_entrada(df: pl.DataFrame, esperado: int = 3) -> dict:
    """I7: Σ OutsOnPlay por media entrada = 3. Cumplimiento = % de medias entradas.

    Se reporta también sin la última media entrada de cada juego (candidata a quedar
    incompleta: out final no jugado, walk-off).
    """
    g = (df.filter(pl.col("game_anon_id").is_not_null())
         .group_by("game_anon_id", "Inning", pl.col("Top/Bottom").cast(pl.Utf8).alias("mitad"))
         .agg(pl.col("OutsOnPlay").cast(pl.Float64).sum().alias("outs")))
    if g.height == 0:
        return {"cumplimiento": None, "n": 0}
    ok = g["outs"] == esperado
    orden = g.with_columns((pl.col("Inning") * 2 + (pl.col("mitad") == "Bottom").cast(pl.Int64)).alias("_o"))
    ultima = orden.group_by("game_anon_id").agg(pl.col("_o").max().alias("_max"))
    orden = orden.join(ultima, on="game_anon_id").filter(pl.col("_o") < pl.col("_max"))
    sin_ultima = orden["outs"] == esperado
    return _res(int(ok.sum()), g.height,
                sin_ultima_media_entrada=float(sin_ultima.mean()) if orden.height else None,
                n_sin_ultima=int(orden.height),
                distribucion_outs={str(int(k)): int(v) for k, v in
                                   g.group_by("outs").len().sort("outs").iter_rows()})


def i8_signo_horzbreak(df: pl.DataFrame, min_filas: int = 50) -> dict:
    """I8: el signo de HorzBreak se invierte con PitcherThrows para el mismo AutoPitchType.

    Cumplimiento = fracción de tipos (con >= `min_filas` por mano) donde las medias tienen
    signo opuesto. Usa la mano CRUDA definida (Left/Right): no depende de ADR-003.
    """
    d = df.filter(pl.col("PitcherThrows").cast(pl.Utf8).is_in(["Left", "Right"])).select(
        pl.col("AutoPitchType").cast(pl.Utf8).alias("tipo"),
        pl.col("PitcherThrows").cast(pl.Utf8).alias("mano"), "HorzBreak").drop_nulls()
    g = d.group_by("tipo", "mano").agg(pl.col("HorzBreak").mean().alias("m"), pl.len().alias("n"))
    tipos, ok_n = {}, 0
    for tipo in g["tipo"].unique().sort():
        s = g.filter(pl.col("tipo") == tipo)
        r, left = s.filter(pl.col("mano") == "Right"), s.filter(pl.col("mano") == "Left")
        if r.height == 0 or left.height == 0 or r["n"][0] < min_filas or left["n"][0] < min_filas:
            tipos[tipo] = {"evaluado": False}
            continue
        mr, ml = float(r["m"][0]), float(left["m"][0])
        opuesto = mr * ml < 0
        ok_n += int(opuesto)
        tipos[tipo] = {"evaluado": True, "media_derecho": mr, "media_zurdo": ml, "signo_opuesto": bool(opuesto)}
    n = sum(1 for v in tipos.values() if v["evaluado"])
    return _res(ok_n, n, tipos=tipos)


def i9_altitud_constante(df: pl.DataFrame) -> dict:
    """I9: altitude_category constante dentro de cada game_anon_id (100 % de los juegos con cubeta)."""
    g = (df.filter(pl.col("game_anon_id").is_not_null() & pl.col("altitude_category").is_not_null())
         .group_by("game_anon_id")
         .agg(pl.col("altitude_category").cast(pl.Utf8).n_unique().alias("k")))
    return _res(int((g["k"] == 1).sum()), g.height, juegos_incoherentes=int((g["k"] > 1).sum()))


def i10_outs_validos(df: pl.DataFrame, validos: list[int] | None = None) -> dict:
    """I10: Outs ∈ {0,1,2}. Se reporta el conteo de violaciones."""
    validos = [float(v) for v in (validos or [0, 1, 2])]
    o = df["Outs"].cast(pl.Float64)
    ok = o.is_in(validos).fill_null(False)
    malos = df.filter(~ok).select(o.filter(~ok).alias("v"))
    return _res(int(ok.sum()), df.height, violaciones=int((~ok).sum()),
                valores_invalidos={("nulo" if k is None or (isinstance(k, float) and math.isnan(k)) else str(k)): int(v)
                                   for k, v in malos.group_by("v").len().iter_rows()})


def correr_qa(df: pl.DataFrame, cat: dict, qa: dict) -> dict:
    """Todas las identidades de F0 sobre el DataFrame limpio."""
    return {
        "I1": i1_speeddrop(df, qa["i1_tol_mph"]),
        "I2": i2_conteo(df),
        "I3": i3_polinomio(df, qa["i3_rtol"], qa["i3_piso"]),
        "I4": i4_gravedad(df, tuple(qa["i4_pendiente"])),
        "I5": i5_tilt_spinaxis(df, qa["i5_min"]),
        "I6p": i6p_flags(df, cat["pitch_call_h"]["contacto"]),
        "I7": i7_outs_media_entrada(df, qa["i7_outs_por_media_entrada"]),
        "I8": i8_signo_horzbreak(df, qa["i8_min_filas"]),
        "I9": i9_altitud_constante(df),
        "I10": i10_outs_validos(df, cat["outs_validos"]),
    }
