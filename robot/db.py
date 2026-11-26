"""Acceso a la base de datos SQLite."""
from __future__ import annotations

import os
import sqlite3
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher
from pathlib import Path

from .catalogo import COMPETICIONES
from .puntuacion import calcular_tabla
from .tiempo import a_iso, ahora_utc, de_iso

RAIZ = Path(__file__).resolve().parents[1]
# Se puede mover con la variable QUINIELA_DB (recomendado fuera de OneDrive/Dropbox:
# SQLite crea archivos temporales que los servicios de sincronización no manejan bien).
RUTA_DB = Path(os.environ.get("QUINIELA_DB", RAIZ / "data" / "quiniela.db"))

_CAMPOS_PARTIDO = ["inicio_utc", "local", "visitante", "local_abrev", "visitante_abrev",
                   "local_logo", "visitante_logo", "estado", "minuto", "goles_local",
                   "goles_visitante", "goles_local_90", "goles_visitante_90", "revisar"]


def conectar(ruta: Path | str = RUTA_DB) -> sqlite3.Connection:
    if str(ruta) != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: el servidor web abre la conexión en un hilo y la usa en otro
    # (cada petición tiene su propia conexión, nunca se comparte entre peticiones).
    conn = sqlite3.connect(ruta, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(ruta) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")  # la app lee mientras el robot escribe
    return conn


def inicializar(conn: sqlite3.Connection):
    conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
    for codigo, nombre, pais, af_id, anual in COMPETICIONES:
        conn.execute(
            """INSERT INTO competiciones (codigo, nombre, pais, apifootball_id, temporada_anual)
               VALUES (?,?,?,?,?)
               ON CONFLICT(codigo) DO UPDATE SET nombre=excluded.nombre, pais=excluded.pais,
                 apifootball_id=excluded.apifootball_id, temporada_anual=excluded.temporada_anual""",
            (codigo, nombre, pais, af_id, int(anual)))
    conn.commit()


# ---------- partidos ----------

def _norm(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode().lower()
    for ruido in ("club", "deportivo", "fc", "cf", "cd", "atletico", "de ", "unam", "."):
        s = s.replace(ruido, " ")
    return " ".join(s.split())


def _parecido(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if a and b and (a in b or b in a):
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def buscar_equivalente(conn, p: dict):
    """Para datos del respaldo: encuentra el mismo partido ya guardado (misma liga, ±3 h, nombres parecidos)."""
    t = de_iso(p["inicio_utc"])
    filas = conn.execute(
        "SELECT * FROM partidos WHERE competicion=? AND inicio_utc BETWEEN ? AND ?",
        (p["competicion"], a_iso(t - timedelta(hours=3)), a_iso(t + timedelta(hours=3)))).fetchall()
    mejor, puntaje = None, 0.0
    for f in filas:
        s = min(_parecido(f["local"], p["local"]), _parecido(f["visitante"], p["visitante"]))
        if s > puntaje:
            mejor, puntaje = f, s
    return mejor if puntaje >= 0.6 else None


def guardar_partido(conn, p: dict) -> tuple[int, str | None, bool]:
    """Inserta o actualiza. Regresa (partido_id, estado_anterior, cambio_relevante)."""
    actual = None
    if p.get("id_espn"):
        actual = conn.execute("SELECT * FROM partidos WHERE id_espn=?", (p["id_espn"],)).fetchone()
    if actual is None and p.get("id_apifootball"):
        actual = conn.execute("SELECT * FROM partidos WHERE id_apifootball=?",
                              (p["id_apifootball"],)).fetchone() or buscar_equivalente(conn, p)

    ahora = a_iso(ahora_utc())
    if actual is None:
        cols = ["competicion", "id_espn", "id_apifootball", "fuente"] + _CAMPOS_PARTIDO + ["actualizado_utc"]
        vals = [p["competicion"], p.get("id_espn"), p.get("id_apifootball"), p["fuente"]] + \
               [int(p[c]) if c == "revisar" else p[c] for c in _CAMPOS_PARTIDO] + [ahora]
        cur = conn.execute(f"INSERT INTO partidos ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        return cur.lastrowid, None, True

    if actual["manual"]:  # el admin lo corrigió: no se toca
        return actual["id"], actual["estado"], False

    campos = list(_CAMPOS_PARTIDO)
    if p["fuente"] != "espn":  # el respaldo no sobreescribe nombres/logos de ESPN
        campos = [c for c in campos if c not in ("local", "visitante", "local_abrev",
                                                   "visitante_abrev", "local_logo", "visitante_logo")]
    cambio = any(actual[c] != (int(p[c]) if c == "revisar" else p[c])
                 for c in ("estado", "goles_local_90", "goles_visitante_90"))
    asignaciones = [f"{c}=?" for c in campos] + ["fuente=?", "actualizado_utc=?"]
    vals = [int(p[c]) if c == "revisar" else p[c] for c in campos] + [p["fuente"], ahora]
    if p.get("id_apifootball"):
        asignaciones.append("id_apifootball=COALESCE(id_apifootball, ?)")
        vals.append(p["id_apifootball"])
    conn.execute(f"UPDATE partidos SET {', '.join(asignaciones)} WHERE id=?", [*vals, actual["id"]])
    return actual["id"], actual["estado"], cambio


# ---------- tabla de posiciones ----------

def quinielas_con_partido(conn, partido_id: int) -> list[int]:
    return [r[0] for r in conn.execute(
        """SELECT DISTINCT q.id FROM quinielas q JOIN quiniela_partidos qp ON qp.quiniela_id=q.id
           WHERE qp.partido_id=? AND q.estado != 'cerrada'""", (partido_id,))]


def recalcular_quiniela(conn, quiniela_id: int):
    partidos, estelar = {}, None
    for r in conn.execute(
            """SELECT p.id, p.estado, p.goles_local_90, p.goles_visitante_90, qp.es_estelar
               FROM quiniela_partidos qp JOIN partidos p ON p.id = qp.partido_id
               WHERE qp.quiniela_id=?""", (quiniela_id,)):
        partidos[r["id"]] = dict(r)
        if r["es_estelar"]:
            estelar = r["id"]

    participantes = [r[0] for r in conn.execute(
        "SELECT usuario_id FROM participaciones WHERE quiniela_id=?", (quiniela_id,))]
    pronos: dict = {}
    for r in conn.execute("SELECT usuario_id, partido_id, pick FROM pronosticos WHERE quiniela_id=?",
                          (quiniela_id,)):
        pronos.setdefault(r[0], {})[r[1]] = r[2]
    desemp = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT usuario_id, goles_local, goles_visitante FROM desempates WHERE quiniela_id=?", (quiniela_id,))}

    filas, provisional = calcular_tabla(partidos, pronos, desemp, participantes, estelar, en_vivo=True)
    ahora = a_iso(ahora_utc())
    previas = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT usuario_id, posicion, posicion_anterior FROM posiciones WHERE quiniela_id=?", (quiniela_id,))}

    def anterior(f):
        # Si la posición no cambió, conservamos la referencia previa para que la flecha no desaparezca.
        if f.usuario_id not in previas:
            return None
        pos, ant = previas[f.usuario_id]
        return ant if pos == f.posicion else pos

    conn.execute("DELETE FROM posiciones WHERE quiniela_id=?", (quiniela_id,))
    conn.executemany(
        """INSERT INTO posiciones (quiniela_id, usuario_id, posicion, posicion_anterior, puntos, exacto_estelar,
                                   distancia, provisional, actualizado_utc) VALUES (?,?,?,?,?,?,?,?,?)""",
        [(quiniela_id, f.usuario_id, f.posicion, anterior(f), f.puntos, int(f.exacto_estelar), f.distancia,
          int(provisional), ahora) for f in filas])
    hay_en_juego = any(p["estado"] == "en_juego" for p in partidos.values())
    nuevo_estado = "cerrada" if not provisional else ("en_juego" if hay_en_juego else None)
    if nuevo_estado:
        conn.execute("UPDATE quinielas SET estado=? WHERE id=?", (nuevo_estado, quiniela_id))
    return filas
