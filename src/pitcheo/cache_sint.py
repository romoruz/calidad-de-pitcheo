"""Caché en disco de la sintética de F2 (ADR-019): `reports/cache/f02_sint/<llave>.npz` (fuera de git).

Llave = SHA-256 de (nombre del escenario, parámetros de `generar_fisica`, semilla, hash del código de `sintetico.py` y
`fisica.py`): cualquier cambio en el generador o en la física invalida la caché. Se guarda el DataFrame por lanzamiento y
la «verdad» (arrays por separado, resto en JSON). Cargarla da exactamente lo que `generar_fisica` habría devuelto.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl

from . import recursos

RAIZ = Path(__file__).resolve().parents[2]
DIR_DEFECTO = RAIZ / "reports" / "cache" / "f02_sint"


def _plano(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, tuple):
        return list(o)
    return str(o)


def llave(escenario: str, params: dict, semilla: int, hash_codigo: str | None = None) -> str:
    """Llave de caché: hash de escenario + parámetros + semilla + hash del código del generador."""
    payload = json.dumps({"esc": escenario, "par": params, "sem": int(semilla),
                          "cod": hash_codigo or recursos.hash_codigo()}, sort_keys=True, default=_plano)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def ruta(clave: str, directorio: Path | None = None) -> Path:
    return (directorio or DIR_DEFECTO) / f"{clave}.npz"


def guardar(clave: str, df: pl.DataFrame, verdad: dict, directorio: Path | None = None) -> Path:
    """Escribe df + verdad en un .npz comprimido (escritura atómica)."""
    p = ruta(clave, directorio)
    p.parent.mkdir(parents=True, exist_ok=True)
    arr: dict = {}
    for c in df.columns:
        x = df[c].to_numpy()
        arr[f"col__{c}"] = x.astype("U") if x.dtype == object else x
    resto = {}
    for k, v in verdad.items():
        if isinstance(v, np.ndarray):
            arr[f"ver__{k}"] = v
        else:
            resto[k] = v
    arr["ver_json"] = np.array(json.dumps(resto, default=_plano))
    arr["orden_cols"] = np.array(json.dumps(df.columns))
    tmp = p.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **arr)
    tmp.replace(p)
    return p


def cargar(clave: str, directorio: Path | None = None) -> tuple[pl.DataFrame, dict] | None:
    """Lee la caché; None si no existe o está corrupta."""
    p = ruta(clave, directorio)
    if not p.exists():
        return None
    try:
        with np.load(p, allow_pickle=False) as z:
            cols = json.loads(str(z["orden_cols"]))
            df = pl.DataFrame({c: z[f"col__{c}"] for c in cols})
            verdad = json.loads(str(z["ver_json"]))
            for k in z.files:
                if k.startswith("ver__"):
                    verdad[k[5:]] = z[k]
    except (OSError, ValueError, KeyError):
        return None
    if "calibracion_parques" in verdad:
        verdad["calibracion_parques"] = {int(k): tuple(v) for k, v in verdad["calibracion_parques"].items()}
    if "cubetas_sesgo" in verdad:
        verdad["cubetas_sesgo"] = tuple(verdad["cubetas_sesgo"])
    return df, verdad


def generar_con_cache(escenario: str, semilla: int, kw: dict, usar_cache: bool = True,
                      directorio: Path | None = None) -> tuple[pl.DataFrame, dict, bool]:
    """`generar_fisica(**kw, semilla)` con caché. → (df, verdad, vino_de_cache). `kw` incluye n_juegos y lanzamientos."""
    from .sintetico import generar_fisica
    clave = llave(escenario, kw, semilla)
    if usar_cache:
        hit = cargar(clave, directorio)
        if hit is not None:
            return hit[0], hit[1], True
    df, verdad = generar_fisica(semilla=semilla, **kw)
    if usar_cache:
        guardar(clave, df, verdad, directorio)
    return df, verdad, False
