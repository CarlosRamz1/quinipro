"""Proceso principal del robot (lo que corre 24/7 en el VPS).

- Cada 6 horas: explora todas las ligas (calendarios, ligas activas).
- Si hay partidos por empezar o en juego: consulta cada 60 s, bloquea, actualiza marcadores
  y recalcula las tablas de posiciones.
- Si no hay partidos: duerme hasta 2 min antes del siguiente (máx. 30 min por siesta).

Uso:  python -m robot.main            (ciclo infinito)
      python -m robot.main --una-vez  (un solo ciclo, para pruebas)
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import timedelta

from .db import RAIZ, conectar, guardar_partido, inicializar, quinielas_con_partido, recalcular_quiniela
from .explorador import explorar
from .proveedores import ErrorFuente, apifootball, espn
from .tiempo import a_iso, ahora_utc, de_iso

log = logging.getLogger("robot")

CADA_EXPLORACION = timedelta(hours=6)
INTERVALO_VIVO = 60          # segundos entre consultas con partidos en juego
SIESTA_MAX = 30 * 60
RESPALDO_CADA = timedelta(minutes=5)  # el respaldo tiene cuota: no más de 1 consulta/5 min por liga


def partidos_a_vigilar(conn):
    ahora = ahora_utc()
    return conn.execute(
        """SELECT p.*, c.apifootball_id, c.temporada_anual FROM partidos p
           JOIN competiciones c ON c.codigo = p.competicion
           WHERE p.manual = 0 AND p.estado IN ('programado', 'en_juego')
             AND p.inicio_utc <= ? AND p.inicio_utc >= ?""",
        (a_iso(ahora + timedelta(minutes=2)), a_iso(ahora - timedelta(hours=5)))).fetchall()


def vigilar(conn, ultimo_respaldo: dict) -> int:
    filas = partidos_a_vigilar(conn)
    if not filas:
        return 0
    por_liga: dict = {}
    for f in filas:
        por_liga.setdefault(f["competicion"], []).append(f)

    afectadas = set()
    for codigo, lista in por_liga.items():
        fechas = set()
        for f in lista:
            d = de_iso(f["inicio_utc"]).date()
            fechas.update({d, d - timedelta(days=1)})  # ESPN agrupa por día de EE. UU.
        nuevos = []
        try:
            data = espn.descargar(codigo)
            nuevos += espn.partidos_de(data, codigo, espn.descargar_resumen)
            for d in sorted(fechas):
                nuevos += espn.partidos_de(espn.descargar(codigo, d), codigo, espn.descargar_resumen)
        except ErrorFuente as e:
            log.warning("ESPN falló en vivo (%s): %s", codigo, e)
            ahora = ahora_utc()
            if (apifootball.disponible() and lista[0]["apifootball_id"]
                    and ahora - ultimo_respaldo.get(codigo, ahora - RESPALDO_CADA) >= RESPALDO_CADA):
                ultimo_respaldo[codigo] = ahora
                for d in sorted({de_iso(f["inicio_utc"]).date() for f in lista}):
                    try:
                        nuevos += apifootball.partidos_del_dia(codigo, lista[0]["apifootball_id"], d,
                                                              bool(lista[0]["temporada_anual"]))
                    except ErrorFuente as e2:
                        log.warning("Respaldo falló (%s): %s", codigo, e2)

        for p in nuevos:
            pid, antes, cambio = guardar_partido(conn, p)
            if cambio:
                if antes != p["estado"]:
                    log.info("%s vs %s: %s -> %s", p["local"], p["visitante"], antes, p["estado"])
                afectadas.update(quinielas_con_partido(conn, pid))
    for qid in afectadas:
        recalcular_quiniela(conn, qid)
    conn.commit()
    return len(filas)


def segundos_de_siesta(conn, proxima_exploracion) -> float:
    ahora = ahora_utc()
    fila = conn.execute("SELECT MIN(inicio_utc) FROM partidos WHERE estado='programado' AND inicio_utc > ?",
                        (a_iso(ahora),)).fetchone()
    espera = SIESTA_MAX
    if fila and fila[0]:
        espera = min(espera, (de_iso(fila[0]) - timedelta(minutes=2) - ahora).total_seconds())
    espera = min(espera, (proxima_exploracion - ahora).total_seconds())
    return max(30, espera)


def ciclo(una_vez: bool = False):
    conn = conectar()
    inicializar(conn)
    proxima_exploracion = ahora_utc()
    ultimo_respaldo: dict = {}
    while True:
        try:
            if ahora_utc() >= proxima_exploracion:
                explorar(conn)
                proxima_exploracion = ahora_utc() + CADA_EXPLORACION
            vigilados = vigilar(conn, ultimo_respaldo)
        except Exception:  # el robot nunca debe morir por un error puntual
            log.exception("Error en el ciclo")
            vigilados = 0
        if una_vez:
            break
        espera = INTERVALO_VIVO if vigilados else segundos_de_siesta(conn, proxima_exploracion)
        log.debug("Durmiendo %.0f s (%d partidos vigilados)", espera, vigilados)
        time.sleep(espera)


def main():
    ap = argparse.ArgumentParser(description="Robot de datos de la Quiniela")
    ap.add_argument("--una-vez", action="store_true")
    args = ap.parse_args()
    (RAIZ / "data").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(RAIZ / "data" / "robot.log", encoding="utf-8")])
    ciclo(args.una_vez)


if __name__ == "__main__":
    main()
