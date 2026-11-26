"""Prueba rápida del robot desde consola.

  python probar.py                     -> partidos de Liga MX (ayer a +10 días) con datos reales de ESPN
  python probar.py --liga eng.1 esp.1  -> otras ligas
  python probar.py --todas             -> explora todo el catálogo y dice cuáles están activas
  python probar.py --demo              -> simula una quiniela completa (sin internet)
"""
import argparse
import logging
import sys

from robot.db import conectar, inicializar, recalcular_quiniela
from robot.explorador import explorar
from robot.tiempo import a_mx, ahora_utc, a_iso
from datetime import timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ICONO = {"programado": "·", "en_juego": "●", "final": "✓", "pospuesto": "×", "suspendido": "×", "cancelado": "×"}


def mostrar_partidos(conn, codigos):
    for codigo in codigos:
        c = conn.execute("SELECT * FROM competiciones WHERE codigo=?", (codigo,)).fetchone()
        if not c:
            print(f"\n{codigo}: no está en el catálogo")
            continue
        print(f"\n=== {c['nombre']} · {c['temporada'] or ''} · {c['fase'] or ''} ===")
        filas = conn.execute("SELECT * FROM partidos WHERE competicion=? ORDER BY inicio_utc", (codigo,)).fetchall()
        if not filas:
            print("  (sin partidos en el rango)")
        for p in filas:
            marcador = "  -  " if p["goles_local"] is None else f"{p['goles_local']:>2}-{p['goles_visitante']:<2}"
            extra = f" {p['minuto']}" if p["minuto"] else ""
            nota = "  [revisar 90']" if p["revisar"] else ""
            print(f"  {ICONO[p['estado']]} {a_mx(p['inicio_utc']):<16} {p['local']:>24} {marcador} "
                  f"{p['visitante']:<24} {p['estado']}{extra}{nota}")


def demo():
    """Quiniela de 4 partidos, 4 jugadores, con empate resuelto por el partido estelar."""
    conn = conectar(":memory:")
    inicializar(conn)
    t0 = ahora_utc() - timedelta(hours=3)
    partidos = [
        ("Guadalajara", "Cruz Azul", 1, 0, "final"),
        ("Querétaro", "Necaxa", 2, 2, "final"),
        ("América", "Toluca", 3, 1, "final"),       # estelar
        ("Monterrey", "Tigres", None, None, "pospuesto"),
    ]
    ids = []
    for i, (l, v, gl, gv, est) in enumerate(partidos):
        cur = conn.execute(
            """INSERT INTO partidos (competicion, id_espn, fuente, inicio_utc, local, visitante, estado,
                 goles_local, goles_visitante, goles_local_90, goles_visitante_90)
               VALUES ('mex.1', ?, 'demo', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"demo{i}", a_iso(t0 + timedelta(minutes=30 * i)), l, v, est, gl, gv, gl, gv))
        ids.append(cur.lastrowid)
    conn.execute("INSERT INTO grupos (nombre, codigo_invitacion) VALUES ('Oficina', 'DEMO')")
    conn.execute("INSERT INTO quinielas (grupo_id, nombre) VALUES (1, 'Demo · Cuartos de final')")
    for orden, pid in enumerate(ids):
        conn.execute("INSERT INTO quiniela_partidos VALUES (1, ?, ?, ?)", (pid, int(orden == 2), orden))

    jugadores = {
        "Ana":    (["L", "E", "L", "V"], (3, 1)),   # 3 aciertos + marcador exacto
        "Beto":   (["L", "E", "L", "L"], (2, 1)),   # 3 aciertos, distancia 1
        "Carmen": (["L", "L", "L", "E"], (2, 0)),   # 2 aciertos
        "Diego":  (["V", "E", "L", "L"], None),     # 2 aciertos, sin desempate
    }
    for nombre, (picks, des) in jugadores.items():
        uid = conn.execute("INSERT INTO usuarios (nombre) VALUES (?)", (nombre,)).lastrowid
        conn.execute("INSERT INTO participaciones (quiniela_id, usuario_id, pagado) VALUES (1, ?, ?)",
                     (uid, int(nombre != "Diego")))
        for pid, pick in zip(ids, picks):
            conn.execute("INSERT INTO pronosticos (quiniela_id, usuario_id, partido_id, pick) VALUES (1,?,?,?)",
                         (uid, pid, pick))
        if des:
            conn.execute("INSERT INTO desempates (quiniela_id, usuario_id, goles_local, goles_visitante) "
                         "VALUES (1,?,?,?)", (uid, *des))
    recalcular_quiniela(conn, 1)

    print("Partidos:")
    for (l, v, gl, gv, est) in partidos:
        res = f"{gl}-{gv}" if gl is not None else "--"
        print(f"  {l:>12} {res:^5} {v:<12} {est}")
    print("  (América vs Toluca es el estelar ⭐; Monterrey-Tigres pospuesto = anulado)\n")
    print("Tabla:")
    for r in conn.execute(
            """SELECT po.*, u.nombre, pa.pagado FROM posiciones po
               JOIN usuarios u ON u.id=po.usuario_id
               JOIN participaciones pa ON pa.usuario_id=po.usuario_id AND pa.quiniela_id=po.quiniela_id
               ORDER BY po.posicion, u.nombre"""):
        des = "exacto ⭐" if r["exacto_estelar"] else (f"a {r['distancia']} goles" if r["distancia"] is not None else "sin marcador")
        print(f"  {r['posicion']}°  {r['nombre']:<7} {r['puntos']} pts  ({des})  {'✅' if r['pagado'] else '⏳'}")
    estado = conn.execute("SELECT estado FROM quinielas WHERE id=1").fetchone()[0]
    print(f"\nEstado de la quiniela: {estado}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--liga", nargs="+", default=["mex.1"])
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--dias", type=int, default=10)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.demo:
        demo()
        return

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    conn = conectar()
    inicializar(conn)
    resumen = explorar(conn, dias=args.dias, codigos=None if args.todas else args.liga)
    print("\nCompeticiones:")
    for r in resumen:
        if "error" in r:
            print(f"  ✗ {r['nombre']:<24} error: {r['error']}")
        else:
            print(f"  {'✓ ACTIVA' if r['activa'] else '  inactiva'}  {r['nombre']:<24} "
                  f"{r['proximos']} próximos · {r['fase'] or ''}")
    mostrar_partidos(conn, [r["codigo"] for r in resumen if r.get("partidos")])


if __name__ == "__main__":
    main()
