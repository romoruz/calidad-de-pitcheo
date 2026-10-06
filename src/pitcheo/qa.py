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
        "I7": i7_outs_media_entrada(df, qa["i7_outs_por_media_entrada"], cat.get("outs_inconsistente", 4)),
        "I8": i8_signo_horzbreak(df, qa["i8_min_filas"]),
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


# --------------------------------------------------------------------------
# ADR-012 — diagnóstico de las medias entradas que terminan con 2 outs
# --------------------------------------------------------------------------
def _cuantiles(s: pl.Series) -> dict:
    return {"media": float(s.mean()), "mediana": float(s.median()),
            "p10": float(s.quantile(0.1)), "p90": float(s.quantile(0.9))} if s.len() else {}


_EV_OUT = ["K", "OUT_BIP", "SAC"]


def _medias_con_eventos(df: pl.DataFrame, inconsistente: int = 4) -> pl.DataFrame:
    """Una fila por media entrada con outs, eventos terminales, turnos incompletos, año y cubeta.

    No hay orden de lanzamientos: un turno es **incompleto** si hay lanzamientos de un bateador (con id) de
    la media entrada y ninguno trae evento terminal. La cubeta es la imputada por juego (ADR-005).
    """
    t = tabla_medias_entradas(df, inconsistente)
    claves = ["game_anon_id", "Inning", "mitad"]
    d = df.filter(pl.col("game_anon_id").is_not_null() & pl.col("Inning").is_not_null()).with_columns(
        pl.col("Top/Bottom").cast(pl.Utf8).alias("mitad"),
        pl.col("evento_terminal").cast(pl.Utf8).alias("_ev"))
    por_media = d.group_by(*claves).agg(
        pl.col("_ev").is_not_null().sum().alias("n_terminales"),
        pl.col("_ev").is_in(_EV_OUT).sum().alias("outs_por_eventos"),
        *[(pl.col("_ev") == e).sum().alias(f"ev_{e}") for e in _EV_OUT + ["BB", "HBP", "ROE"]])
    turnos = (d.filter(pl.col("batter_anon_id").is_not_null())
              .group_by(*claves, "batter_anon_id").agg(pl.col("_ev").is_not_null().any().alias("termina")))
    inc = turnos.group_by(*claves).agg((~pl.col("termina")).sum().alias("turnos_incompletos"))
    cubeta = pl.col("altitude_category_h").cast(pl.Utf8) if "altitude_category_h" in df.columns else \
        pl.col("altitude_category").cast(pl.Utf8)
    juego = (df.filter(pl.col("game_anon_id").is_not_null())
             .group_by("game_anon_id")
             .agg(pl.col("year").first().alias("year"),
                  cubeta.drop_nulls().first().fill_null("(sin cubeta)").alias("cubeta")))
    # Orden determinista: el group_by multihilo no garantiza el orden y el bootstrap con semilla fija remuestrea por
    # posición; sin esto el mismo `seed` daba intervalos distintos entre corridas.
    return (t.join(por_media, on=claves, how="left").join(inc, on=claves, how="left")
            .join(juego, on="game_anon_id", how="left")
            .with_columns(pl.col("turnos_incompletos").fill_null(0), pl.col("cubeta").fill_null("(sin cubeta)"))
            .sort("game_anon_id", "Inning", "mitad"))


def diagnostico_dos_outs(df: pl.DataFrame, inconsistente: int = 4) -> dict:
    """¿Por qué el ~13 % de las medias entradas suma 2 outs en vez de 3? (agregado, ADR-012 y 015).

    Contrasta tres candidatos: (1) tercer out en un evento sin lanzamiento propio (robo, pickoff): la media
    entrada deja un turno **incompleto**; (2) **turno final perdido**: faltan todos los lanzamientos del
    último turno; (3) `OutsOnPlay` que no cuenta ciertos outs. ADR-015: cada media entrada **no final** de
    2 outs se clasifica en "turno incompleto" (hay un bateador con lanzamientos pero sin evento terminal) o
    "turno final perdido" (todos sus turnos terminan).
    """
    t = _medias_con_eventos(df, inconsistente)

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
            # Si lo único que falta es el último turno y los outs son intercambiables, los ponches por out
            # REGISTRADO serían iguales en las de 2 y en las de 3 outs. Si no, son poblaciones distintas.
            "ponches_por_out_registrado": float(g["ev_K"].sum() / g["outs"].sum()) if g["outs"].sum() else None,
            "eventos_terminales_por_media_entrada": {
                e: round(float(g[f"ev_{e}"].mean()), 3) for e in _EV_OUT + ["BB", "HBP", "ROE"]},
            "outs_implicados_por_eventos_menos_OutsOnPlay": {
                str(int(k)): int(v) for k, v in dif.value_counts().sort(dif.name).iter_rows()},
        }

    dos_nf = t.filter((pl.col("outs") == 2) & ~pl.col("final"))
    n_inc = int((dos_nf["turnos_incompletos"] > 0).sum())
    n_perd = int(dos_nf.height - n_inc)
    tabla = (df.group_by(pl.col("evento_terminal").cast(pl.Utf8).fill_null("NO_TERMINAL").alias("evento"),
                         pl.col("OutsOnPlay").cast(pl.Int64).alias("OutsOnPlay"))
             .agg(pl.len().alias("n")).sort("evento", "OutsOnPlay"))
    return {
        "dos_outs": grupo(2), "tres_outs": grupo(3),
        "clasificacion_no_finales": {
            "n": int(dos_nf.height), "turno_incompleto": n_inc, "turno_final_perdido": n_perd,
            "pct_turno_incompleto": round(100.0 * n_inc / dos_nf.height, 3) if dos_nf.height else None,
            "pct_turno_final_perdido": round(100.0 * n_perd / dos_nf.height, 3) if dos_nf.height else None},
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
    """Tasas por grupo sobre medias entradas no finales: 2 outs, turno incompleto y turno final perdido."""
    out = []
    for fila in (g.group_by(*claves).agg(
            pl.len().alias("n"), (pl.col("outs") == 2).sum().alias("dos_outs"),
            ((pl.col("outs") == 2) & (pl.col("turnos_incompletos") > 0)).sum().alias("incompleto"),
            ((pl.col("outs") == 2) & (pl.col("turnos_incompletos") == 0)).sum().alias("perdido"))
            .sort(*claves).iter_rows(named=True)):
        lo, hi = wilson(fila["perdido"], fila["n"])
        out.append({**{c: fila[c] for c in claves}, "medias_entradas": fila["n"], "dos_outs": fila["dos_outs"],
                    "turno_incompleto": fila["incompleto"], "turno_final_perdido": fila["perdido"],
                    "tasa_dos_outs": fila["dos_outs"] / fila["n"],
                    "tasa_turno_final_perdido": fila["perdido"] / fila["n"],
                    "ic95_wilson": [lo, hi]})
    return out


def analisis_perdida_turnos(df: pl.DataFrame, inconsistente: int = 4, n_boot: int = 1000, seed: int = 2026) -> dict:
    """ADR-015: la pérdida de turnos finales por cubeta × año y por cubeta, y π̂_K (agregado).

    - Tasa de "turno final perdido" por (cubeta, año) y por cubeta, sobre las medias entradas **no finales**,
      con IC de Wilson. G0.8: el rango entre cubetas (puntos %) debe ser pequeño; si no, la pérdida se
      confunde con la altitud en cualquier comparación de outcomes.
    - Déficits de eventos K, OUT_BIP y SAC por media entrada (3 outs menos 2 outs) y
      π̂_K = d_K / (d_K + d_OUT_BIP + d_SAC) con IC por bootstrap de medias entradas. No se implementan los
      pesos de Horvitz–Thompson (eso es F4).
    """
    t = _medias_con_eventos(df, inconsistente)
    nf = t.filter(~pl.col("final"))
    con_cubeta = nf.filter(pl.col("cubeta") != "(sin cubeta)")
    por_cubeta = _tasas(nf, ["cubeta"])
    comparadas = [r for r in por_cubeta if r["cubeta"] != "(sin cubeta)"]
    tasas = [100 * r["tasa_turno_final_perdido"] for r in comparadas]
    rango = float(max(tasas) - min(tasas)) if len(tasas) >= 2 else None

    rng = np.random.default_rng(seed)

    def deficits(tres: pl.DataFrame, dos: pl.DataFrame) -> dict:
        a3 = {e: tres[f"ev_{e}"].to_numpy().astype(float) for e in _EV_OUT}
        a2 = {e: dos[f"ev_{e}"].to_numpy().astype(float) for e in _EV_OUT}
        if len(a3["K"]) == 0 or len(a2["K"]) == 0:
            return {"n_dos": int(dos.height), "n_tres": int(tres.height)}

        def calc(i3, i2):
            d = {e: a3[e][i3].mean() - a2[e][i2].mean() for e in _EV_OUT}
            tot = sum(d.values())
            return d, (d["K"] / tot if tot > 0 else float("nan"))

        d0, pi0 = calc(slice(None), slice(None))
        bs = []
        for _ in range(n_boot):
            d, pi = calc(rng.integers(0, len(a3["K"]), len(a3["K"])), rng.integers(0, len(a2["K"]), len(a2["K"])))
            bs.append([d["K"], d["OUT_BIP"], d["SAC"], pi])
        bs = np.array(bs)
        ic = lambda col: [float(np.nanquantile(bs[:, col], 0.025)), float(np.nanquantile(bs[:, col], 0.975))]
        return {"n_dos": int(dos.height), "n_tres": int(tres.height),
                "deficit": {e: {"estimado": float(d0[e]), "ic95": ic(i)} for i, e in enumerate(_EV_OUT)},
                "pi_k": {"estimado": float(pi0), "ic95": ic(3)}}

    # ¿La pérdida se reparte al azar entre juegos o se concentra en algunos? (huecos de datos por juego).
    # Dispersión de Pearson φ de los turnos finales perdidos por juego: ≈ 1 si es binomial, >> 1 si se agrupa.
    pj = (nf.filter(pl.col("game_anon_id").is_not_null()).group_by("game_anon_id")
          .agg(pl.len().alias("n"), ((pl.col("outs") == 2) & (pl.col("turnos_incompletos") == 0)).sum().alias("m")))
    n_g, m_g = pj["n"].to_numpy().astype(float), pj["m"].to_numpy().astype(float)
    p_bar = m_g.sum() / n_g.sum() if n_g.sum() else float("nan")
    phi = (float(np.sum((m_g - n_g * p_bar) ** 2 / (n_g * p_bar * (1 - p_bar))) / (len(n_g) - 1))
           if len(n_g) > 1 and 0 < p_bar < 1 else None)
    por_juego = {"juegos": len(n_g), "tasa_media": float(p_bar),
                 "dispersion_pearson_phi": phi,
                 "pct_juegos_con_al_menos_una": float(100 * np.mean(m_g > 0)) if len(m_g) else None,
                 "pct_juegos_con_mas_de_dos": float(100 * np.mean(m_g > 2)) if len(m_g) else None}
    tres = t.filter(pl.col("outs") == 3)
    dos_todas = t.filter(pl.col("outs") == 2)
    dos_perdidas = dos_todas.filter(pl.col("turnos_incompletos") == 0)
    return {
        "por_cubeta": por_cubeta, "por_cubeta_anio": _tasas(nf, ["cubeta", "year"]),
        "cubetas_comparadas": [r["cubeta"] for r in comparadas], "rango_pp": rango,
        "medias_entradas_no_finales": int(nf.height), "con_cubeta": int(con_cubeta.height),
        "turnos_finales_perdidos_M": int(((nf["outs"] == 2) & (nf["turnos_incompletos"] == 0)).sum()),
        "por_juego": por_juego,
        "todas_las_de_2_outs": deficits(tres, dos_todas),         # misma población que ROADMAP §1.3
        "solo_turno_final_perdido": deficits(tres, dos_perdidas),
    }


def correr_extras(df: pl.DataFrame, cat: dict, qa: dict, gates: dict | None = None, fis: dict | None = None,
                  seed: int = 2026) -> dict:
    """Diagnósticos de v2.4/v2.5: ADR-010 (polinomios), ADR-011 (is_*), ADR-012/015 (2 outs y pérdida de
    turnos) y ADR-014 (marco temporal de los 9P)."""
    gates, fis = gates or {}, fis or {}
    pol = matriz_polinomios(df, gates.get("g02_r2_c2_min", 0.9999), gates.get("g02_r2_c1_min", 0.999),
                            qa["poli_piso"])
    ts = t_s_por_lanzamiento(df, pol, qa["poli_piso"]) if pol.get("existe") else None
    inc = cat.get("outs_inconsistente", 4)
    return {
        "polinomios": pol,
        "calibracion_9p": calibrar_plano_y_signo(
            df, ts, tuple(fis.get("planos_candidatos_ft", (Y_FRENTE_PLATO_FT, 0.0))),
            tuple(fis.get("signos_candidatos", (1, -1)))),
        "discrepancias_flags": discrepancias_flags(df, cat),
        "dos_outs": diagnostico_dos_outs(df, inc),
        "perdida_turnos": analisis_perdida_turnos(df, inc, int(qa.get("bootstrap_n", 1000)), seed),
    }
