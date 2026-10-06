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

from .fisica import verificar_9p
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


def matriz_polinomios(df: pl.DataFrame, r2_min: float = 0.99, piso: float = 1.0) -> dict:
    """ADR-010: ¿los polinomios PitchTrajectory{X,Y,Z}c{0,1,2} son los 9P con otros ejes?

    Matriz 3×3 de regresiones (pendiente, intercepto, R²) de c2 sobre ax0/ay0/az0 y de c1 sobre
    vx0/vy0/vz0 (y, informativo, c0 sobre x0/y0/z0). Busca la permutación con signo de mayor
    R² mínimo (sobre c2 y c1). Si existe con R² ≥ `r2_min` en los tres ejes se documenta y los
    polinomios sirven de verificación cruzada; si no, se declaran no canónicos. Si c1 encaja con un
    desfase, estima t_s = (s·c1 − v0)/a0. Ninguna fase depende de los polinomios: la trayectoria
    canónica es la de los 9P.
    """
    cols = [f"PitchTrajectory{p}c{k}" for k in (0, 1, 2) for p in _POLI] + \
           [c for fam in _NUEVE.values() for c in fam]
    d = df.select(cols).drop_nulls()
    if d.height < 100:
        return {"n": d.height, "existe": False, "decision": "sin_datos_suficientes"}
    arr = {fam: (d.select([f"PitchTrajectory{p}{fam}" for p in _POLI]).to_numpy().astype(float),
                 d.select(list(_NUEVE[fam])).to_numpy().astype(float)) for fam in _NUEVE}
    matriz = {fam: _corr_cruzada(*arr[fam]) for fam in _NUEVE}

    def r2(fam: str, p: str, q: str) -> float:
        v = matriz[fam][p][q]["r2"]
        return -1.0 if v is None else v

    mejor, mejor_score = None, -2.0
    for perm in itertools.permutations(range(3)):
        score = min(min(r2("c2", p, _EJES[perm[i]]), r2("c1", p, _EJES[perm[i]])) for i, p in enumerate(_POLI))
        if score > mejor_score:
            mejor, mejor_score = perm, score
    asignacion = {p: _EJES[mejor[i]] for i, p in enumerate(_POLI)}
    signos = {p: (1 if (matriz["c2"][p][asignacion[p]]["pendiente"] or 0) >= 0 else -1) for p in _POLI}
    escala = {p: (None if matriz["c2"][p][asignacion[p]]["pendiente"] is None
                  else abs(2 * matriz["c2"][p][asignacion[p]]["pendiente"])) for p in _POLI}
    existe = mejor_score >= r2_min

    t_s = None
    if existe:
        t_s = {}
        for p in _POLI:
            q = asignacion[p]
            j = _EJES.index(q)
            c1, v0, a0 = arr["c1"][0][:, _POLI.index(p)], arr["c1"][1][:, j], arr["c2"][1][:, j]
            ok = np.abs(a0) > piso
            if ok.any():
                ts = (signos[p] * c1[ok] - v0[ok]) / a0[ok]
                t_s[p] = {"mediana_s": float(np.median(ts)),
                          "rango_intercuartil_s": float(np.subtract(*np.quantile(ts, [0.75, 0.25]))),
                          "intercepto_c1_sobre_v0": matriz["c1"][p][q]["intercepto"]}
    return {
        "n": int(d.height), "matriz": matriz, "r2_min_exigido": r2_min,
        "permutacion": asignacion, "signos": signos, "escala_2c2_sobre_a0": escala,
        "r2_min_permutacion": mejor_score, "existe": bool(existe),
        "decision": "mapeo_con_signo" if existe else "no_canonicos",
        "t_s": t_s,
        "rotacion": {fam: _regresion_conjunta(*arr[fam]) for fam in _NUEVE},
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


def diagnostico_dos_outs(df: pl.DataFrame, inconsistente: int = 4) -> dict:
    """¿Por qué el ~13 % de las medias entradas suma 2 outs en vez de 3? (agregado, ADR-012).

    Contrasta tres candidatos: (1) tercer out en un evento sin lanzamiento propio (robo, pickoff):
    la media entrada deja un turno **incompleto** (lanzamientos de un bateador sin evento terminal);
    (2) lanzamientos faltantes de Trackman; (3) `OutsOnPlay` que no cuenta los outs de los ponches
    u otros eventos. No hay orden de lanzamientos: el "último turno reconstruible" es el del
    bateador de la media entrada cuyos lanzamientos no traen evento terminal.
    """
    t = tabla_medias_entradas(df, inconsistente)
    claves = ["game_anon_id", "Inning", "mitad"]
    d = df.filter(pl.col("game_anon_id").is_not_null() & pl.col("Inning").is_not_null()).with_columns(
        pl.col("Top/Bottom").cast(pl.Utf8).alias("mitad"),
        pl.col("evento_terminal").cast(pl.Utf8).alias("_ev"))
    ev_out = ["K", "OUT_BIP", "SAC"]
    por_media = d.group_by(*claves).agg(
        pl.col("_ev").is_not_null().sum().alias("n_terminales"),
        pl.col("_ev").is_in(ev_out).sum().alias("outs_por_eventos"),
        *[(pl.col("_ev") == e).sum().alias(f"ev_{e}") for e in ev_out + ["BB", "HBP", "ROE"]])
    # turnos incompletos: bateadores (con id) de la media entrada sin ningún evento terminal.
    turnos = (d.filter(pl.col("batter_anon_id").is_not_null())
              .group_by(*claves, "batter_anon_id").agg(pl.col("_ev").is_not_null().any().alias("termina")))
    inc = turnos.group_by(*claves).agg((~pl.col("termina")).sum().alias("turnos_incompletos"))
    t = (t.join(por_media, on=claves, how="left").join(inc, on=claves, how="left")
         .with_columns(pl.col("turnos_incompletos").fill_null(0)))

    def grupo(outs: int) -> dict:
        g = t.filter(pl.col("outs") == outs)
        if g.height == 0:
            return {"n": 0}
        dif = (g["outs_por_eventos"] - g["outs"])
        return {
            "n": int(g.height),
            "pct_ultima_del_juego": round(100.0 * float(g["final"].mean()), 3),
            "lanzamientos_por_media_entrada": _cuantiles(g["n_lanz"].cast(pl.Float64)),
            "pct_con_turno_incompleto": round(100.0 * float((g["turnos_incompletos"] > 0).mean()), 3),
            "turnos_incompletos_media": float(g["turnos_incompletos"].mean()),
            "eventos_terminales_por_media_entrada": {
                e: round(float(g[f"ev_{e}"].mean()), 3) for e in ev_out + ["BB", "HBP", "ROE"]},
            "outs_implicados_por_eventos_menos_OutsOnPlay": {
                str(int(k)): int(v) for k, v in dif.value_counts().sort(dif.name).iter_rows()},
        }

    tabla = (df.group_by(pl.col("evento_terminal").cast(pl.Utf8).fill_null("NO_TERMINAL").alias("evento"),
                         pl.col("OutsOnPlay").cast(pl.Int64).alias("OutsOnPlay"))
             .agg(pl.len().alias("n")).sort("evento", "OutsOnPlay"))
    return {
        "dos_outs": grupo(2), "tres_outs": grupo(3),
        "outs_on_play_x_evento_terminal": tabla.to_dicts(),
    }


def correr_extras(df: pl.DataFrame, cat: dict, qa: dict) -> dict:
    """Diagnósticos de v2.4: ADR-010 (polinomios), ADR-011 (is_*), ADR-012 (2 outs) y verificación de los 9P."""
    return {
        "polinomios": matriz_polinomios(df, 0.99, qa["poli_piso"]),
        "discrepancias_flags": discrepancias_flags(df, cat),
        "dos_outs": diagnostico_dos_outs(df, cat.get("outs_inconsistente", 4)),
        "verificacion_9p": verificar_9p(df),
    }
