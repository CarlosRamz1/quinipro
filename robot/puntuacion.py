"""Reglas de puntuación (funciones puras, sin base de datos). Ver docs/REGLAS.md."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

ANULADOS = {"pospuesto", "suspendido", "cancelado"}


def resultado(gl: int, gv: int) -> str:
    return "L" if gl > gv else "V" if gv > gl else "E"


def puede_editar(partido: dict, ahora: datetime) -> bool:
    """Un pick se puede cambiar solo antes del pitazo inicial."""
    from .tiempo import de_iso
    return partido["estado"] == "programado" and ahora < de_iso(partido["inicio_utc"])


def marcador_que_cuenta(p: dict, en_vivo: bool):
    """Marcador a 90'. Si en_vivo, también cuenta el marcador parcial de partidos en juego."""
    if p["estado"] == "final" or (en_vivo and p["estado"] == "en_juego"):
        if p.get("goles_local_90") is not None and p.get("goles_visitante_90") is not None:
            return p["goles_local_90"], p["goles_visitante_90"]
    return None


@dataclass
class Fila:
    usuario_id: int
    puntos: int = 0
    exacto_estelar: bool = False
    distancia: int | None = None
    posicion: int = 0


def calcular_tabla(partidos: dict, pronosticos: dict, desempates: dict,
                   participantes: list, estelar_id=None, en_vivo: bool = True):
    """
    partidos:     {partido_id: {"estado", "goles_local_90", "goles_visitante_90"}}
    pronosticos:  {usuario_id: {partido_id: "L"|"E"|"V"}}
    desempates:   {usuario_id: (goles_local, goles_visitante)}  -> marcador del estelar
    Regresa (filas ordenadas, provisional: bool).
    """
    resultados = {}
    pendientes = False
    for pid, p in partidos.items():
        if p["estado"] in ANULADOS:
            continue
        if p["estado"] != "final":
            pendientes = True
        m = marcador_que_cuenta(p, en_vivo)
        if m:
            resultados[pid] = resultado(*m)

    est = None
    if estelar_id is not None and estelar_id in partidos:
        est = marcador_que_cuenta(partidos[estelar_id], en_vivo)

    filas = []
    for uid in participantes:
        f = Fila(usuario_id=uid)
        picks = pronosticos.get(uid, {})
        f.puntos = sum(1 for pid, r in resultados.items() if picks.get(pid) == r)
        d = desempates.get(uid)
        if est and d:
            f.exacto_estelar = (d[0], d[1]) == est
            f.distancia = abs(d[0] - est[0]) + abs(d[1] - est[1])
        filas.append(f)

    def clave(f: Fila):
        return (-f.puntos, not f.exacto_estelar, f.distancia if f.distancia is not None else 999)

    filas.sort(key=lambda f: (clave(f), f.usuario_id))
    pos, anterior = 0, None
    for i, f in enumerate(filas, start=1):
        if clave(f) != anterior:
            pos, anterior = i, clave(f)
        f.posicion = pos  # empates comparten lugar: 1, 1, 3...
    return filas, pendientes
