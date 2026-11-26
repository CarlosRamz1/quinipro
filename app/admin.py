"""Comandos de administración (se corren en el servidor, nunca desde la app).

  python -m app.admin super "Tu Nombre"     crea tu usuario súper admin y te da tu enlace de acceso
  python -m app.admin enlace 1                   genera un enlace de acceso nuevo para el usuario 1
  python -m app.admin codigo "Para el grupo de X" crea un código para que alguien pueda crear su grupo
  python -m app.admin demo                       grupo de prueba con partidos reales próximos

La dirección base de los enlaces sale de la variable QUINIPRO_URL (por defecto http://localhost:8000).
"""
import argparse
import os
import sys

from robot.db import conectar, inicializar, recalcular_quiniela
from robot.tiempo import a_iso, ahora_utc

from .seguridad import hash_token, nuevo_codigo, nuevo_token

BASE = os.environ.get("QUINIPRO_URL", "http://localhost:8000").rstrip("/")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _enlace(token):
    return f"{BASE}/#/entrar/{token}"


def crear_super(conn, nombre):
    token = nuevo_token()
    uid = conn.execute("INSERT INTO usuarios (nombre, token_hash, es_superadmin) VALUES (?,?,1)",
                       (nombre, hash_token(token))).lastrowid
    conn.commit()
    return uid, token


def nuevo_enlace(conn, uid):
    token = nuevo_token()
    if conn.execute("UPDATE usuarios SET token_hash=? WHERE id=?", (hash_token(token), uid)).rowcount == 0:
        raise SystemExit(f"No existe el usuario {uid}")
    conn.commit()
    return token


def arranque(conn):
    """Para el servidor: si no existe súper admin y vienen QUINIPRO_SUPER_NOMBRE y QUINIPRO_SUPER_TOKEN
    en el entorno, lo crea con ese token. Así no hace falta una terminal en el VPS."""
    nombre, token = os.environ.get("QUINIPRO_SUPER_NOMBRE"), os.environ.get("QUINIPRO_SUPER_TOKEN")
    if not (nombre and token) or conn.execute("SELECT 1 FROM usuarios WHERE es_superadmin=1").fetchone():
        return False
    conn.execute("INSERT INTO usuarios (nombre, token_hash, es_superadmin) VALUES (?,?,1)", (nombre, hash_token(token)))
    conn.commit()
    return True


def crear_codigo(conn, nota):
    codigo = nuevo_codigo()
    conn.execute("INSERT INTO codigos_grupo (codigo, nota) VALUES (?,?)", (codigo, nota))
    conn.commit()
    return codigo


def demo(conn):
    """Grupo 'Los Compas' con el súper admin como dueño y una quiniela con los próximos partidos reales."""
    from robot.explorador import explorar
    try:
        explorar(conn, dias=7, codigos=["mex.1", "eng.1", "esp.1"])
    except Exception as e:  # sin internet: se usa lo que ya haya en la base
        print("Aviso: no se pudo consultar ESPN:", e)
    sup = conn.execute("SELECT id FROM usuarios WHERE es_superadmin=1 ORDER BY id LIMIT 1").fetchone()
    if not sup:
        raise SystemExit("Primero crea tu usuario: python -m app.admin super \"Tu nombre\"")
    ahora = a_iso(ahora_utc())
    partidos = conn.execute("""SELECT id, competicion FROM partidos WHERE estado='programado' AND inicio_utc>?
                               ORDER BY (competicion='mex.1') DESC, inicio_utc LIMIT 8""", (ahora,)).fetchall()
    if not partidos:
        raise SystemExit("No hay partidos próximos en la base. Corre primero: python probar.py --todas")
    gid = conn.execute("INSERT INTO grupos (nombre, codigo_invitacion, creado_por) VALUES ('Los Compas',?,?)",
                       (nuevo_codigo(), sup[0])).lastrowid
    conn.execute("INSERT INTO miembros (grupo_id, usuario_id, rol) VALUES (?,?,'dueno')", (gid, sup[0]))
    qid = conn.execute("INSERT INTO quinielas (grupo_id, nombre, tipo) VALUES (?, 'Fin de semana', 'mixta')",
                       (gid,)).lastrowid
    for i, p in enumerate(partidos):
        conn.execute("INSERT INTO quiniela_partidos (quiniela_id, partido_id, es_estelar, orden) VALUES (?,?,?,?)",
                     (qid, p[0], int(i == 0), i))
    conn.execute("INSERT INTO participaciones (quiniela_id, usuario_id) VALUES (?,?)", (qid, sup[0]))
    recalcular_quiniela(conn, qid)
    conn.commit()
    codigo = conn.execute("SELECT codigo_invitacion FROM grupos WHERE id=?", (gid,)).fetchone()[0]
    return gid, qid, codigo, len(partidos)


def main():
    ap = argparse.ArgumentParser(description="Administración de QuiniPro")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("super"); s.add_argument("nombre")
    e = sub.add_parser("enlace"); e.add_argument("usuario_id", type=int)
    c = sub.add_parser("codigo"); c.add_argument("nota", nargs="?", default=None)
    sub.add_parser("demo")
    sub.add_parser("arranque")
    a = ap.parse_args()

    conn = conectar()
    inicializar(conn)
    if a.cmd == "super":
        uid, token = crear_super(conn, a.nombre)
        print(f"Súper admin creado (usuario {uid}). Abre este enlace en tu celular y guárdalo:\n{_enlace(token)}")
    elif a.cmd == "enlace":
        print(_enlace(nuevo_enlace(conn, a.usuario_id)))
    elif a.cmd == "codigo":
        print(f"Código para crear grupo: {crear_codigo(conn, a.nota)}")
    elif a.cmd == "arranque":
        print("Súper admin inicial creado." if arranque(conn) else "Arranque: nada que crear.")
    elif a.cmd == "demo":
        gid, qid, codigo, n = demo(conn)
        print(f"Grupo {gid} 'Los Compas' con quiniela {qid} ({n} partidos).\nInvitación: {BASE}/#/unirse/{codigo}")


if __name__ == "__main__":
    main()
