"""Adaptador ESPN: JSON público de marcadores, gratis y sin llave (no oficial).

URL: https://site.api.espn.com/apis/site/v2/sports/soccer/<codigo>/scoreboard[?dates=AAAAMMDD]
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta

from . import ErrorFuente
from ..tiempo import a_iso, de_iso

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{codigo}/scoreboard"
# Ojo: ESPN responde 403 si el User-Agent contiene "Bot".
HEADERS = {"User-Agent": "quiniela/1.0", "Accept": "application/json"}

_ANULADOS = {
    "STATUS_POSTPONED": "pospuesto",
    "STATUS_DELAYED": "pospuesto",
    "STATUS_SUSPENDED": "suspendido",
    "STATUS_ABANDONED": "suspendido",
    "STATUS_CANCELED": "cancelado",
    "STATUS_CANCELLED": "cancelado",
}


def descargar(codigo: str, dia: date | None = None, timeout: int = 15) -> dict:
    url = BASE.format(codigo=codigo)
    if dia:
        url += f"?dates={dia:%Y%m%d}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ErrorFuente(f"ESPN {codigo} {dia or 'hoy'}: {e}") from e


def info_liga(data: dict) -> dict:
    """Nombre, temporada, fase y (si ESPN lo da por día) los días con partidos."""
    ligas = data.get("leagues") or []
    if not ligas:
        return {}
    lg = ligas[0]
    season = lg.get("season") or {}
    cal = lg.get("calendar") or []
    dias = None
    if lg.get("calendarType") == "day" and cal and isinstance(cal[0], str):
        dias = sorted({date.fromisoformat(x[:10]) for x in cal})
    return {
        "nombre": lg.get("name"),
        "temporada": season.get("displayName"),
        "fase": (season.get("type") or {}).get("name"),
        "dias_con_partidos": dias,  # None = ESPN no lo da por día; hay que revisar cada día
    }


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _goles_90(competidor: dict):
    """Suma de los dos primeros periodos (90'). None si no hay desglose."""
    ls = competidor.get("linescores") or []
    if len(ls) < 2:
        return None
    vals = [_int(x.get("value", x.get("displayValue"))) for x in ls[:2]]
    return None if None in vals else sum(vals)


RESUMEN = "https://site.api.espn.com/apis/site/v2/sports/soccer/{codigo}/summary?event={id}"


def descargar_resumen(codigo: str, id_evento: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(RESUMEN.format(codigo=codigo, id=id_evento), headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ErrorFuente(f"ESPN resumen {codigo}/{id_evento}: {e}") from e


def completar_90(p: dict, resumidor=descargar_resumen) -> dict:
    """El scoreboard no trae goles por tiempo. Si el partido se fue a prórroga,
    el resumen del partido sí los trae: de ahí sacamos el marcador a 90'."""
    if not p["revisar"] or p["estado"] != "final" or resumidor is None:
        return p
    try:
        res = resumidor(p["competicion"], p["id_espn"])
        comps = (((res.get("header") or {}).get("competitions") or [{}])[0]).get("competitors") or []
        lados = {c.get("homeAway"): c for c in comps}
        gl90, gv90 = _goles_90(lados.get("home", {})), _goles_90(lados.get("away", {}))
        if gl90 is not None and gv90 is not None:
            p.update(goles_local_90=gl90, goles_visitante_90=gv90, revisar=False)
    except ErrorFuente:
        pass  # se queda "por revisar"
    return p


def normalizar_evento(ev: dict, codigo: str) -> dict:
    comp = (ev.get("competitions") or [{}])[0]
    st = ev.get("status") or comp.get("status") or {}
    tipo = st.get("type") or {}
    nombre_st = tipo.get("name", "")
    state = tipo.get("state", "pre")
    periodo = _int(st.get("period")) or 0

    lados = {c.get("homeAway"): c for c in comp.get("competitors", [])}
    loc, vis = lados.get("home", {}), lados.get("away", {})
    tl, tv = loc.get("team") or {}, vis.get("team") or {}

    if nombre_st in _ANULADOS:
        estado = _ANULADOS[nombre_st]
    elif state == "in":
        estado = "en_juego"
    elif state == "post":
        estado = "final"
    else:
        estado = "programado"

    gl = gv = gl90 = gv90 = None
    revisar = False
    if estado in ("en_juego", "final"):
        gl, gv = _int(loc.get("score")), _int(vis.get("score"))
        hubo_extra = periodo > 2 or any(k in nombre_st for k in ("AET", "PEN", "EXTRA", "SHOOTOUT"))
        if hubo_extra:
            gl90, gv90 = _goles_90(loc), _goles_90(vis)
            if estado == "final" and (gl90 is None or gv90 is None):
                revisar = True
        else:
            gl90, gv90 = gl, gv
        if estado == "final" and (gl is None or gv is None):
            revisar = True

    minuto = None
    if estado == "en_juego":
        minuto = tipo.get("shortDetail") or st.get("displayClock")

    return {
        "competicion": codigo,
        "id_espn": str(ev.get("id")),
        "fuente": "espn",
        "inicio_utc": a_iso(de_iso(ev.get("date") or comp.get("date"))),
        "local": tl.get("displayName") or tl.get("name") or "?",
        "visitante": tv.get("displayName") or tv.get("name") or "?",
        "local_abrev": tl.get("abbreviation"),
        "visitante_abrev": tv.get("abbreviation"),
        "local_logo": tl.get("logo"),
        "visitante_logo": tv.get("logo"),
        "estado": estado,
        "minuto": minuto,
        "goles_local": gl,
        "goles_visitante": gv,
        "goles_local_90": gl90,
        "goles_visitante_90": gv90,
        "revisar": revisar,
    }


def partidos_de(data: dict, codigo: str, resumidor=None) -> list[dict]:
    return [completar_90(normalizar_evento(ev, codigo), resumidor) for ev in data.get("events") or []]


def partidos_en_rango(codigo: str, desde: date, hasta: date, descargador=descargar,
                      resumidor=descargar_resumen):
    """Regresa (info_liga, partidos) entre dos fechas, consultando solo días con partidos."""
    base = descargador(codigo, None)
    info = info_liga(base)
    vistos = {p["id_espn"]: p for p in partidos_de(base, codigo, resumidor)}

    dias = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
    if info.get("dias_con_partidos") is not None:
        con_partido = set(info["dias_con_partidos"])
        dias = [d for d in dias if d in con_partido]
    for d in dias:
        for p in partidos_de(descargador(codigo, d), codigo, resumidor):
            vistos[p["id_espn"]] = p

    return info, sorted(vistos.values(), key=lambda p: p["inicio_utc"])
