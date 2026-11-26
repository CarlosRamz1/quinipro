"""Explorador: revisa todas las ligas del catálogo, guarda sus partidos próximos
y marca cuáles están activas. Corre cada pocas horas."""
from __future__ import annotations

import logging
from datetime import timedelta

from .db import guardar_partido, quinielas_con_partido, recalcular_quiniela
from .proveedores import ErrorFuente, apifootball, espn
from .tiempo import MX, a_iso, ahora_utc, de_iso

log = logging.getLogger("robot.explorador")


def explorar(conn, dias: int = 10, codigos=None, descargador=espn.descargar,
             resumidor=espn.descargar_resumen, hoy=None) -> list[dict]:
    ahora = hoy or ahora_utc()  # `hoy` (datetime UTC) permite simular una fecha en pruebas
    hoy = ahora.astimezone(MX).date()
    desde, hasta = hoy - timedelta(days=1), hoy + timedelta(days=dias)

    sql = "SELECT * FROM competiciones WHERE habilitada=1"
    comps = conn.execute(sql).fetchall()
    if codigos:
        comps = [c for c in comps if c["codigo"] in codigos]

    resumen = []
    for c in comps:
        codigo = c["codigo"]
        info, partidos, fuente = {}, [], "espn"
        try:
            info, partidos = espn.partidos_en_rango(codigo, desde, hasta, descargador, resumidor)
        except ErrorFuente as e:
            log.warning("ESPN falló para %s: %s", codigo, e)
            # Respaldo solo para ligas que ya sabíamos activas, y solo hoy/mañana (cuidar la cuota).
            if c["activa"] and c["apifootball_id"] and apifootball.disponible():
                fuente = "apifootball"
                for d in (hoy, hoy + timedelta(days=1)):
                    try:
                        partidos += apifootball.partidos_del_dia(codigo, c["apifootball_id"], d,
                                                                bool(c["temporada_anual"]))
                    except ErrorFuente as e2:
                        log.warning("Respaldo falló para %s: %s", codigo, e2)
            if not partidos:
                resumen.append({"codigo": codigo, "nombre": c["nombre"], "error": str(e)})
                continue

        afectadas = set()
        for p in partidos:
            pid, _, cambio = guardar_partido(conn, p)
            if cambio:
                afectadas.update(quinielas_con_partido(conn, pid))
        for qid in afectadas:
            recalcular_quiniela(conn, qid)

        limite = ahora + timedelta(days=dias)
        futuros = [p for p in partidos
                   if p["estado"] in ("programado", "en_juego") and de_iso(p["inicio_utc"]) <= limite]
        proximo = min((p["inicio_utc"] for p in futuros if p["estado"] == "programado"), default=None)
        activa = bool(futuros)
        conn.execute(
            """UPDATE competiciones SET activa=?, temporada=COALESCE(?, temporada),
                 fase=COALESCE(?, fase), proximo_partido_utc=?, actualizado_utc=? WHERE codigo=?""",
            (int(activa), info.get("temporada"), info.get("fase"), proximo, a_iso(ahora), codigo))
        conn.commit()
        resumen.append({"codigo": codigo, "nombre": c["nombre"], "activa": activa, "fuente": fuente,
                        "partidos": len(partidos), "proximos": len(futuros),
                        "fase": info.get("fase"), "temporada": info.get("temporada")})
        log.info("%s: %d partidos (%d próximos) vía %s", codigo, len(partidos), len(futuros), fuente)
    return resumen
