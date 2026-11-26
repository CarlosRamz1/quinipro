"""API de QuiniPro + archivos de la PWA.

Correr en local:   uvicorn app.main:app --reload --port 8000
La base de datos es la misma que usa el robot (robot.db.RUTA_DB o la variable QUINIELA_DB).
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from robot.db import RUTA_DB, conectar, inicializar, recalcular_quiniela
from robot.puntuacion import ANULADOS, puede_editar
from robot.tiempo import a_iso, ahora_utc, de_iso

from .seguridad import hash_token, nuevo_codigo, nuevo_token

WEB = Path(__file__).resolve().parents[1] / "web"
ADMINS = ("dueno", "coadmin")


# ---------------------------------------------------------------- base de datos y sesión

def crear_app(ruta_db=None) -> FastAPI:
    app = FastAPI(title="QuiniPro", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.ruta_db = str(ruta_db or RUTA_DB)
    c = conectar(app.state.ruta_db)
    inicializar(c)
    c.close()
    _rutas(app)
    if WEB.exists():
        app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app


def db(request: Request):
    conn = conectar(request.app.state.ruta_db)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _usuario_por_token(conn, token: Optional[str]):
    if not token:
        return None
    return conn.execute("SELECT * FROM usuarios WHERE token_hash=?", (hash_token(token),)).fetchone()


def _token_de(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def usuario_opcional(conn=Depends(db), authorization: Optional[str] = Header(None)):
    return _usuario_por_token(conn, _token_de(authorization))


def usuario(u=Depends(usuario_opcional)):
    if u is None:
        raise HTTPException(401, "Sesión no válida. Vuelve a entrar con tu enlace de invitación.")
    return u


def _rol(conn, grupo_id: int, u) -> Optional[str]:
    r = conn.execute("SELECT rol FROM miembros WHERE grupo_id=? AND usuario_id=?", (grupo_id, u["id"])).fetchone()
    return r[0] if r else None


def _exigir_miembro(conn, grupo_id: int, u) -> str:
    rol = _rol(conn, grupo_id, u)
    if rol is None and not u["es_superadmin"]:
        raise HTTPException(403, "No eres parte de este grupo.")
    return rol or "superadmin"


def _exigir_admin(conn, grupo_id: int, u) -> str:
    rol = _exigir_miembro(conn, grupo_id, u)
    if rol not in ADMINS and not u["es_superadmin"]:
        raise HTTPException(403, "Solo los administradores del grupo pueden hacer esto.")
    return rol


def _quiniela(conn, qid: int):
    q = conn.execute("SELECT * FROM quinielas WHERE id=?", (qid,)).fetchone()
    if not q:
        raise HTTPException(404, "Esa quiniela no existe.")
    return q


def _bitacora(conn, grupo_id, actor_id, accion, objetivo_id=None, detalle=None):
    conn.execute("INSERT INTO bitacora (grupo_id, actor_id, accion, objetivo_id, detalle) VALUES (?,?,?,?,?)",
                 (grupo_id, actor_id, accion, objetivo_id, detalle))


def _asegurar_participacion(conn, qid: int, uid: int):
    conn.execute("INSERT OR IGNORE INTO participaciones (quiniela_id, usuario_id) VALUES (?,?)", (qid, uid))


def _nombre_valido(nombre: str) -> str:
    nombre = " ".join((nombre or "").split())
    if not 2 <= len(nombre) <= 40:
        raise HTTPException(422, "Escribe tu nombre (de 2 a 40 letras).")
    return nombre


def _partido_publico(p) -> dict:
    return {k: p[k] for k in ("id", "competicion", "inicio_utc", "local", "visitante", "local_abrev",
                              "visitante_abrev", "local_logo", "visitante_logo", "estado", "minuto",
                              "goles_local", "goles_visitante", "goles_local_90", "goles_visitante_90")}


def _ya_empezo(p, ahora) -> bool:
    return p["estado"] != "programado" or ahora >= de_iso(p["inicio_utc"])


# ---------------------------------------------------------------- modelos de entrada

class Unirse(BaseModel):
    codigo: str
    nombre: Optional[str] = None


class NuevoGrupo(BaseModel):
    codigo: Optional[str] = None
    nombre: str
    tu_nombre: Optional[str] = None  # si quien crea el grupo todavía no tiene cuenta


class CambioRol(BaseModel):
    rol: Literal["coadmin", "participante"]


class Transferir(BaseModel):
    usuario_id: int


class NuevaQuiniela(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    tipo: Literal["jornada", "mixta", "torneo"] = "mixta"
    partidos: list[int] = Field(min_length=1, max_length=20)
    estelar: int
    cuota_texto: Optional[str] = Field(None, max_length=30)


class Pick(BaseModel):
    partido_id: int
    pick: Optional[Literal["L", "E", "V"]] = None


class Desempate(BaseModel):
    goles_local: int = Field(ge=0, le=20)
    goles_visitante: int = Field(ge=0, le=20)


class Pago(BaseModel):
    pagado: bool


class NuevoCodigo(BaseModel):
    nota: Optional[str] = Field(None, max_length=80)


class Correccion(BaseModel):
    estado: Literal["final", "pospuesto", "suspendido", "cancelado"] = "final"
    goles_local_90: Optional[int] = Field(None, ge=0, le=30)
    goles_visitante_90: Optional[int] = Field(None, ge=0, le=30)


# ---------------------------------------------------------------- rutas

def _rutas(app: FastAPI):

    # ---------- entrada y perfil

    @app.post("/api/unirse")
    def unirse(datos: Unirse, conn=Depends(db), u=Depends(usuario_opcional)):
        g = conn.execute("SELECT * FROM grupos WHERE codigo_invitacion=?", (datos.codigo.strip().upper(),)).fetchone()
        if not g:
            raise HTTPException(404, "Ese enlace de invitación ya no es válido. Pide uno nuevo al admin del grupo.")
        token = None
        if u is None:
            token = nuevo_token()
            uid = conn.execute("INSERT INTO usuarios (nombre, token_hash) VALUES (?,?)",
                               (_nombre_valido(datos.nombre), hash_token(token))).lastrowid
        else:
            uid = u["id"]
        conn.execute("INSERT OR IGNORE INTO miembros (grupo_id, usuario_id) VALUES (?,?)", (g["id"], uid))
        for q in conn.execute("SELECT id FROM quinielas WHERE grupo_id=? AND estado!='cerrada'", (g["id"],)).fetchall():
            _asegurar_participacion(conn, q[0], uid)
            recalcular_quiniela(conn, q[0])
        return {"token": token, "grupo_id": g["id"], "grupo": g["nombre"]}

    @app.get("/api/invitacion/{codigo}")
    def ver_invitacion(codigo: str, conn=Depends(db)):
        g = conn.execute("SELECT id, nombre FROM grupos WHERE codigo_invitacion=?", (codigo.strip().upper(),)).fetchone()
        if not g:
            raise HTTPException(404, "Ese enlace de invitación ya no es válido.")
        n = conn.execute("SELECT COUNT(*) FROM miembros WHERE grupo_id=?", (g["id"],)).fetchone()[0]
        q = conn.execute("""SELECT q.nombre, COUNT(qp.partido_id) FROM quinielas q
                            LEFT JOIN quiniela_partidos qp ON qp.quiniela_id=q.id
                            WHERE q.grupo_id=? AND q.estado!='cerrada' GROUP BY q.id ORDER BY q.id DESC LIMIT 1""",
                         (g["id"],)).fetchone()
        return {"grupo": g["nombre"], "participantes": n,
                "quiniela": {"nombre": q[0], "partidos": q[1]} if q else None}

    @app.get("/api/yo")
    def yo(conn=Depends(db), u=Depends(usuario)):
        grupos = []
        for g in conn.execute("""SELECT g.id, g.nombre, m.rol FROM miembros m JOIN grupos g ON g.id=m.grupo_id
                                 WHERE m.usuario_id=? ORDER BY m.unido_utc""", (u["id"],)):
            # Todas las quinielas activas del grupo (puede haber varias a la vez) y la última terminada.
            qs = [dict(r) for r in conn.execute(
                """SELECT q.id, q.nombre, q.estado,
                          (SELECT COUNT(*) FROM quiniela_partidos qp WHERE qp.quiniela_id=q.id) AS partidos,
                          (SELECT COUNT(*) FROM pronosticos pr WHERE pr.quiniela_id=q.id AND pr.usuario_id=?) AS mis_picks
                   FROM quinielas q WHERE q.grupo_id=? ORDER BY (q.estado='cerrada'), q.id DESC""", (u["id"], g["id"]))]
            activas = [q for q in qs if q["estado"] != "cerrada"]
            terminada = next((q for q in qs if q["estado"] == "cerrada"), None)
            grupos.append({"id": g["id"], "nombre": g["nombre"], "rol": g["rol"],
                           "quinielas": activas + ([terminada] if terminada else []),
                           "quiniela_actual": qs[0] if qs else None})
        return {"usuario": {"id": u["id"], "nombre": u["nombre"], "es_superadmin": bool(u["es_superadmin"])},
                "grupos": grupos}

    # ---------- grupos

    @app.post("/api/grupos")
    def crear_grupo(datos: NuevoGrupo, conn=Depends(db), u=Depends(usuario_opcional)):
        nombre = " ".join(datos.nombre.split())
        if not 2 <= len(nombre) <= 40:
            raise HTTPException(422, "El nombre del grupo debe tener de 2 a 40 letras.")
        c = None
        if u is None or not u["es_superadmin"]:
            c = conn.execute("SELECT * FROM codigos_grupo WHERE codigo=? AND usado_por IS NULL",
                             ((datos.codigo or "").strip().upper(),)).fetchone()
            if not c:
                raise HTTPException(403, "Necesitas un código válido para crear un grupo. Pídeselo al administrador de QuiniPro.")
        token = None
        if u is None:
            token = nuevo_token()
            uid = conn.execute("INSERT INTO usuarios (nombre, token_hash) VALUES (?,?)",
                               (_nombre_valido(datos.tu_nombre), hash_token(token))).lastrowid
            u = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        if c is not None:
            conn.execute("UPDATE codigos_grupo SET usado_por=?, usado_utc=? WHERE codigo=?",
                         (u["id"], a_iso(ahora_utc()), c["codigo"]))
        gid = conn.execute("INSERT INTO grupos (nombre, codigo_invitacion, creado_por) VALUES (?,?,?)",
                           (nombre, nuevo_codigo(), u["id"])).lastrowid
        conn.execute("INSERT INTO miembros (grupo_id, usuario_id, rol) VALUES (?,?, 'dueno')", (gid, u["id"]))
        _bitacora(conn, gid, u["id"], "crear_grupo", u["id"], datos.codigo)
        return {"id": gid, "token": token}

    @app.get("/api/grupos/{gid}")
    def ver_grupo(gid: int, conn=Depends(db), u=Depends(usuario)):
        rol = _exigir_miembro(conn, gid, u)
        g = conn.execute("SELECT * FROM grupos WHERE id=?", (gid,)).fetchone()
        if not g:
            raise HTTPException(404, "Ese grupo no existe.")
        es_admin = rol in ADMINS or bool(u["es_superadmin"])
        quinielas = [dict(r) for r in conn.execute(
            """SELECT q.id, q.nombre, q.tipo, q.estado, q.cuota_texto, COUNT(qp.partido_id) AS partidos
               FROM quinielas q LEFT JOIN quiniela_partidos qp ON qp.quiniela_id=q.id
               WHERE q.grupo_id=? GROUP BY q.id ORDER BY q.id DESC""", (gid,))]
        return {"id": gid, "nombre": g["nombre"], "rol": rol, "es_admin": es_admin,
                "codigo_invitacion": g["codigo_invitacion"] if es_admin else None,
                "miembros": conn.execute("SELECT COUNT(*) FROM miembros WHERE grupo_id=?", (gid,)).fetchone()[0],
                "quinielas": quinielas}

    @app.get("/api/grupos/{gid}/miembros")
    def miembros(gid: int, conn=Depends(db), u=Depends(usuario)):
        _exigir_admin(conn, gid, u)
        return [dict(r) for r in conn.execute(
            """SELECT u.id, u.nombre, m.rol, m.unido_utc FROM miembros m JOIN usuarios u ON u.id=m.usuario_id
               WHERE m.grupo_id=? ORDER BY CASE m.rol WHEN 'dueno' THEN 0 WHEN 'coadmin' THEN 1 ELSE 2 END, u.nombre""",
            (gid,))]

    @app.put("/api/grupos/{gid}/miembros/{uid}/rol")
    def cambiar_rol(gid: int, uid: int, datos: CambioRol, conn=Depends(db), u=Depends(usuario)):
        if _exigir_miembro(conn, gid, u) != "dueno" and not u["es_superadmin"]:
            raise HTTPException(403, "Solo el dueño del grupo puede nombrar o quitar co-admins.")
        actual = conn.execute("SELECT rol FROM miembros WHERE grupo_id=? AND usuario_id=?", (gid, uid)).fetchone()
        if not actual:
            raise HTTPException(404, "Esa persona no está en el grupo.")
        if actual[0] == "dueno":
            raise HTTPException(409, "El dueño no cambia de rol; usa 'transferir grupo'.")
        conn.execute("UPDATE miembros SET rol=? WHERE grupo_id=? AND usuario_id=?", (datos.rol, gid, uid))
        _bitacora(conn, gid, u["id"], "cambiar_rol", uid, datos.rol)
        return {"ok": True}

    @app.post("/api/grupos/{gid}/transferir")
    def transferir(gid: int, datos: Transferir, conn=Depends(db), u=Depends(usuario)):
        if _exigir_miembro(conn, gid, u) != "dueno" and not u["es_superadmin"]:
            raise HTTPException(403, "Solo el dueño puede transferir el grupo.")
        if not conn.execute("SELECT 1 FROM miembros WHERE grupo_id=? AND usuario_id=?", (gid, datos.usuario_id)).fetchone():
            raise HTTPException(404, "Esa persona no está en el grupo.")
        conn.execute("UPDATE miembros SET rol='coadmin' WHERE grupo_id=? AND rol='dueno'", (gid,))
        conn.execute("UPDATE miembros SET rol='dueno' WHERE grupo_id=? AND usuario_id=?", (gid, datos.usuario_id))
        _bitacora(conn, gid, u["id"], "transferir", datos.usuario_id)
        return {"ok": True}

    @app.delete("/api/grupos/{gid}/miembros/{uid}")
    def sacar(gid: int, uid: int, conn=Depends(db), u=Depends(usuario)):
        rol_actor = _exigir_admin(conn, gid, u)
        objetivo = conn.execute("SELECT rol FROM miembros WHERE grupo_id=? AND usuario_id=?", (gid, uid)).fetchone()
        if not objetivo:
            raise HTTPException(404, "Esa persona no está en el grupo.")
        if objetivo[0] == "dueno":
            raise HTTPException(409, "No se puede sacar al dueño del grupo.")
        if objetivo[0] == "coadmin" and rol_actor != "dueno" and not u["es_superadmin"]:
            raise HTTPException(403, "Solo el dueño puede sacar a un co-admin.")
        conn.execute("DELETE FROM miembros WHERE grupo_id=? AND usuario_id=?", (gid, uid))
        for q in conn.execute("SELECT id FROM quinielas WHERE grupo_id=? AND estado!='cerrada'", (gid,)).fetchall():
            conn.execute("DELETE FROM participaciones WHERE quiniela_id=? AND usuario_id=?", (q[0], uid))
            recalcular_quiniela(conn, q[0])
        _bitacora(conn, gid, u["id"], "sacar", uid)
        return {"ok": True}

    @app.post("/api/grupos/{gid}/salir")
    def salir(gid: int, conn=Depends(db), u=Depends(usuario)):
        rol = _rol(conn, gid, u)
        if rol is None:
            raise HTTPException(404, "No estás en este grupo.")
        conn.execute("DELETE FROM miembros WHERE grupo_id=? AND usuario_id=?", (gid, u["id"]))
        if rol == "dueno":
            # Un grupo nunca se queda sin dueño: pasa al co-admin más antiguo, o al miembro más antiguo.
            sig = conn.execute("""SELECT usuario_id FROM miembros WHERE grupo_id=?
                                  ORDER BY (rol!='coadmin'), unido_utc LIMIT 1""", (gid,)).fetchone()
            if sig:
                conn.execute("UPDATE miembros SET rol='dueno' WHERE grupo_id=? AND usuario_id=?", (gid, sig[0]))
                _bitacora(conn, gid, u["id"], "transferir_auto", sig[0])
        for q in conn.execute("SELECT id FROM quinielas WHERE grupo_id=? AND estado!='cerrada'", (gid,)).fetchall():
            conn.execute("DELETE FROM participaciones WHERE quiniela_id=? AND usuario_id=?", (q[0], u["id"]))
            recalcular_quiniela(conn, q[0])
        _bitacora(conn, gid, u["id"], "salir", u["id"])
        return {"ok": True}

    @app.delete("/api/grupos/{gid}")
    def borrar_grupo(gid: int, conn=Depends(db), u=Depends(usuario)):
        g = conn.execute("SELECT nombre FROM grupos WHERE id=?", (gid,)).fetchone()
        if not g:
            raise HTTPException(404, "Ese grupo no existe.")
        if _rol(conn, gid, u) != "dueno" and not u["es_superadmin"]:
            raise HTTPException(403, "Solo el dueño del grupo o el administrador de QuiniPro pueden borrarlo.")
        conn.execute("DELETE FROM grupos WHERE id=?", (gid,))  # borra en cascada miembros, quinielas, picks y tablas
        _bitacora(conn, None, u["id"], "borrar_grupo", gid, g["nombre"])
        return {"ok": True}

    @app.post("/api/grupos/{gid}/invitacion")
    def nueva_invitacion(gid: int, conn=Depends(db), u=Depends(usuario)):
        _exigir_admin(conn, gid, u)
        codigo = nuevo_codigo()
        conn.execute("UPDATE grupos SET codigo_invitacion=? WHERE id=?", (codigo, gid))
        _bitacora(conn, gid, u["id"], "nueva_invitacion")
        return {"codigo_invitacion": codigo}

    # ---------- catálogo para armar quinielas

    @app.get("/api/competiciones")
    def competiciones(conn=Depends(db), u=Depends(usuario)):
        return [dict(r) for r in conn.execute(
            """SELECT codigo, nombre, pais, activa, fase, proximo_partido_utc FROM competiciones
               WHERE habilitada=1 ORDER BY activa DESC, proximo_partido_utc IS NULL, proximo_partido_utc""")]

    @app.get("/api/partidos")
    def partidos_disponibles(competicion: Optional[str] = None, dias: int = Query(10, ge=1, le=30),
                             conn=Depends(db), u=Depends(usuario)):
        ahora = ahora_utc()
        sql = """SELECT p.*, c.nombre AS competicion_nombre FROM partidos p JOIN competiciones c ON c.codigo=p.competicion
                 WHERE p.estado='programado' AND p.inicio_utc > ? AND p.inicio_utc <= ?"""
        args = [a_iso(ahora), a_iso(ahora + timedelta(days=dias))]
        if competicion:
            sql += " AND p.competicion=?"
            args.append(competicion)
        return [dict(_partido_publico(r), competicion_nombre=r["competicion_nombre"])
                for r in conn.execute(sql + " ORDER BY p.inicio_utc", args)]

    # ---------- quinielas

    @app.post("/api/grupos/{gid}/quinielas")
    def crear_quiniela(gid: int, datos: NuevaQuiniela, conn=Depends(db), u=Depends(usuario)):
        _exigir_admin(conn, gid, u)
        ids = list(dict.fromkeys(datos.partidos))
        if datos.estelar not in ids:
            raise HTTPException(422, "El partido estelar debe estar entre los partidos elegidos.")
        ahora = ahora_utc()
        filas = conn.execute(f"SELECT * FROM partidos WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()
        if len(filas) != len(ids):
            raise HTTPException(422, "Algún partido no existe.")
        if any(_ya_empezo(p, ahora) for p in filas):
            raise HTTPException(422, "Solo se pueden elegir partidos que no han empezado.")
        orden = {p["id"]: p["inicio_utc"] for p in filas}
        qid = conn.execute("INSERT INTO quinielas (grupo_id, nombre, tipo, cuota_texto) VALUES (?,?,?,?)",
                           (gid, datos.nombre.strip(), datos.tipo, datos.cuota_texto)).lastrowid
        for i, pid in enumerate(sorted(ids, key=lambda x: orden[x])):
            conn.execute("INSERT INTO quiniela_partidos (quiniela_id, partido_id, es_estelar, orden) VALUES (?,?,?,?)",
                         (qid, pid, int(pid == datos.estelar), i))
        for m in conn.execute("SELECT usuario_id FROM miembros WHERE grupo_id=?", (gid,)).fetchall():
            _asegurar_participacion(conn, qid, m[0])
        recalcular_quiniela(conn, qid)
        _bitacora(conn, gid, u["id"], "crear_quiniela", qid, datos.nombre)
        return {"id": qid}

    @app.get("/api/quinielas/{qid}")
    def ver_quiniela(qid: int, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        rol = _exigir_miembro(conn, q["grupo_id"], u)
        g = conn.execute("SELECT nombre FROM grupos WHERE id=?", (q["grupo_id"],)).fetchone()
        ahora = ahora_utc()
        picks = {r[0]: r[1] for r in conn.execute(
            "SELECT partido_id, pick FROM pronosticos WHERE quiniela_id=? AND usuario_id=?", (qid, u["id"]))}
        partidos, estelar = [], None
        for r in conn.execute(
                """SELECT p.*, qp.es_estelar, c.nombre AS competicion_nombre FROM quiniela_partidos qp
                   JOIN partidos p ON p.id=qp.partido_id JOIN competiciones c ON c.codigo=p.competicion
                   WHERE qp.quiniela_id=? ORDER BY qp.orden""", (qid,)):
            d = dict(_partido_publico(r), competicion_nombre=r["competicion_nombre"], es_estelar=bool(r["es_estelar"]),
                     mi_pick=picks.get(r["id"]),
                     editable=q["estado"] != "cerrada" and puede_editar(dict(r), ahora),
                     anulado=r["estado"] in ANULADOS)
            partidos.append(d)
            if d["es_estelar"]:
                estelar = d
        des = conn.execute("SELECT goles_local, goles_visitante FROM desempates WHERE quiniela_id=? AND usuario_id=?",
                           (qid, u["id"])).fetchone()
        part = conn.execute("SELECT pagado FROM participaciones WHERE quiniela_id=? AND usuario_id=?",
                            (qid, u["id"])).fetchone()
        return {"id": qid, "nombre": q["nombre"], "tipo": q["tipo"], "estado": q["estado"],
                "cuota_texto": q["cuota_texto"], "grupo": {"id": q["grupo_id"], "nombre": g["nombre"]},
                "rol": rol, "es_admin": rol in ADMINS or bool(u["es_superadmin"]),
                "partidos": partidos, "llenos": len([p for p in partidos if p["mi_pick"]]),
                "mi_desempate": dict(des) if des else None,
                "desempate_editable": bool(estelar and estelar["editable"]),
                "pagado": bool(part and part[0]), "ahora_utc": a_iso(ahora)}

    @app.delete("/api/quinielas/{qid}")
    def borrar_quiniela(qid: int, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        if _rol(conn, q["grupo_id"], u) != "dueno" and not u["es_superadmin"]:
            raise HTTPException(403, "Solo el dueño del grupo puede borrar quinielas.")
        conn.execute("DELETE FROM quinielas WHERE id=?", (qid,))
        _bitacora(conn, q["grupo_id"], u["id"], "borrar_quiniela", qid, q["nombre"])
        return {"ok": True}

    @app.put("/api/quinielas/{qid}/picks")
    def guardar_pick(qid: int, datos: Pick, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        if _rol(conn, q["grupo_id"], u) is None:
            raise HTTPException(403, "No eres parte de este grupo.")
        p = conn.execute("""SELECT p.* FROM quiniela_partidos qp JOIN partidos p ON p.id=qp.partido_id
                            WHERE qp.quiniela_id=? AND qp.partido_id=?""", (qid, datos.partido_id)).fetchone()
        if not p:
            raise HTTPException(404, "Ese partido no es de esta quiniela.")
        if q["estado"] == "cerrada" or not puede_editar(dict(p), ahora_utc()):
            raise HTTPException(409, "Este partido ya empezó: tu pick quedó cerrado.")
        _asegurar_participacion(conn, qid, u["id"])
        if datos.pick is None:
            conn.execute("DELETE FROM pronosticos WHERE quiniela_id=? AND usuario_id=? AND partido_id=?",
                         (qid, u["id"], datos.partido_id))
        else:
            conn.execute("""INSERT INTO pronosticos (quiniela_id, usuario_id, partido_id, pick) VALUES (?,?,?,?)
                            ON CONFLICT(quiniela_id, usuario_id, partido_id)
                            DO UPDATE SET pick=excluded.pick, actualizado_utc=strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
                         (qid, u["id"], datos.partido_id, datos.pick))
        return {"ok": True}

    @app.put("/api/quinielas/{qid}/desempate")
    def guardar_desempate(qid: int, datos: Desempate, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        if _rol(conn, q["grupo_id"], u) is None:
            raise HTTPException(403, "No eres parte de este grupo.")
        p = conn.execute("""SELECT p.* FROM quiniela_partidos qp JOIN partidos p ON p.id=qp.partido_id
                            WHERE qp.quiniela_id=? AND qp.es_estelar=1""", (qid,)).fetchone()
        if not p or q["estado"] == "cerrada" or not puede_editar(dict(p), ahora_utc()):
            raise HTTPException(409, "El partido estelar ya empezó: el marcador quedó cerrado.")
        _asegurar_participacion(conn, qid, u["id"])
        conn.execute("""INSERT INTO desempates (quiniela_id, usuario_id, goles_local, goles_visitante) VALUES (?,?,?,?)
                        ON CONFLICT(quiniela_id, usuario_id) DO UPDATE SET goles_local=excluded.goles_local,
                        goles_visitante=excluded.goles_visitante, actualizado_utc=strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
                     (qid, u["id"], datos.goles_local, datos.goles_visitante))
        return {"ok": True}

    @app.get("/api/quinielas/{qid}/tabla")
    def tabla(qid: int, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        _exigir_miembro(conn, q["grupo_id"], u)
        n_part = conn.execute("SELECT COUNT(*) FROM participaciones WHERE quiniela_id=?", (qid,)).fetchone()[0]
        n_pos = conn.execute("SELECT COUNT(*) FROM posiciones WHERE quiniela_id=?", (qid,)).fetchone()[0]
        if n_part != n_pos:
            recalcular_quiniela(conn, qid)
        filas = [dict(r, es_yo=r["usuario_id"] == u["id"]) for r in conn.execute(
            """SELECT po.usuario_id, u.nombre, po.posicion, po.posicion_anterior, po.puntos, po.exacto_estelar,
                      po.distancia, po.provisional, pa.pagado
               FROM posiciones po JOIN usuarios u ON u.id=po.usuario_id
               LEFT JOIN participaciones pa ON pa.quiniela_id=po.quiniela_id AND pa.usuario_id=po.usuario_id
               WHERE po.quiniela_id=? ORDER BY po.posicion, u.nombre""", (qid,))]
        estados = [r[0] for r in conn.execute(
            """SELECT p.estado FROM quiniela_partidos qp JOIN partidos p ON p.id=qp.partido_id
               WHERE qp.quiniela_id=?""", (qid,))]
        return {"quiniela": {"id": qid, "nombre": q["nombre"], "estado": q["estado"]},
                "terminados": sum(e == "final" for e in estados), "en_juego": sum(e == "en_juego" for e in estados),
                "total": len(estados), "provisional": any(f["provisional"] for f in filas) if filas else True,
                "filas": filas}

    @app.get("/api/quinielas/{qid}/partidos/{pid}")
    def picks_de_partido(qid: int, pid: int, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        _exigir_miembro(conn, q["grupo_id"], u)
        p = conn.execute("""SELECT p.*, qp.es_estelar, c.nombre AS competicion_nombre FROM quiniela_partidos qp
                            JOIN partidos p ON p.id=qp.partido_id JOIN competiciones c ON c.codigo=p.competicion
                            WHERE qp.quiniela_id=? AND qp.partido_id=?""", (qid, pid)).fetchone()
        if not p:
            raise HTTPException(404, "Ese partido no es de esta quiniela.")
        mio = conn.execute("SELECT pick FROM pronosticos WHERE quiniela_id=? AND usuario_id=? AND partido_id=?",
                           (qid, u["id"], pid)).fetchone()
        base = dict(_partido_publico(p), competicion_nombre=p["competicion_nombre"], es_estelar=bool(p["es_estelar"]),
                    mi_pick=mio[0] if mio else None)
        if not _ya_empezo(p, ahora_utc()):
            # Regla: nadie (ni admins) ve picks ajenos antes del pitazo.
            return dict(base, revelado=False)
        picks = [dict(r) for r in conn.execute(
            """SELECT u.id AS usuario_id, u.nombre, pr.pick FROM participaciones pa JOIN usuarios u ON u.id=pa.usuario_id
               LEFT JOIN pronosticos pr ON pr.quiniela_id=pa.quiniela_id AND pr.usuario_id=pa.usuario_id AND pr.partido_id=?
               WHERE pa.quiniela_id=? ORDER BY u.nombre""", (pid, qid))]
        conteo = {k: sum(1 for x in picks if x["pick"] == k) for k in ("L", "E", "V")}
        return dict(base, revelado=True, conteo=conteo, sin_pick=sum(1 for x in picks if not x["pick"]), picks=picks)

    @app.get("/api/quinielas/{qid}/pagos")
    def pagos(qid: int, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        _exigir_admin(conn, q["grupo_id"], u)
        return [dict(r) for r in conn.execute(
            """SELECT u.id AS usuario_id, u.nombre, pa.pagado FROM participaciones pa JOIN usuarios u ON u.id=pa.usuario_id
               WHERE pa.quiniela_id=? ORDER BY pa.pagado, u.nombre""", (qid,))]

    @app.put("/api/quinielas/{qid}/pagos/{uid}")
    def marcar_pago(qid: int, uid: int, datos: Pago, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        _exigir_admin(conn, q["grupo_id"], u)
        cur = conn.execute("UPDATE participaciones SET pagado=? WHERE quiniela_id=? AND usuario_id=?",
                           (int(datos.pagado), qid, uid))
        if cur.rowcount == 0:
            raise HTTPException(404, "Esa persona no participa en esta quiniela.")
        _bitacora(conn, q["grupo_id"], u["id"], "pago" if datos.pagado else "pago_pendiente", uid, str(qid))
        return {"ok": True}

    @app.put("/api/quinielas/{qid}/pagos")
    def marcar_todos(qid: int, datos: Pago, conn=Depends(db), u=Depends(usuario)):
        q = _quiniela(conn, qid)
        _exigir_admin(conn, q["grupo_id"], u)
        conn.execute("UPDATE participaciones SET pagado=? WHERE quiniela_id=?", (int(datos.pagado), qid))
        _bitacora(conn, q["grupo_id"], u["id"], "pago_todos", None, str(qid))
        return {"ok": True}

    # ---------- en vivo (Server-Sent Events)

    @app.get("/api/quinielas/{qid}/eventos")
    async def eventos(qid: int, request: Request, token: str = Query(...)):
        conn = conectar(request.app.state.ruta_db)
        try:
            u = _usuario_por_token(conn, token)
            if u is None:
                raise HTTPException(401, "Sesión no válida.")
            q = _quiniela(conn, qid)
            _exigir_miembro(conn, q["grupo_id"], u)
        finally:
            conn.close()

        def firma():
            c = conectar(request.app.state.ruta_db)
            try:
                r = c.execute("""SELECT (SELECT MAX(actualizado_utc) FROM posiciones WHERE quiniela_id=?),
                                        (SELECT MAX(p.actualizado_utc) FROM quiniela_partidos qp
                                         JOIN partidos p ON p.id=qp.partido_id WHERE qp.quiniela_id=?)""",
                              (qid, qid)).fetchone()
                return f"{r[0]}|{r[1]}"
            finally:
                c.close()

        async def flujo():
            ultima = firma()
            yield "retry: 5000\n\n"
            for i in range(600):  # ~30 min; el navegador se reconecta solo
                if await request.is_disconnected():
                    break
                await asyncio.sleep(3)
                actual = firma()
                if actual != ultima:
                    ultima = actual
                    yield "event: actualizacion\ndata: {}\n\n"
                elif i % 5 == 4:
                    yield ": ping\n\n"

        return StreamingResponse(flujo(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---------- súper admin

    def _exigir_super(u):
        if not u["es_superadmin"]:
            raise HTTPException(403, "Solo el administrador de QuiniPro.")

    @app.post("/api/super/codigos")
    def crear_codigo(datos: NuevoCodigo, conn=Depends(db), u=Depends(usuario)):
        _exigir_super(u)
        codigo = nuevo_codigo()
        conn.execute("INSERT INTO codigos_grupo (codigo, nota) VALUES (?,?)", (codigo, datos.nota))
        return {"codigo": codigo}

    @app.get("/api/super/codigos")
    def listar_codigos(conn=Depends(db), u=Depends(usuario)):
        _exigir_super(u)
        return [dict(r) for r in conn.execute(
            """SELECT c.codigo, c.nota, c.creado_utc, c.usado_utc, us.nombre AS usado_por FROM codigos_grupo c
               LEFT JOIN usuarios us ON us.id=c.usado_por ORDER BY c.creado_utc DESC""")]

    @app.get("/api/super/revisar")
    def por_revisar(conn=Depends(db), u=Depends(usuario)):
        _exigir_super(u)
        return [dict(_partido_publico(r), competicion_nombre=r["competicion_nombre"]) for r in conn.execute(
            """SELECT p.*, c.nombre AS competicion_nombre FROM partidos p JOIN competiciones c ON c.codigo=p.competicion
               WHERE p.revisar=1 ORDER BY p.inicio_utc DESC""")]

    @app.get("/api/super/grupos")
    def todos_los_grupos(conn=Depends(db), u=Depends(usuario)):
        _exigir_super(u)
        return [dict(r) for r in conn.execute(
            """SELECT g.id, g.nombre, g.creado_utc, COUNT(m.usuario_id) AS miembros,
                      (SELECT us.nombre FROM miembros d JOIN usuarios us ON us.id=d.usuario_id
                       WHERE d.grupo_id=g.id AND d.rol='dueno') AS dueno
               FROM grupos g LEFT JOIN miembros m ON m.grupo_id=g.id GROUP BY g.id ORDER BY g.id DESC""")]

    @app.put("/api/super/partidos/{pid}")
    def corregir_partido(pid: int, datos: Correccion, conn=Depends(db), u=Depends(usuario)):
        _exigir_super(u)
        if not conn.execute("SELECT 1 FROM partidos WHERE id=?", (pid,)).fetchone():
            raise HTTPException(404, "Ese partido no existe.")
        if datos.estado == "final" and (datos.goles_local_90 is None or datos.goles_visitante_90 is None):
            raise HTTPException(422, "Para un partido final captura el marcador a 90'.")
        gl, gv = (datos.goles_local_90, datos.goles_visitante_90) if datos.estado == "final" else (None, None)
        conn.execute("""UPDATE partidos SET estado=?, goles_local_90=?, goles_visitante_90=?,
                        goles_local=COALESCE(goles_local, ?), goles_visitante=COALESCE(goles_visitante, ?),
                        revisar=0, manual=1, fuente='manual', minuto=NULL, actualizado_utc=? WHERE id=?""",
                     (datos.estado, gl, gv, gl, gv, a_iso(ahora_utc()), pid))
        afectadas = [r[0] for r in conn.execute(
            "SELECT DISTINCT quiniela_id FROM quiniela_partidos WHERE partido_id=?", (pid,))]
        for qid in afectadas:
            recalcular_quiniela(conn, qid)
        _bitacora(conn, None, u["id"], "corregir_partido", pid, f"{datos.estado} {gl}-{gv}")
        return {"ok": True, "quinielas_recalculadas": len(afectadas)}


app = crear_app()
