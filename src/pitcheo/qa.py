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

import itertools
import math
import warnings

import numpy as np
import polars as pl

from .fisica import Y_FRENTE_PLATO_FT, calibrar_plano_y_signo
from .limpieza import tabla_medias_entradas

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
            "tolerancia_relativa": rtol, "piso": piso, "sustituida_por": "G0.2 (ADR-010 enmendado)"}


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


def i7_outs_media_entrada(df: pl.DataFrame, esperado: int = 3, inconsistente: int = 4) -> dict:
    """I7: Σ OutsOnPlay por media entrada = 3. `cumplimiento` = criterio A (estricto) sobre TODAS.

    ADR-012: se reportan además el criterio A sobre las no finales y el **criterio B** (amplio: hay
    estado previo Outs = 2 y existe una media entrada posterior) sobre las no finales, que es el que
    evalúa G0.3. Las de >= `inconsistente` outs se cuentan aparte y se excluyen de A y de B.
    """
    t = tabla_medias_entradas(df, inconsistente)
    if t.height == 0:
        return {"cumplimiento": None, "n": 0}
    no_fin = t.filter(~pl.col("final"))
    return _res(int(t["A"].sum()), t.height,
                sin_ultima_media_entrada=float(no_fin["A"].mean()) if no_fin.height else None,
                n_sin_ultima=int(no_fin.height),
                B_no_finales=float(no_fin["B"].mean()) if no_fin.height else None,
                inconsistentes=int((t["outs"] >= inconsistente).sum()),
                distribucion_outs={str(int(k)): int(v) for k, v in
                                   t.group_by("outs").len().sort("outs").iter_rows()})


def i8_signo_horzbreak(df: pl.DataFrame, min_filas: int = 50, mediana_min_in: float = 2.0) -> dict:
    """I8: el signo de HorzBreak se invierte con PitcherThrows para el mismo AutoPitchType.

    Cumplimiento = fracción de tipos (con >= `min_filas` por mano) donde las medias tienen
    signo opuesto. Usa la mano CRUDA definida (Left/Right): no depende de ADR-003.

    v2.6: para cada tipo que FALLA se reporta la mediana de |HorzBreak| por mano; si alguna es menor que
    `mediana_min_in` (2 in) el tipo casi no rompe en horizontal, el signo de su media es ruido y la falla se marca
    `no_informativo`. No cambia el cumplimiento; solo dice cuántas de las fallas son informativas.
    """
    d = df.filter(pl.col("PitcherThrows").cast(pl.Utf8).is_in(["Left", "Right"])).select(
        pl.col("AutoPitchType").cast(pl.Utf8).alias("tipo"),
        pl.col("PitcherThrows").cast(pl.Utf8).alias("mano"), "HorzBreak").drop_nulls()
    g = d.group_by("tipo", "mano").agg(pl.col("HorzBreak").mean().alias("m"),
                                       pl.col("HorzBreak").abs().median().alias("mediana_abs"), pl.len().alias("n"))
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
        info = {"evaluado": True, "media_derecho": mr, "media_zurdo": ml, "signo_opuesto": bool(opuesto)}
        if not opuesto:
            md, mz = float(r["mediana_abs"][0]), float(left["mediana_abs"][0])
            info |= {"mediana_abs_derecho_in": md, "mediana_abs_zurdo_in": mz,
                     "no_informativo": bool(min(md, mz) < mediana_min_in)}
        tipos[tipo] = info
    n = sum(1 for v in tipos.values() if v["evaluado"])
    fallas = [t for t, v in tipos.items() if v.get("evaluado") and not v["signo_opuesto"]]
    return _res(ok_n, n, tipos=tipos, mediana_min_in=mediana_min_in, fallas=fallas,
                fallas_no_informativas=[t for t in fallas if tipos[t]["no_informativo"]])


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
        "I7": i7_outs_media_entrada(df, qa["i7_outs_por_media_entrada"], cat.get("outs_inconsistente", 4)),
        "I8": i8_signo_horzbreak(df, qa["i8_min_filas"], qa.get("i8_mediana_min_in", 2.0)),
        "I9": i9_altitud_constante(df),
        "I10": i10_outs_validos(df, cat["outs_validos"]),
    }


# --------------------------------------------------------------------------
# ADR-010 — ejes de los polinomios de trayectoria vs. los 9P
# --------------------------------------------------------------------------
_POLI = ("X", "Y", "Z")
_NUEVE = {"c2": ("ax0", "ay0", "az0"), "c1": ("vx0", "vy0", "vz0"), "c0": ("x0", "y0", "z0")}
_EJES = ("x", "y", "z")


def _corr_cruzada(y: np.ndarray, x: np.ndarray) -> dict:
    """Matriz 3×3 de regresiones simples y_P ~ a + b·x_q: pendiente, intercepto y R² (filas P, columnas q)."""
    out: dict = {}
    mx, my = x.mean(axis=0), y.mean(axis=0)
    xc, yc = x - mx, y - my
    sxx, syy = (xc**2).sum(axis=0), (yc**2).sum(axis=0)
    sxy = yc.T @ xc  # (P, q)
    for i, p in enumerate(_POLI):
        out[p] = {}
        for j, q in enumerate(_EJES):
            if sxx[j] <= 0 or syy[i] <= 0:
                out[p][q] = {"pendiente": None, "intercepto": None, "r2": None}
                continue
            b = sxy[i, j] / sxx[j]
            out[p][q] = {"pendiente": float(b), "intercepto": float(my[i] - b * mx[j]),
                         "r2": float(sxy[i, j] ** 2 / (sxx[j] * syy[i]))}
    return out


def _regresion_conjunta(y: np.ndarray, x: np.ndarray) -> dict:
    """y_P ~ a + x_x + x_y + x_z (por eje P): coeficientes y R². Detecta un marco rotado."""
    a = np.hstack([np.ones((x.shape[0], 1)), x])
    out = {}
    for i, p in enumerate(_POLI):
        coef, *_ = np.linalg.lstsq(a, y[:, i], rcond=None)
        resid = y[:, i] - a @ coef
        tot = ((y[:, i] - y[:, i].mean()) ** 2).sum()
        out[p] = {"intercepto": float(coef[0]), "coef_xyz": [float(c) for c in coef[1:]],
                  "r2": float(1 - (resid**2).sum() / tot) if tot > 0 else None}
    return out


def _regresion_simple(x: np.ndarray, y: np.ndarray) -> dict:
    xc, yc = x - x.mean(), y - y.mean()
    sxx, syy, sxy = float(xc @ xc), float(yc @ yc), float(xc @ yc)
    if sxx <= 0 or syy <= 0:
        return {"r2": None, "pendiente": None, "intercepto": None}
    b = sxy / sxx
    return {"r2": sxy**2 / (sxx * syy), "pendiente": b, "intercepto": float(y.mean() - b * x.mean())}


def _estad_ts(ts: np.ndarray) -> dict:
    ts = ts[np.isfinite(ts)]
    if ts.size == 0:
        return {"n": 0}
    q = np.quantile(ts, [0.01, 0.25, 0.5, 0.75, 0.99])
    return {"n": int(ts.size), "mediana_s": float(q[2]), "rango_intercuartil_s": float(q[3] - q[1]),
            "p1_s": float(q[0]), "p99_s": float(q[4])}


def t_s_por_lanzamiento(df: pl.DataFrame, pol: dict, piso: float = 1.0) -> np.ndarray:
    """t_s por lanzamiento = (s·c1_X − v0)/a0 con el eje 9P al que corresponde el eje X del polinomio.

    Alineado con las filas de `df` (NaN si hay nulos o |a0| <= piso). Solo tiene sentido si ADR-010 los
    reconoce como equivalentes (`pol["existe"]`).
    """
    q = pol["permutacion"]["X"]
    v, a = {"x": "vx0", "y": "vy0", "z": "vz0"}[q], {"x": "ax0", "y": "ay0", "z": "az0"}[q]
    c1, v0, a0 = (df[c].cast(pl.Float64).to_numpy() for c in ("PitchTrajectoryXc1", v, a))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.abs(a0) > piso, (pol["signos"]["X"] * c1 - v0) / a0, np.nan)


def matriz_polinomios(df: pl.DataFrame, r2_c2_min: float = 0.9999, r2_c1_min: float = 0.999,
                      piso: float = 1.0) -> dict:
    """ADR-010 (enmienda v2.5): ¿los polinomios PitchTrajectory{X,Y,Z}c{0,1,2} son los 9P en otros ejes?

    1. Matriz 3×3 de regresiones (pendiente, intercepto, R²) de c2 sobre a0, c1 sobre v0 y c0 sobre r0,
       más la regresión conjunta (cada eje del polinomio sobre los tres de los 9P).
    2. La permutación con signo se elige con **c2**, que NO depende del origen de tiempo (v2.4 la elegía
       con c1 también y, al ignorar el desfase, la rechazó).
    3. Si el polinomio arranca en t_s (la liberación), c1 = v0 + a·t_s y c0 = r0 + v0·t_s + ½·a·t_s²:
       t_s por lanzamiento = (s·c1_X − v0)/a0 y se regresa c1 de cada eje sobre (v0 + a0·t_s).
       El eje de referencia (X) sale 1 por construcción; Y y Z son la prueba independiente.
    Decisión: `equivalentes` si c2 (por pares y conjunta) ≥ `r2_c2_min` y c1 con t_s ≥ `r2_c1_min` en los
    tres ejes; si no, `no_canonicos`. La trayectoria canónica sigue siendo la de los 9P.
    """
    cols = [f"PitchTrajectory{p}c{k}" for k in (0, 1, 2) for p in _POLI] + \
           [c for fam in _NUEVE.values() for c in fam]
    d = df.select(cols).drop_nulls()
    if d.height < 100:
        return {"n": d.height, "existe": False, "decision": "sin_datos_suficientes"}
    arr = {fam: (d.select([f"PitchTrajectory{p}{fam}" for p in _POLI]).to_numpy().astype(float),
                 d.select(list(_NUEVE[fam])).to_numpy().astype(float)) for fam in _NUEVE}
    matriz = {fam: _corr_cruzada(*arr[fam]) for fam in _NUEVE}
    rotacion = {fam: _regresion_conjunta(*arr[fam]) for fam in _NUEVE}

    def r2(fam: str, p: str, q: str) -> float:
        v = matriz[fam][p][q]["r2"]
        return -1.0 if v is None else v

    mejor, mejor_score = None, -2.0
    for perm in itertools.permutations(range(3)):
        score = min(r2("c2", p, _EJES[perm[i]]) for i, p in enumerate(_POLI))
        if score > mejor_score:
            mejor, mejor_score = perm, score
    asignacion = {p: _EJES[mejor[i]] for i, p in enumerate(_POLI)}
    signos = {p: (1 if (matriz["c2"][p][asignacion[p]]["pendiente"] or 0) >= 0 else -1) for p in _POLI}
    escala = {p: (None if matriz["c2"][p][asignacion[p]]["pendiente"] is None
                  else abs(2 * matriz["c2"][p][asignacion[p]]["pendiente"])) for p in _POLI}

    # t_s por lanzamiento desde el eje de referencia X, y c1 ajustado con t_s en cada eje.
    q0 = _EJES.index(asignacion["X"])
    v0_ref, a0_ref = arr["c1"][1][:, q0], arr["c2"][1][:, q0]
    ok = np.abs(a0_ref) > piso
    ts = np.full(d.height, np.nan)
    ts[ok] = (signos["X"] * arr["c1"][0][ok, 0] - v0_ref[ok]) / a0_ref[ok]
    c1_con_ts, c1_sin_ts, ts_por_eje = {}, {}, {}
    for i, p in enumerate(_POLI):
        j = _EJES.index(asignacion[p])
        v0, a0 = arr["c1"][1][:, j], arr["c2"][1][:, j]
        c1_p = arr["c1"][0][:, i]
        reg = _regresion_simple((v0 + a0 * np.nan_to_num(ts))[ok], c1_p[ok])
        c1_con_ts[p] = {**reg, "referencia": p == "X"}
        c1_sin_ts[p] = matriz["c1"][p][asignacion[p]]
        oki = np.abs(a0) > piso
        ts_por_eje[p] = float(np.median((signos[p] * c1_p[oki] - v0[oki]) / a0[oki])) if oki.any() else None

    r2_pares = float(mejor_score)
    r2_conj = min((rotacion["c2"][p]["r2"] or -1.0) for p in _POLI)
    r2_c1 = min((c1_con_ts[p]["r2"] or -1.0) for p in _POLI)
    existe = r2_pares >= r2_c2_min and r2_conj >= r2_c2_min and r2_c1 >= r2_c1_min
    return {
        "n": int(d.height), "matriz": matriz, "rotacion": rotacion,
        "r2_exigidos": {"c2": r2_c2_min, "c1_con_ts": r2_c1_min},
        "permutacion": asignacion, "signos": signos, "escala_2c2_sobre_a0": escala,
        "r2_c2_pares_min": r2_pares, "r2_c2_conjunta_min": float(r2_conj), "r2_c1_con_ts_min": float(r2_c1),
        "c1_con_ts": c1_con_ts, "c1_sin_ts": c1_sin_ts,
        "t_s": _estad_ts(ts), "t_s_mediana_por_eje": ts_por_eje,
        "existe": bool(existe), "decision": "equivalentes" if existe else "no_canonicos",
    }


# --------------------------------------------------------------------------
# ADR-011 — banderas is_* del organizador contra pitch_call_h (verificación cruzada)
# --------------------------------------------------------------------------
def discrepancias_flags(df: pl.DataFrame, cat: dict) -> dict:
    """Cada combinación (columna derivada de pitch_call_h) × (bandera del organizador) con su n.

    El árbol de desenlaces se define desde `pitch_call_h` (partición exacta por construcción);
    las `is_*` solo se contrastan aquí. Se desglosa por `pitch_call_h` para ver QUÉ llamadas
    marcan distinto. Agregado: nunca filas por lanzamiento.
    """
    d = df.filter(pl.col("pitch_call_h").cast(pl.Utf8) != "Undefined")
    pares = dict(cat["desenlace"]["contraste"])
    pares["es_hbp"] = "is_hit_by_pitch"
    d = d.with_columns((pl.col("pitch_call_h").cast(pl.Utf8) == "HitByPitch").alias("es_hbp"))
    out: dict = {}
    for col, flag in pares.items():
        t = (d.group_by(col, flag, pl.col("pitch_call_h").cast(pl.Utf8).alias("pitch_call_h"))
             .agg(pl.len().alias("n")).sort("n", descending=True))
        filas = [{"derivada": col, "derivada_valor": r[col], "bandera": flag, "bandera_valor": r[flag],
                  "pitch_call_h": r["pitch_call_h"], "n": int(r["n"])} for r in t.iter_rows(named=True)]
        discrep = sum(f["n"] for f in filas if f["derivada_valor"] != f["bandera_valor"])
        out[col] = {"bandera": flag, "n": int(d.height), "discrepantes": int(discrep),
                    "pct_discrepantes": round(100.0 * discrep / d.height, 4) if d.height else None,
                    "tabla": filas}
    return out


_EV_OUT = ["K", "OUT_BIP", "SAC"]
_EV_BASE = ["1B", "2B", "3B", "BB", "HBP", "ROE"]        # N_h (Prop. 16): turnos que dejan al bateador en base
_CUBETA_SIN = "(sin cubeta)"


def _medias_con_eventos(df: pl.DataFrame, inconsistente: int = 4) -> pl.DataFrame:
    """Una fila por media entrada con outs, eventos terminales, turnos incompletos, año y cubeta.

    No hay orden de lanzamientos: un turno es **incompleto** si hay lanzamientos de un bateador (con id) de
    la media entrada y ninguno trae evento terminal. La cubeta es la imputada por juego (ADR-005). Además de los
    conteos por evento trae el resumen de la columna `Outs` (estado previo): mínimo, máximo, valores distintos y si
    hay un out terminal con `Outs` = 2 (corroboración (b) de ADR-016).
    """
    t = tabla_medias_entradas(df, inconsistente)
    claves = ["game_anon_id", "Inning", "mitad"]
    d = df.filter(pl.col("game_anon_id").is_not_null() & pl.col("Inning").is_not_null()).with_columns(
        pl.col("Top/Bottom").cast(pl.Utf8).alias("mitad"),
        pl.col("evento_terminal").cast(pl.Utf8).alias("_ev"),
        pl.col("Outs").cast(pl.Float64).alias("_outs_prev"))
    por_media = d.group_by(*claves).agg(
        pl.col("_ev").is_not_null().sum().alias("n_terminales"),
        pl.col("_ev").is_in(_EV_OUT).sum().alias("outs_por_eventos"),
        *[(pl.col("_ev") == e).sum().alias(f"ev_{e}") for e in _EV_OUT + _EV_BASE],
        pl.col("_outs_prev").min().alias("outs_min"),
        pl.col("_outs_prev").max().alias("outs_max"),
        pl.col("_outs_prev").drop_nulls().n_unique().alias("outs_n_unicos"),
        ((pl.col("_outs_prev") == 2) & pl.col("_ev").is_in(_EV_OUT)).any().alias("out_con_outs2"))
    turnos = (d.filter(pl.col("batter_anon_id").is_not_null())
              .group_by(*claves, "batter_anon_id").agg(pl.col("_ev").is_not_null().any().alias("termina")))
    inc = turnos.group_by(*claves).agg((~pl.col("termina")).sum().alias("turnos_incompletos"))
    cubeta = pl.col("altitude_category_h").cast(pl.Utf8) if "altitude_category_h" in df.columns else \
        pl.col("altitude_category").cast(pl.Utf8)
    juego = (df.filter(pl.col("game_anon_id").is_not_null())
             .group_by("game_anon_id")
             .agg(pl.col("year").first().alias("year"),
                  cubeta.drop_nulls().first().fill_null(_CUBETA_SIN).alias("cubeta")))
    # Orden determinista: el group_by multihilo no garantiza el orden y el bootstrap con semilla fija remuestrea por
    # posición; sin esto el mismo `seed` daba intervalos distintos entre corridas.
    return (t.join(por_media, on=claves, how="left").join(inc, on=claves, how="left")
            .join(juego, on="game_anon_id", how="left")
            .with_columns(pl.col("turnos_incompletos").fill_null(0), pl.col("cubeta").fill_null(_CUBETA_SIN))
            .sort("game_anon_id", "Inning", "mitad"))


def _cuantiles(s: pl.Series) -> dict:
    return {"media": float(s.mean()), "mediana": float(s.median()),
            "p10": float(s.quantile(0.1)), "p90": float(s.quantile(0.9))} if s.len() else {}


# --------------------------------------------------------------------------
# ADR-012 / ADR-016 — diagnóstico de las medias entradas que terminan con 2 outs registrados
# --------------------------------------------------------------------------
def diagnostico_dos_outs(df: pl.DataFrame, inconsistente: int = 4, t: pl.DataFrame | None = None) -> dict:
    """¿Por qué el ~13 % de las medias entradas suma 2 outs registrados en vez de 3? (agregado, ADR-012 y 016).

    Contrasta tres candidatos: (1) tercer out en un evento sin lanzamiento propio (robo, pickoff): la media
    entrada deja un turno **incompleto**; (2) un turno de out cuyos lanzamientos faltan (L); (3) `OutsOnPlay` que
    no cuenta ciertos outs (U). Cada media entrada **no final** de 2 outs se clasifica en "turno incompleto" (hay un
    bateador con lanzamientos pero sin evento terminal) o **"out faltante (sin turno incompleto)"**: todos sus turnos
    terminan, así que falta un out que se perdió con su turno (L) o que `OutsOnPlay` no cuenta (U); ADR-016 los separa.
    `t` = tabla de `_medias_con_eventos` si ya se calculó.
    """
    t = _medias_con_eventos(df, inconsistente) if t is None else t

    def grupo(outs: int) -> dict:
        g = t.filter(pl.col("outs") == outs)
        if g.height == 0:
            return {"n": 0}
        dif = g["outs_por_eventos"] - g["outs"]
        return {
            "n": int(g.height),
            "pct_ultima_del_juego": round(100.0 * float(g["final"].mean()), 3),
            "lanzamientos_por_media_entrada": _cuantiles(g["n_lanz"].cast(pl.Float64)),
            "pct_con_turno_incompleto": round(100.0 * float((g["turnos_incompletos"] > 0).mean()), 3),
            "turnos_incompletos_media": float(g["turnos_incompletos"].mean()),
            # Si lo único que falta es un turno independiente del tipo de out, los ponches por out REGISTRADO
            # serían iguales en las de 2 y en las de 3 outs. Si no, son poblaciones distintas (ADR-016).
            "ponches_por_out_registrado": float(g["ev_K"].sum() / g["outs"].sum()) if g["outs"].sum() else None,
            "eventos_terminales_por_media_entrada": {
                e: round(float(g[f"ev_{e}"].mean()), 3) for e in _EV_OUT + ["BB", "HBP", "ROE"]},
            "outs_implicados_por_eventos_menos_OutsOnPlay": {
                str(int(k)): int(v) for k, v in dif.value_counts().sort(dif.name).iter_rows()},
        }

    dos_nf = t.filter((pl.col("outs") == 2) & ~pl.col("final"))
    n_inc = int((dos_nf["turnos_incompletos"] > 0).sum())
    n_falt = int(dos_nf.height - n_inc)
    tabla = (df.group_by(pl.col("evento_terminal").cast(pl.Utf8).fill_null("NO_TERMINAL").alias("evento"),
                         pl.col("OutsOnPlay").cast(pl.Int64).alias("OutsOnPlay"))
             .agg(pl.len().alias("n")).sort("evento", "OutsOnPlay"))
    return {
        "dos_outs": grupo(2), "tres_outs": grupo(3),
        "clasificacion_no_finales": {
            "n": int(dos_nf.height), "turno_incompleto": n_inc, "out_faltante": n_falt,
            "pct_turno_incompleto": round(100.0 * n_inc / dos_nf.height, 3) if dos_nf.height else None,
            "pct_out_faltante": round(100.0 * n_falt / dos_nf.height, 3) if dos_nf.height else None},
        "outs_on_play_x_evento_terminal": tabla.to_dicts(),
    }


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson para una proporción k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / den
    mitad = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return (max(0.0, centro - mitad), min(1.0, centro + mitad))


def _tasas(g: pl.DataFrame, claves: list[str]) -> list[dict]:
    """Tasas por grupo sobre medias entradas no finales: 2 outs, turno incompleto y out faltante (informativas)."""
    out = []
    for fila in (g.group_by(*claves).agg(
            pl.len().alias("n"), (pl.col("outs") == 2).sum().alias("dos_outs"),
            ((pl.col("outs") == 2) & (pl.col("turnos_incompletos") > 0)).sum().alias("incompleto"),
            ((pl.col("outs") == 2) & (pl.col("turnos_incompletos") == 0)).sum().alias("faltante"))
            .sort(*claves).iter_rows(named=True)):
        lo, hi = wilson(fila["faltante"], fila["n"])
        out.append({**{c: fila[c] for c in claves}, "medias_entradas": fila["n"], "dos_outs": fila["dos_outs"],
                    "turno_incompleto": fila["incompleto"], "out_faltante": fila["faltante"],
                    "tasa_dos_outs": fila["dos_outs"] / fila["n"],
                    "tasa_out_faltante": fila["faltante"] / fila["n"],
                    "ic95_wilson": [lo, hi]})
    return out


# --------------------------------------------------------------------------
# ADR-016 — conjunto T, Prop. 16 (identificación de la pérdida real), Prop. 17 (cota del sesgo) y reglas G0.8′/G0.9
# --------------------------------------------------------------------------
def conjunto_T(df: pl.DataFrame, inconsistente: int = 4,
               t: pl.DataFrame | None = None) -> tuple[pl.DataFrame, list[dict]]:
    """T = medias entradas no finales, `Inning` ≤ 9, consistentes (outs registrados ≤ 3) y sin turno incompleto.

    Devuelve (T, pasos). Cada media entrada de T trae `P` (outs registrados = 2), `N_h` (turnos que dejan al bateador
    en base: 1B, 2B, 3B, BB, HBP, ROE), `Z` (N_h = 0) y `PZ`. `pasos` dice cuántas excluye cada filtro, en cascada y
    aplicado solo.
    """
    t = (_medias_con_eventos(df, inconsistente) if t is None else t).with_columns(
        pl.sum_horizontal([pl.col(f"ev_{e}") for e in _EV_BASE]).alias("N_h"))
    filtros = {"no es la final del juego": ~pl.col("final"), "Inning ≤ 9": pl.col("Inning") <= 9,
               f"consistente (outs < {inconsistente})": pl.col("outs") < inconsistente,
               "sin turno incompleto": pl.col("turnos_incompletos") == 0}
    pasos = [{"filtro": "todas las medias entradas", "excluye": None, "excluye_solo_este": None, "quedan": t.height}]
    cur = t
    for nombre, expr in filtros.items():
        antes = cur.height
        cur = cur.filter(expr)
        pasos.append({"filtro": nombre, "excluye": antes - cur.height,
                      "excluye_solo_este": int(t.filter(~expr).height), "quedan": cur.height})
    T = cur.with_columns((pl.col("outs") == 2).alias("P"), (pl.col("N_h") == 0).alias("Z")).with_columns(
        (pl.col("P") & pl.col("Z")).alias("PZ"))
    return T, pasos


_COLS_SUMA = ["nT", "nP", "nZ", "nPZ", "turnos", "nK"]


def _por_juego(T: pl.DataFrame) -> pl.DataFrame:
    """Una fila por juego de T con los conteos que alimentan Prop. 16/17 (ordenada por juego: bootstrap reproducible)."""
    return (T.group_by("game_anon_id")
            .agg(pl.col("cubeta").first().alias("cubeta"), pl.len().alias("nT"), pl.col("P").sum().alias("nP"),
                 pl.col("Z").sum().alias("nZ"), pl.col("PZ").sum().alias("nPZ"),
                 pl.col("n_terminales").sum().alias("turnos"), pl.col("ev_K").sum().alias("nK"))
            .sort("game_anon_id"))


def _razones(s) -> dict:
    """f, p0, r̂ y θ̂ de Prop. 16 a partir de las sumas (nT, nP, nZ, nPZ, ...), escalares o arreglos (réplicas)."""
    nT, nP, nZ, nPZ = (np.asarray(s[i], float) for i in range(4))
    with np.errstate(divide="ignore", invalid="ignore"):
        f, p0 = nZ / nT, nPZ / nT
        r = np.where(nZ > 0, nPZ / np.where(nZ > 0, nZ, 1), np.nan)
        tasa_p = nP / nT
        theta = np.where(nP > 0, r / np.where(nP > 0, tasa_p, 1), np.nan)
    return {"f": f, "p0": p0, "r_hat": r, "tasa_P": tasa_p, "theta_hat": theta}


def _ic(x: np.ndarray) -> list | None:
    x = x[np.isfinite(x)]
    return [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))] if len(x) else None


def _num(v) -> float | None:
    v = float(v)
    return v if math.isfinite(v) else None


def prop16(T: pl.DataFrame, n_boot: int = 1000, seed: int = 2026) -> dict:
    """Prop. 16 por cubeta y global: f_b, p0_b, r̂_b = p0_b / f_b y θ̂_b = r̂_b / P(P | b), con IC95 por bootstrap de juegos.

    El bootstrap remuestrea juegos con reemplazo DENTRO de cada cubeta (la cubeta es constante por juego), así que cada
    réplica conserva el tamaño de cada cubeta; el global suma las réplicas de las cubetas. La tabla `J` va ordenada por
    juego y la semilla es la de config: el mismo dato da el mismo intervalo.
    """
    J = _por_juego(T)
    rng = np.random.default_rng(seed)
    obs, boot = {}, {}
    for cub in sorted(J["cubeta"].unique().to_list()):
        a = J.filter(pl.col("cubeta") == cub).select(_COLS_SUMA).to_numpy().astype(float)
        obs[cub] = a.sum(axis=0)
        idx = rng.integers(0, len(a), size=(n_boot, len(a)))
        boot[cub] = np.stack([a[:, j][idx].sum(axis=1) for j in range(a.shape[1])], axis=0)    # (6, B)
    obs["global"], boot["global"] = sum(obs.values()), sum(boot.values())

    def fila(nombre: str) -> dict:
        o, b = _razones(obs[nombre]), _razones(boot[nombre])
        s = obs[nombre]
        return {"cubeta": nombre, "medias_entradas": int(s[0]), "P": int(s[1]), "Z": int(s[2]), "PZ": int(s[3]),
                "turnos": int(s[4]), "m_tilde": _num(s[4] / s[0]) if s[0] else None, "ponches": int(s[5]),
                **{k: _num(v) for k, v in o.items()},
                "ic95": {k: _ic(v) for k, v in b.items() if k in ("f", "tasa_P", "r_hat", "theta_hat")}}

    return {"por_cubeta": [fila(c) for c in obs if c != "global"], "global": fila("global"),
            "juegos": J.height, "bootstrap": {"n": n_boot, "seed": seed, "unidad": "juego, dentro de cada cubeta"}}


def prop17(filas: list[dict], kappa_bar: float, cub_ext: str, cub_no: str, gammas=(1, 2)) -> dict:
    """Prop. 17: W(Γ) = Σ_{b ∈ {Extreme, No}} Γ·r̂_b / (m̃_b + Γ·r̂_b) y SE_ref = √(κ̄(1−κ̄)(1/n_Ext + 1/n_No)).

    `filas`: una por cubeta con `cubeta`, `r_hat`, `m_tilde` (turnos observados por media entrada de T_b) y `turnos`
    (n_b). κ̄ es la tasa GLOBAL de K por turno: una sola cifra. W es el ancho del conjunto identificado del contraste
    Extreme − No cuando la fracción de turnos perdidos con K recorre [0, 1] (Manski).
    """
    por = {f["cubeta"]: f for f in filas}
    try:
        e, n = por[cub_ext], por[cub_no]
        n_e, n_n = e["turnos"], n["turnos"]
        se = math.sqrt(kappa_bar * (1 - kappa_bar) * (1 / n_e + 1 / n_n))
        w = {}
        for g in gammas:
            partes = [g * f["r_hat"] / (f["m_tilde"] + g * f["r_hat"]) for f in (e, n)]
            w[str(g)] = float(sum(partes))
    except (KeyError, TypeError, ZeroDivisionError, ValueError):
        return {"evaluable": False, "cubeta_extrema": cub_ext, "cubeta_base": cub_no}
    return {"evaluable": True, "cubeta_extrema": cub_ext, "cubeta_base": cub_no, "kappa_bar": kappa_bar,
            "SE_ref": se, "n_extrema": n_e, "n_base": n_n, "W": w,
            "m_tilde": {cub_ext: e["m_tilde"], cub_no: n["m_tilde"]}, "r_hat": {cub_ext: e["r_hat"], cub_no: n["r_hat"]}}


def regla_g08p(p17: dict, k_ic: float = 3.92, k_ign: float = 1.0, gamma: str = "2") -> dict:
    """G0.8′: W(Γ=2) ≤ 3.92·SE_ref. Si además W(Γ=2) ≤ SE_ref → `perdida_ignorable` verdadera; si pasa sin eso, falsa
    (F8 reporta los contrastes con intervalo de Imbens-Manski). Si falla, es una discrepancia y no se sigue a F1."""
    if not p17.get("evaluable"):
        return {"ok": False, "perdida_ignorable": False, "motivo": "contraste Extreme − No no evaluable"}
    w, se = p17["W"][gamma], p17["SE_ref"]
    ok = w <= k_ic * se
    return {"ok": bool(ok), "perdida_ignorable": bool(ok and w <= k_ign * se), "W": w, "SE_ref": se,
            "W_sobre_SE_ref": w / se if se else None, "umbral_ic": k_ic, "umbral_ignorable": k_ign}


def regla_g09(theta_ic: list | None, u_max: float = 0.25, l_min: float = 0.50) -> str:
    """G0.9: U dominante si el IC95 superior de θ̂ ≤ 0.25; L dominante si el inferior ≥ 0.50; mezcla en otro caso."""
    if not theta_ic:
        return "mezcla"
    lo, hi = theta_ic
    return "U" if hi <= u_max else ("L" if lo >= l_min else "mezcla")


# --------------------------------------------------------------------------
# ADR-016 — corroboraciones (a)-(e): informativas, no son compuertas
# --------------------------------------------------------------------------
def _pct_wilson(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"n": int(n), "k": int(k), "pct": round(100.0 * k / n, 3) if n else None,
            "ic95_wilson_pct": [round(100 * lo, 3), round(100 * hi, 3)] if n else None}


def corr_a_rodados(df: pl.DataFrame, T: pl.DataFrame) -> dict:
    """(a) % de rodados entre los OUT_BIP con `Outs` previo ∈ {0, 1}: P vs. T∖P.

    Rodado = `hit_type` GroundBall; si esa categoría no existe, `Angle` < 10°. Con doble matanza no contada (U) se
    espera que P tenga MÁS rodados; con un turno perdido (L), la misma mezcla que T∖P.
    """
    hit = df["hit_type"].cast(pl.Utf8) if "hit_type" in df.columns else pl.Series([], dtype=pl.Utf8)
    hay = "GroundBall" in set(hit.drop_nulls().unique().to_list())
    rodado = (pl.col("hit_type").cast(pl.Utf8) == "GroundBall") if hay else (pl.col("Angle") < 10)
    claves = ["game_anon_id", "Inning", "mitad"]
    d = (df.filter((pl.col("evento_terminal").cast(pl.Utf8) == "OUT_BIP")
                   & pl.col("Outs").cast(pl.Float64).is_in([0.0, 1.0]))
         .with_columns(pl.col("Top/Bottom").cast(pl.Utf8).alias("mitad"), rodado.alias("_rod"))
         .filter(pl.col("_rod").is_not_null())
         .join(T.select(*claves, "P"), on=claves, how="inner"))
    out = {"definicion": "hit_type == GroundBall" if hay else "Angle < 10°"}
    for nombre, valor in (("P", True), ("T_menos_P", False)):
        g = d.filter(pl.col("P") == valor)
        out[nombre] = _pct_wilson(int(g["_rod"].sum()), g.height)
    return out


def corr_b_outs_previo(T: pl.DataFrame) -> dict:
    """(b) Columna `Outs` (estado previo), P vs. T∖P: % con mínimo `Outs` > 0 (faltan los primeros turnos), % con un
    out terminal en un lanzamiento con `Outs` = 2 y % con un hueco en los valores de `Outs`.

    U no quita lanzamientos: `Outs` previo es continuo y empieza en 0. L sí: deja huecos o arranca en 1.
    """
    t = T.with_columns(
        (pl.col("outs_min") > 0).fill_null(False).alias("_min"),
        (pl.col("outs_n_unicos") < (pl.col("outs_max") - pl.col("outs_min") + 1)).fill_null(False).alias("_hueco"))
    out = {}
    for nombre, valor in (("P", True), ("T_menos_P", False)):
        g = t.filter(pl.col("P") == valor)
        out[nombre] = {"n": g.height,
                       "pct_min_outs_mayor_0": _pct_wilson(int(g["_min"].sum()), g.height)["pct"],
                       "pct_out_con_estado_2": _pct_wilson(int(g["out_con_outs2"].sum()), g.height)["pct"],
                       "pct_hueco_en_outs": _pct_wilson(int(g["_hueco"].sum()), g.height)["pct"]}
    return out


def corr_c_logit(T: pl.DataFrame, cub_base: str, tope_n: int = 5) -> dict:
    """(c) Logit de 1[h ∈ P] sobre cubeta + año, sin y con factor(min(N_h, 5)); errores agrupados por juego.

    OR de cada cubeta contra la base con IC95. Si el OR por cubeta cae al controlar por N_h, la diferencia entre
    cubetas es tráfico de corredores (U); si sigue igual, no lo es. Excluye las medias entradas sin cubeta.
    """
    import pandas as pd
    import statsmodels.api as sm
    from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationError

    d = T.filter(pl.col("cubeta") != _CUBETA_SIN).select("game_anon_id", "cubeta", "year", "N_h", "P").to_pandas()
    if d["cubeta"].nunique() < 2 or cub_base not in set(d["cubeta"]):
        return {"error": "menos de dos cubetas o falta la base"}
    grupos = pd.factorize(d["game_anon_id"])[0]

    def ajustar(con_n: bool) -> dict:
        partes = [pd.get_dummies(d["cubeta"].astype(str), prefix="cubeta", dtype=float).drop(columns=f"cubeta_{cub_base}"),
                  pd.get_dummies(d["year"].astype(str), prefix="year", dtype=float).iloc[:, 1:]]
        if con_n:
            partes.append(pd.get_dummies(np.minimum(d["N_h"], tope_n).astype(int).astype(str), prefix="N",
                                         dtype=float).iloc[:, 1:])
        X = sm.add_constant(pd.concat(partes, axis=1))
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            try:
                r = sm.Logit(d["P"].astype(float), X).fit(disp=0, maxiter=200, cov_type="cluster",
                                                          cov_kwds={"groups": grupos})
            except (PerfectSeparationError, np.linalg.LinAlgError, ValueError) as e:   # separación, matriz singular...
                return {"error": f"{type(e).__name__}: {str(e)[:160]}"}
        ci = r.conf_int()
        ors = {c.removeprefix("cubeta_"): {"OR": float(np.exp(r.params[c])),
                                           "ic95": [float(np.exp(ci.loc[c, 0])), float(np.exp(ci.loc[c, 1]))]}
               for c in r.params.index if c.startswith("cubeta_")}
        ors["convergio"] = bool(r.mle_retvals.get("converged", True)) and not any(
            issubclass(a.category, ConvergenceWarning) for a in avisos)
        return ors

    return {"base": cub_base, "n": len(d), "sin_N_h": ajustar(False), "con_N_h": ajustar(True)}


def corr_d_dobles(df: pl.DataFrame, ref_por_juego: float = 1.63) -> dict:
    """(d) Jugadas con `OutsOnPlay` ≥ 2 por evento, junto al número de dobles matanzas esperado a la tasa MLB de
    referencia (1.63 por juego; solo referencia). `fraccion_registrada` baja si `OutsOnPlay` no las cuenta (U)."""
    d = df.filter(pl.col("OutsOnPlay").cast(pl.Int64) >= 2)
    juegos = int(df["game_anon_id"].drop_nulls().n_unique())
    esperadas = ref_por_juego * juegos
    tabla = (d.group_by(pl.col("evento_terminal").cast(pl.Utf8).fill_null("NO_TERMINAL").alias("evento"),
                        pl.col("OutsOnPlay").cast(pl.Int64).alias("OutsOnPlay"))
             .agg(pl.len().alias("n")).sort("evento", "OutsOnPlay"))
    return {"por_evento": tabla.to_dicts(), "jugadas_con_2_o_mas_outs": int(d.height), "juegos": juegos,
            "tasa_mlb_ref_por_juego": ref_por_juego, "dobles_matanzas_esperadas_ref": esperadas,
            "fraccion_registrada": (d.height / esperadas) if esperadas else None}


def corr_e_poisson(T: pl.DataFrame) -> dict:
    """(e) |P| por juego de T contra una Poisson con la misma media: histograma, dispersión de Pearson φ y P(≥1), P(>2).

    Un evento de juego a tasa constante (doble matanza no contada) da φ ≈ 1; una falla del sensor u operador se
    concentra en algunos juegos (φ ≫ 1). Solo conteos de juegos: nada por lanzamiento.
    """
    from scipy.stats import poisson

    m = _por_juego(T)["nP"].to_numpy().astype(float)
    n = len(m)
    if n < 2 or m.mean() <= 0:
        return {"juegos": n, "lambda": float(m.mean()) if n else None}
    lam = float(m.mean())
    ks = np.arange(0, int(m.max()) + 1)
    return {"juegos": n, "lambda": lam, "varianza": float(m.var(ddof=1)),
            "dispersion_phi": float(np.sum((m - lam) ** 2 / lam) / (n - 1)),
            "P_ge1": {"observado": float(np.mean(m >= 1)), "poisson": float(1 - poisson.pmf(0, lam))},
            "P_gt2": {"observado": float(np.mean(m > 2)), "poisson": float(1 - poisson.cdf(2, lam))},
            "histograma": [{"k": int(k), "juegos": int(np.sum(m == k)), "esperados_poisson": float(n * poisson.pmf(k, lam))}
                           for k in ks]}


def _deficits(tres: pl.DataFrame, dos: pl.DataFrame, n_boot: int, seed: int) -> dict:
    """Déficit de eventos K, OUT_BIP y SAC por media entrada (3 outs menos 2 outs), IC95 por bootstrap. Informativo."""
    rng = np.random.default_rng(seed)
    a3 = {e: tres[f"ev_{e}"].to_numpy().astype(float) for e in _EV_OUT}
    a2 = {e: dos[f"ev_{e}"].to_numpy().astype(float) for e in _EV_OUT}
    if len(a3["K"]) == 0 or len(a2["K"]) == 0:
        return {"n_dos": int(dos.height), "n_tres": int(tres.height)}
    d0 = {e: a3[e].mean() - a2[e].mean() for e in _EV_OUT}
    bs = {e: [] for e in _EV_OUT}
    for _ in range(n_boot):
        i3, i2 = rng.integers(0, len(a3["K"]), len(a3["K"])), rng.integers(0, len(a2["K"]), len(a2["K"]))
        for e in _EV_OUT:
            bs[e].append(a3[e][i3].mean() - a2[e][i2].mean())
    return {"n_dos": int(dos.height), "n_tres": int(tres.height),
            "deficit": {e: {"estimado": float(d0[e]), "ic95": _ic(np.array(bs[e]))} for e in _EV_OUT}}


def mecanismo_outs(df: pl.DataFrame, qa: dict, gates: dict, inconsistente: int = 4, seed: int = 2026,
                   t_all: pl.DataFrame | None = None) -> dict:
    """ADR-016 (ROADMAP §1.4): conjunto T, Prop. 16 y 17, G0.8′ y G0.9, corroboraciones (a)-(e) y tablas informativas.

    El umbral y las reglas vienen de `config/default.yaml` y son los fijados por el orquestador (no se ajustan).
    `perdida_ignorable` y `mecanismo` son lo que `--aplicar` escribe en `qa.perdida_ignorable` y `qa.mecanismo_outs`.
    """
    n_boot = int(qa.get("bootstrap_n", 1000))
    cub_ext, cub_no = qa.get("cubeta_extrema", "Extreme Altitude"), qa.get("cubeta_base", "No Altitude")
    t_all = _medias_con_eventos(df, inconsistente) if t_all is None else t_all
    T, pasos = conjunto_T(df, inconsistente, t_all)
    p16 = prop16(T, n_boot, seed)
    turnos, ponches = p16["global"]["turnos"], p16["global"]["ponches"]
    kappa = ponches / turnos if turnos else float("nan")
    p17 = prop17(p16["por_cubeta"], kappa, cub_ext, cub_no, tuple(qa.get("gammas", (1, 2))))
    g08 = regla_g08p(p17, gates.get("g08_k_ic", 3.92), gates.get("g08_k_ignorable", 1.0))
    theta_ic = p16["global"]["ic95"].get("theta_hat")
    mecanismo = regla_g09(theta_ic, gates.get("g09_u_max", 0.25), gates.get("g09_l_min", 0.50))

    # Informativas: la tasa de out faltante por cubeta (el antiguo G0.8) y los déficits (sin π̂_K, retirado en ADR-016).
    nf = t_all.filter(~pl.col("final"))
    por_cubeta = _tasas(nf, ["cubeta"])
    tasas = [100 * r["tasa_out_faltante"] for r in por_cubeta if r["cubeta"] != _CUBETA_SIN]
    tres = t_all.filter(pl.col("outs") == 3)
    dos = t_all.filter(pl.col("outs") == 2)
    return {
        "T": {"pasos": pasos, "medias_entradas": T.height, "P": int(T["P"].sum()), "Z": int(T["Z"].sum()),
              "PZ": int(T["PZ"].sum())},
        "prop16": p16, "prop17": p17,
        "G08p": {**g08, "regla": "W(Γ=2) ≤ 3.92·SE_ref; ignorable si W(Γ=2) ≤ SE_ref"},
        "G09": {"mecanismo": mecanismo, "theta_global": p16["global"]["theta_hat"], "ic95": theta_ic,
                "regla": "U si IC95 sup ≤ 0.25 · L si IC95 inf ≥ 0.50 · mezcla en otro caso"},
        "mecanismo_outs": mecanismo, "perdida_ignorable": bool(g08["perdida_ignorable"]),
        "corroboraciones": {
            "a_rodados": corr_a_rodados(df, T), "b_outs_previo": corr_b_outs_previo(T),
            "c_logit": corr_c_logit(T, cub_no), "d_dobles": corr_d_dobles(
                df, float(qa.get("dobles_matanzas_por_juego_ref", 1.63))), "e_poisson": corr_e_poisson(T)},
        "informativas": {
            "out_faltante_por_cubeta": por_cubeta, "out_faltante_por_cubeta_anio": _tasas(nf, ["cubeta", "year"]),
            "rango_pp": float(max(tasas) - min(tasas)) if len(tasas) >= 2 else None,
            "deficits_todas_las_de_2_outs": _deficits(tres, dos, n_boot, seed),
            "deficits_sin_turno_incompleto": _deficits(tres, dos.filter(pl.col("turnos_incompletos") == 0), n_boot, seed)},
    }


def correr_extras(df: pl.DataFrame, cat: dict, qa: dict, gates: dict | None = None, fis: dict | None = None,
                  seed: int = 2026) -> dict:
    """Diagnósticos de v2.4 a v2.6: ADR-010 (polinomios), ADR-011 (is_*), ADR-012/016 (2 outs y mecanismo de los
    outs faltantes) y ADR-014 (marco temporal de los 9P)."""
    gates, fis = gates or {}, fis or {}
    pol = matriz_polinomios(df, gates.get("g02_r2_c2_min", 0.9999), gates.get("g02_r2_c1_min", 0.999),
                            qa["poli_piso"])
    ts = t_s_por_lanzamiento(df, pol, qa["poli_piso"]) if pol.get("existe") else None
    inc = cat.get("outs_inconsistente", 4)
    t_all = _medias_con_eventos(df, inc)         # una sola vez: lo usan el diagnóstico de 2 outs y ADR-016
    return {
        "polinomios": pol,
        "calibracion_9p": calibrar_plano_y_signo(
            df, ts, tuple(fis.get("planos_candidatos_ft", (Y_FRENTE_PLATO_FT, 0.0))),
            tuple(fis.get("signos_candidatos", (1, -1)))),
        "discrepancias_flags": discrepancias_flags(df, cat),
        "dos_outs": diagnostico_dos_outs(df, inc, t_all),
        "mecanismo_outs": mecanismo_outs(df, qa, gates, inc, seed, t_all),
    }
