"""Generador sintético. La pieza que permite trabajar sin los datos reales.

Produce un DataFrame con TODAS las columnas de `docs/diccionario.csv`, con sus
tipos y categorías, ids anónimos con su formato, cubetas de altitud, medias
entradas completas (I7) y valores que cumplen las identidades I1-I8 de ROADMAP
§4-F0 **por construcción**:

  I1  SpeedDrop = RelSpeed - ZoneSpeed                 (exacto)
  I2  count = f(Balls, Strikes)                        (exacto)
  I3  2 * PitchTrajectory?c2 = a?0                     (exacto: c2 = a0/2)
  I4  VertBreak - InducedVertBreak = -1/2 g ZoneTime^2 (exacto, en pulgadas)
  I5  Tilt <-> SpinAxis biyectivos                     (mapa lineal reloj)
  I6  is_swing = is_whiff + is_contact; whiff=>StrikeSwinging
  I7  suma de OutsOnPlay por media entrada = 3         (se simula hasta 3 outs)
  I8  signo de HorzBreak se invierte con PitcherThrows para el mismo tipo

NO son los datos reales. La física es la mínima para que las identidades valgan
y las magnitudes sean plausibles; F2 extiende este módulo con física exacta y rho
conocida por cubeta.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from .io import leer_diccionario

FTPS_A_MPH = 3600.0 / 5280.0
G_FTS2 = 32.174
Y_FRENTE_PLATO = 17.0 / 12.0  # ft

# Categorías cerradas que el generador emite (coinciden con el diccionario).
CUBETAS_DEFECTO = {
    "baja":  {"altitud_m": 3,    "peso_juegos": 0.20},
    "media": {"altitud_m": 532,  "peso_juegos": 0.30},
    "alta":  {"altitud_m": 2232, "peso_juegos": 0.50},
}

# Parámetros base por tipo de lanzamiento, en el marco de un DIESTRO.
# magnus_z, magnus_x en ft/s^2 (break ~ 0.5 * magnus * ZoneTime^2 * 12 pulgadas).
# magnus_x>0 = lado del brazo del diestro; para zurdos se invierte (I8).
_TIPOS = {
    "Four-Seam": {"vel": 94, "spin": 2300, "axis": 205, "mz": 15.0, "mx": 7.0,  "peso": 0.34},
    "Sinker":    {"vel": 92, "spin": 2150, "axis": 230, "mz": 9.0,  "mx": 14.0, "peso": 0.14},
    "Cutter":    {"vel": 89, "spin": 2400, "axis": 160, "mz": 8.0,  "mx": -3.0, "peso": 0.08},
    "Changeup":  {"vel": 85, "spin": 1750, "axis": 240, "mz": 8.0,  "mx": 13.0, "peso": 0.12},
    "Splitter":  {"vel": 86, "spin": 1500, "axis": 225, "mz": 4.0,  "mx": 8.0,  "peso": 0.04},
    "Slider":    {"vel": 85, "spin": 2500, "axis": 120, "mz": 1.0,  "mx": -11.0, "peso": 0.16},
    "Curveball": {"vel": 79, "spin": 2650, "axis": 40,  "mz": -12.0, "mx": -9.0, "peso": 0.10},
    "Other":     {"vel": 85, "spin": 2000, "axis": 180, "mz": 6.0,  "mx": 2.0,  "peso": 0.02},
}

_HIT_TYPES = ["Ground ball", "Line drive", "Fly ball", "Popup"]


def spinaxis_a_tilt(axis_deg: float) -> str:
    """Mapa reloj biyectivo (I5). 0 grados -> 12:00, 30 grados por hora."""
    total_min = round((float(axis_deg) % 360.0) / 360.0 * 720.0) % 720
    h = (total_min // 60) % 12
    m = total_min % 60
    h = 12 if h == 0 else h
    return f"{h:02d}:{m:02d}"


def _densidad_rel(altitud_m: float) -> float:
    """rho/rho0 barométrica (ROADMAP §2)."""
    return (1.0 - 2.25577e-5 * altitud_m) ** 5.25588


def _fisica_lanzamiento(rng, tipo: str, mano: str, dens_scale: float) -> dict:
    """Un lanzamiento coherente: release, aceleración constante y derivadas.

    Devuelve todas las columnas de trayectoria, velocidad, movimiento y ángulos
    que cumplen I1, I3, I4 por construcción, y I8 vía el signo de mano.
    """
    p = _TIPOS[tipo]
    s = 1.0 if mano == "Right" else -1.0  # espejo del eje x para zurdos (I8)

    rel_speed_mph = max(55.0, rng.normal(p["vel"], 1.6))
    speed0 = rel_speed_mph / FTPS_A_MPH  # ft/s

    extension = float(np.clip(rng.normal(6.2, 0.35), 5.0, 7.5))
    rel_height = float(np.clip(rng.normal(5.8, 0.35), 4.0, 7.0))
    rel_side = s * float(np.clip(rng.normal(1.7, 0.4), 0.3, 3.2)) * -1.0  # diestro: lado 3B

    y0 = 60.5 - extension
    z0 = rel_height
    x0 = rel_side

    vra = rng.normal(-2.0, 1.2)      # ángulo vertical de salida (grados)
    hra = s * rng.normal(1.0, 1.2)   # ángulo horizontal de salida (grados)
    vz0 = speed0 * np.sin(np.radians(vra))
    vx0 = speed0 * np.sin(np.radians(hra))
    vy0 = -np.sqrt(max(speed0**2 - vx0**2 - vz0**2, 1.0))  # hacia el plato (-y)

    # Aceleraciones constantes (modelo 9P): arrastre + Magnus + gravedad.
    ay0 = float(rng.normal(29.0, 3.0)) * dens_scale          # arrastre (decelera -y)
    magnus_z = (p["mz"] + rng.normal(0, 1.5)) * dens_scale
    magnus_x = s * (p["mx"] + rng.normal(0, 1.5)) * dens_scale
    az0 = -G_FTS2 + magnus_z
    ax0 = magnus_x

    # Tiempo a cruzar el frente del plato: 0.5*ay0*t^2 + vy0*t + (y0 - yf) = 0.
    a_, b_, c_ = 0.5 * ay0, vy0, (y0 - Y_FRENTE_PLATO)
    disc = b_**2 - 4 * a_ * c_
    disc = max(disc, 0.0)
    t1 = (-b_ - np.sqrt(disc)) / (2 * a_)
    t2 = (-b_ + np.sqrt(disc)) / (2 * a_)
    tf = min([t for t in (t1, t2) if t > 0], default=0.45)

    # Velocidad y rapidez en el plato -> I1.
    vxf, vyf, vzf = vx0 + ax0 * tf, vy0 + ay0 * tf, vz0 + az0 * tf
    zone_speed_mph = np.sqrt(vxf**2 + vyf**2 + vzf**2) * FTPS_A_MPH
    speed_drop = rel_speed_mph - zone_speed_mph

    # Break respecto a la recta sin fuerzas: desviación = 0.5*a*tf^2 (-> pulgadas).
    f_in = 0.5 * tf**2 * 12.0
    horz_break = ax0 * f_in
    vert_break = az0 * f_in                 # incluye gravedad
    induced_vb = (az0 + G_FTS2) * f_in       # solo Magnus -> I4: VB - IVB = -1/2 g tf^2 *12

    # Ubicación en el plato.
    plate_side = x0 + vx0 * tf + 0.5 * ax0 * tf**2
    plate_height = z0 + vz0 * tf + 0.5 * az0 * tf**2

    # Ángulos de aproximación.
    vaa = np.degrees(np.arctan2(vzf, -vyf))
    haa = np.degrees(np.arctan2(vxf, -vyf))

    # pfx: movimiento sobre los últimos ~40 ft (proxy a partir del Magnus).
    esc = (40.0 / max(y0 - Y_FRENTE_PLATO, 1.0)) ** 2
    pfxx = horz_break * esc
    pfxz = induced_vb * esc

    axis = (p["axis"] + rng.normal(0, 6)) % 360.0
    if mano == "Left":
        axis = (360.0 - axis) % 360.0

    eff_velo = rel_speed_mph + (extension - 6.2) * 1.5 + rng.normal(0, 0.8)

    return {
        "RelSpeed": rel_speed_mph, "EffectiveVelo": eff_velo, "ZoneSpeed": zone_speed_mph,
        "SpinRate": max(600.0, rng.normal(p["spin"], 120)), "SpinAxis": axis,
        "Tilt": spinaxis_a_tilt(axis),
        "RelHeight": rel_height, "RelSide": rel_side, "Extension": extension,
        "VertBreak": vert_break, "InducedVertBreak": induced_vb, "HorzBreak": horz_break,
        "VertRelAngle": vra, "HorzRelAngle": hra, "VertApprAngle": vaa, "HorzApprAngle": haa,
        "SpeedDrop": speed_drop, "ZoneTime": tf,
        "x0": x0, "y0": y0, "z0": z0, "vx0": vx0, "vy0": vy0, "vz0": vz0,
        "ax0": ax0, "ay0": ay0, "az0": az0, "pfxx": pfxx, "pfxz": pfxz,
        # Polinomio de trayectoria: c0=pos, c1=vel, c2=accel/2  -> I3: 2*c2 = a0.
        "PitchTrajectoryXc0": x0, "PitchTrajectoryXc1": vx0, "PitchTrajectoryXc2": ax0 / 2.0,
        "PitchTrajectoryYc0": y0, "PitchTrajectoryYc1": vy0, "PitchTrajectoryYc2": ay0 / 2.0,
        "PitchTrajectoryZc0": z0, "PitchTrajectoryZc1": vz0, "PitchTrajectoryZc2": az0 / 2.0,
        "PlateLocHeight": plate_height, "PlateLocSide": plate_side,
    }


def _desenlace(rng, en_zona: bool) -> dict:
    """PitchCall y flags coherentes con I6. No es terminal por sí mismo."""
    p_swing = 0.62 if en_zona else 0.30
    swing = rng.random() < p_swing
    call = None
    if swing:
        p_contacto = 0.82 if en_zona else 0.66
        if rng.random() < p_contacto:
            call = "InPlay" if rng.random() < 0.34 else "FoulBall"
        else:
            call = "StrikeSwinging"
    else:
        if en_zona:
            call = "StrikeCalled"
        else:
            r = rng.random()
            call = "BallCalled" if r < 0.93 else ("BallinDirt" if r < 0.98 else "HitByPitch")
    is_swing = int(call in ("StrikeSwinging", "FoulBall", "InPlay"))
    is_whiff = int(call == "StrikeSwinging")
    is_contact = int(call in ("FoulBall", "InPlay"))
    return {
        "PitchCall": call, "is_swing": is_swing, "is_whiff": is_whiff, "is_contact": is_contact,
        "is_called_strike": int(call == "StrikeCalled"),
        "is_swinging_strike": is_whiff,
        "is_ball_in_play": int(call == "InPlay"),
    }


def _batazo(rng, dens_scale: float) -> dict:
    """Resultado de un batazo (InPlay). Carry mayor a menor densidad."""
    ht = _HIT_TYPES[rng.integers(0, len(_HIT_TYPES))]
    exit_speed = float(np.clip(rng.normal(88, 12), 40, 118))
    angle = {"Ground ball": rng.normal(-5, 8), "Line drive": rng.normal(14, 6),
             "Fly ball": rng.normal(32, 8), "Popup": rng.normal(60, 8)}[ht]
    direction = float(rng.normal(0, 22))
    # Distancia: crece con EV y ángulo óptimo; el carry sube a menor densidad.
    base = max(0.0, exit_speed * 4.0 - abs(angle - 28) * 6.0)
    distance = float(np.clip(base * (1.0 + (1.0 - dens_scale) * 0.12) + rng.normal(0, 20), 0, 480))
    # Resultado según distancia/EV (heurístico, plausible).
    if ht == "Fly ball" and distance > 380 and exit_speed > 98:
        res, hit, s, d, t, hr = "HomeRun", 1, 0, 0, 0, 1
    elif ht == "Line drive" and exit_speed > 95 and rng.random() < 0.5:
        res, hit, s, d, t, hr = ("Double", 1, 0, 1, 0, 0) if rng.random() < 0.4 else ("Single", 1, 1, 0, 0, 0)
    elif ht == "Ground ball" and rng.random() < 0.26 or ht == "Line drive" and rng.random() < 0.55:
        res, hit, s, d, t, hr = "Single", 1, 1, 0, 0, 0
    else:
        res, hit, s, d, t, hr = "Out", 0, 0, 0, 0, 0
    return {
        "hit_type": ht, "ExitSpeed": exit_speed, "Angle": float(angle), "Direction": direction,
        "Distance": distance, "play_result": res, "is_hit": hit,
        "single": s, "double": d, "triple": t, "home_run": hr,
    }


_COLS_BATAZO_NULAS = {
    "hit_type": None, "ExitSpeed": None, "Angle": None, "Direction": None, "Distance": None,
    "play_result": None, "is_hit": 0, "single": 0, "double": 0, "triple": 0, "home_run": 0,
}


def generar(n_juegos: int = 40, semilla: int = 2026, cubetas: dict | None = None,
            n_lanzadores: int = 60, n_bateadores: int = 120, n_receptores: int = 24,
            n_lanzadores_nucleo: int = 12, anios: tuple[int, ...] = (2023, 2024, 2025),
            innings_por_juego: int = 9) -> pl.DataFrame:
    """Genera un dataset sintético con el esquema del diccionario.

    El núcleo de lanzadores aparece en casi todos los juegos y cubetas (prueba de
    "solo Diablos" y "lanzadores en >=2 cubetas" de F0). La cubeta "alta" ~ Harp
    Helú concentra la mitad de los juegos.
    """
    rng = np.random.default_rng(semilla)
    cubetas = cubetas or CUBETAS_DEFECTO
    nombres_cub = list(cubetas)
    pesos_cub = np.array([cubetas[c]["peso_juegos"] for c in nombres_cub], float)
    pesos_cub /= pesos_cub.sum()
    dens = {c: _densidad_rel(cubetas[c]["altitud_m"]) for c in nombres_cub}
    dens_baja = dens[min(cubetas, key=lambda c: cubetas[c]["altitud_m"])]

    lanz = [f"pitcher_{i:05d}" for i in range(1, n_lanzadores + 1)]
    nucleo = lanz[:n_lanzadores_nucleo]
    bats = [f"batter_{i:05d}" for i in range(1, n_bateadores + 1)]
    recs = [f"catcher_{i:05d}" for i in range(1, n_receptores + 1)]
    tipos = list(_TIPOS)
    pesos_tipo = np.array([_TIPOS[t]["peso"] for t in tipos], float)
    pesos_tipo /= pesos_tipo.sum()

    filas: list[dict] = []
    puid = 0
    for g in range(n_juegos):
        game_id = f"game_{g + 1:06d}"
        cub = nombres_cub[rng.choice(len(nombres_cub), p=pesos_cub)]
        dens_scale = dens[cub] / dens_baja
        anio = int(anios[rng.integers(0, len(anios))])
        # Dos planteles de lanzadores (uno por mitad), sesgados al núcleo.
        mano_eq = {"Top": rng.choice(["Right", "Left"], p=[0.72, 0.28]),
                   "Bottom": rng.choice(["Right", "Left"], p=[0.72, 0.28])}
        for inning in range(1, innings_por_juego + 1):
            for mitad in ("Top", "Bottom"):
                # Lanzador de la defensa en esta media entrada.
                if rng.random() < 0.6:
                    lanzador = nucleo[rng.integers(0, len(nucleo))]
                else:
                    lanzador = lanz[rng.integers(0, len(lanz))]
                mano = str(mano_eq[mitad])
                receptor = recs[rng.integers(0, len(recs))]
                outs = 0
                pa = 0
                while outs < 3:
                    pa += 1
                    forzar_out = pa > 20  # salvaguarda: media entrada siempre cierra
                    bateador = bats[rng.integers(0, len(bats))]
                    lado_bat = str(rng.choice(["Right", "Left"], p=[0.55, 0.45]))
                    balls, strikes = 0, 0
                    terminada = False
                    while not terminada:
                        puid += 1
                        tipo = tipos[rng.choice(len(tipos), p=pesos_tipo)]
                        fis = _fisica_lanzamiento(rng, tipo, mano, dens_scale)
                        en_zona = (1.5 <= fis["PlateLocHeight"] <= 3.5) and (abs(fis["PlateLocSide"]) <= 0.83)
                        des = _desenlace(rng, en_zona)
                        call = des["PitchCall"]
                        if forzar_out:  # cierra la entrada con un out en juego
                            call = "InPlay"
                            des = {"PitchCall": "InPlay", "is_swing": 1, "is_whiff": 0,
                                   "is_contact": 1, "is_called_strike": 0,
                                   "is_swinging_strike": 0, "is_ball_in_play": 1}

                        # Transición del conteo y terminalidad.
                        korbb, outs_jugada, runs = "Undefined", 0, 0
                        extra = dict(_COLS_BATAZO_NULAS)
                        base_on_balls = strikeout = is_hbp = is_batted = 0
                        if call in ("StrikeCalled", "StrikeSwinging"):
                            strikes += 1
                            if strikes >= 3:
                                terminada, korbb, strikeout, outs_jugada = True, "Strikeout", 1, 1
                        elif call == "FoulBall":
                            strikes = min(strikes + 1, 2)
                        elif call in ("BallCalled", "BallinDirt", "BallIntentional"):
                            balls += 1
                            if balls >= 4:
                                terminada, korbb, base_on_balls = True, "Walk", 1
                        elif call == "HitByPitch":
                            terminada, is_hbp = True, 1
                        elif call == "InPlay":
                            terminada, is_batted = True, 1
                            bat = _batazo(rng, dens_scale)
                            extra.update(bat)
                            if forzar_out or bat["play_result"] == "Out":
                                extra.update(_batazo_a_out(bat))
                                outs_jugada = 1
                            else:
                                outs_jugada = 0
                                runs = int(rng.integers(0, 3)) if bat["home_run"] else int(rng.random() < 0.25)
                                if bat["home_run"]:
                                    runs = max(1, runs)

                        if terminada:
                            outs_jugada = min(outs_jugada, 3 - outs)

                        fila = {
                            "year": anio, "PitchUID": f"pitch_{puid:08d}", "game_anon_id": game_id,
                            "pitcher_anon_id": lanzador, "batter_anon_id": bateador,
                            "catcher_anon_id": receptor, "PitcherThrows": mano, "BatterSide": lado_bat,
                            "altitude_category": cub, "AutoPitchType": tipo,
                            **{k: fis[k] for k in (
                                "RelSpeed", "EffectiveVelo", "ZoneSpeed", "SpinRate", "SpinAxis", "Tilt",
                                "RelHeight", "RelSide", "Extension", "VertBreak", "InducedVertBreak",
                                "HorzBreak", "VertRelAngle", "HorzRelAngle", "VertApprAngle", "HorzApprAngle",
                                "SpeedDrop", "ZoneTime", "x0", "y0", "z0", "vx0", "vy0", "vz0",
                                "ax0", "ay0", "az0", "pfxx", "pfxz",
                                "PitchTrajectoryXc0", "PitchTrajectoryXc1", "PitchTrajectoryXc2",
                                "PitchTrajectoryYc0", "PitchTrajectoryYc1", "PitchTrajectoryYc2",
                                "PitchTrajectoryZc0", "PitchTrajectoryZc1", "PitchTrajectoryZc2")},
                            "PitchCall": call, "KorBB": korbb,
                            "play_result": extra["play_result"], "hit_type": extra["hit_type"],
                            "ExitSpeed": extra["ExitSpeed"], "Angle": extra["Angle"],
                            "Direction": extra["Direction"], "Distance": extra["Distance"],
                            "is_swing": des["is_swing"], "is_whiff": des["is_whiff"],
                            "is_contact": des["is_contact"], "is_called_strike": des["is_called_strike"],
                            "is_swinging_strike": des["is_swinging_strike"],
                            "is_ball_in_play": des["is_ball_in_play"], "is_batted": is_batted,
                            "is_hit": extra["is_hit"], "single": extra["single"], "double": extra["double"],
                            "triple": extra["triple"], "home_run": extra["home_run"],
                            "base_on_balls": base_on_balls, "strikeout": strikeout,
                            "is_hit_by_pitch": is_hbp, "RunsScored": runs, "OutsOnPlay": outs_jugada,
                            "Inning": inning, "Top/Bottom": mitad, "Outs": outs,
                            # Balls/Strikes ANTES del lanzamiento (I2): se fijan abajo.
                            "Balls": 0, "Strikes": 0, "count": None,
                            "PlateLocHeight": fis["PlateLocHeight"], "PlateLocSide": fis["PlateLocSide"],
                            "in_strike_zone": int(en_zona), "outside_strike_zone": int(not en_zona),
                            "swung_outside_strike_zone": int(des["is_swing"] and not en_zona),
                        }
                        b_antes, s_antes = _conteo_antes(call, balls, strikes)
                        fila["Balls"], fila["Strikes"] = b_antes, s_antes
                        fila["count"] = f"{b_antes}-{s_antes}"
                        filas.append(fila)
                    outs += outs_jugada
    df = pl.DataFrame(filas)
    return _ordenar_y_tipar(df)


def _conteo_antes(call, balls_despues, strikes_despues):
    """Balls y Strikes ANTES del lanzamiento, a partir del estado posterior."""
    b, s = balls_despues, strikes_despues
    if call in ("StrikeCalled", "StrikeSwinging"):
        s = strikes_despues - 1
    elif call == "FoulBall":
        s = strikes_despues if strikes_despues == 2 else strikes_despues - 1
    elif call in ("BallCalled", "BallinDirt", "BallIntentional"):
        b = balls_despues - 1
    return int(max(0, min(b, 3))), int(max(0, min(s, 2)))


def _batazo_a_out(bat: dict) -> dict:
    return {"play_result": "Out", "is_hit": 0, "single": 0, "double": 0, "triple": 0, "home_run": 0}


# --------------------------------------------------------------------------
# Tipado y orden de columnas segun el diccionario
# --------------------------------------------------------------------------
_RAIZ = Path(__file__).resolve().parents[2]


def _ordenar_y_tipar(df: pl.DataFrame) -> pl.DataFrame:
    specs = leer_diccionario(_RAIZ / "docs" / "diccionario.csv")
    orden = [s.nombre for s in specs]
    tipos = {s.nombre: s for s in specs}
    exprs = []
    for nombre in orden:
        if nombre not in df.columns:
            raise ValueError(f"el generador no produjo la columna documentada: {nombre}")
        s = tipos[nombre]
        if s.es_entera:
            exprs.append(pl.col(nombre).cast(pl.Int64))
        elif s.es_booleana:
            exprs.append(pl.col(nombre).cast(pl.Int8))
        elif s.es_numerica:
            exprs.append(pl.col(nombre).cast(pl.Float64))
        else:  # string / categorical
            exprs.append(pl.col(nombre).cast(pl.Utf8))
    return df.select(exprs)


# --------------------------------------------------------------------------
# Escritura de los tres formatos
# --------------------------------------------------------------------------
def escribir_tres_formatos(df: pl.DataFrame, ruta_base: str | Path) -> dict:
    """Escribe el mismo dataset en .parquet, .pkl y .rds.

    `ruta_base` sin extensión (p. ej. data/raw/stuff_model_df). Devuelve tamaños
    en disco. El .rds exige tipos simples: las categóricas van como texto.
    """
    base = Path(ruta_base)
    base.parent.mkdir(parents=True, exist_ok=True)
    p_parquet = base.with_suffix(".parquet")
    p_pkl = base.with_suffix(".pkl")
    p_rds = base.with_suffix(".rds")

    df.write_parquet(p_parquet)
    pdf = df.to_pandas()
    pdf.to_pickle(p_pkl)

    import pyreadr
    pdf_rds = pdf.copy()
    for c in pdf_rds.columns:
        if pdf_rds[c].dtype == object or str(pdf_rds[c].dtype) == "category":
            pdf_rds[c] = pdf_rds[c].astype("string")
    pyreadr.write_rds(str(p_rds), pdf_rds)

    return {
        "parquet": p_parquet.stat().st_size,
        "pkl": p_pkl.stat().st_size,
        "rds": p_rds.stat().st_size,
        "filas": df.height,
        "columnas": df.width,
    }
