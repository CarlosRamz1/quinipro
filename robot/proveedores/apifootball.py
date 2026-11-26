"""Respaldo: API-Football, plan gratis (100 consultas/día, sin tarjeta).

Solo se usa si ESPN falla. Requiere la variable de entorno API_FOOTBALL_KEY
(se obtiene gratis en dashboard.api-football.com). Sin llave, el respaldo queda apagado.
Un contador local evita pasar de LIMITE_DIARIO consultas.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from . import ErrorFuente
from ..tiempo import a_iso, ahora_utc, de_iso

BASE = "https://v3.football.api-sports.io"
LIMITE_DIARIO = 90  # dejamos 10 de margen
_CONTADOR = Path(__file__).resolve().parents[2] / "data" / "apifootball_uso.json"

_FINAL = {"FT", "AET", "PEN", "AWD", "WO"}
_EN_JUEGO = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}
_ANULADOS = {"PST": "pospuesto", "SUSP": "suspendido", "ABD": "suspendido", "CANC": "cancelado"}


def disponible() -> bool:
    return bool(os.environ.get("API_FOOTBALL_KEY"))


def _consumir_cuota():
    hoy = ahora_utc().strftime("%Y-%m-%d")  # la cuota se reinicia a medianoche UTC
    uso = {"dia": hoy, "n": 0}
    if _CONTADOR.exists():
        try:
            uso = json.loads(_CONTADOR.read_text())
        except ValueError:
            pass
    if uso.get("dia") != hoy:
        uso = {"dia": hoy, "n": 0}
    if uso["n"] >= LIMITE_DIARIO:
        raise ErrorFuente("API-Football: cuota diaria agotada")
    uso["n"] += 1
    _CONTADOR.parent.mkdir(parents=True, exist_ok=True)
    _CONTADOR.write_text(json.dumps(uso))


def _get(ruta: str, params: dict) -> dict:
    if not disponible():
        raise ErrorFuente("API-Football: falta API_FOOTBALL_KEY")
    _consumir_cuota()
    url = f"{BASE}{ruta}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": os.environ["API_FOOTBALL_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ErrorFuente(f"API-Football {ruta}: {e}") from e
    if data.get("errors"):
        raise ErrorFuente(f"API-Football: {data['errors']}")
    return data


def temporada_para(dia: date, anual: bool) -> int:
    """API-Football nombra la temporada por el año en que empieza (Liga MX 2026 = Apertura 26 + Clausura 27)."""
    if anual:
        return dia.year
    return dia.year if dia.month >= 7 else dia.year - 1


def normalizar(fx: dict, codigo: str) -> dict:
    f, t, g, s = fx["fixture"], fx["teams"], fx["goals"], fx.get("score") or {}
    corto = (f.get("status") or {}).get("short", "NS")
    if corto in _ANULADOS:
        estado = _ANULADOS[corto]
    elif corto in _FINAL:
        estado = "final"
    elif corto in _EN_JUEGO:
        estado = "en_juego"
    else:
        estado = "programado"

    gl = gv = gl90 = gv90 = None
    if estado in ("en_juego", "final"):
        gl, gv = g.get("home"), g.get("away")
        ft = s.get("fulltime") or {}
        if corto in ("AET", "PEN", "ET", "BT", "P") and ft.get("home") is not None:
            gl90, gv90 = ft.get("home"), ft.get("away")
        else:
            gl90, gv90 = gl, gv

    elapsed = (f.get("status") or {}).get("elapsed")
    return {
        "competicion": codigo,
        "id_apifootball": f["id"],
        "fuente": "apifootball",
        "inicio_utc": a_iso(de_iso(f["date"])),
        "local": t["home"]["name"],
        "visitante": t["away"]["name"],
        "local_abrev": None,
        "visitante_abrev": None,
        "local_logo": t["home"].get("logo"),
        "visitante_logo": t["away"].get("logo"),
        "estado": estado,
        "minuto": (f"{elapsed}'" if elapsed else corto) if estado == "en_juego" else None,
        "goles_local": gl,
        "goles_visitante": gv,
        "goles_local_90": gl90,
        "goles_visitante_90": gv90,
        "revisar": estado == "final" and gl90 is None,
    }


def partidos_del_dia(codigo: str, liga_id: int, dia: date, anual: bool) -> list[dict]:
    data = _get("/fixtures", {"league": liga_id, "season": temporada_para(dia, anual),
                              "date": dia.isoformat(), "timezone": "UTC"})
    return [normalizar(fx, codigo) for fx in data.get("response", [])]
