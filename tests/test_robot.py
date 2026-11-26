"""Pruebas sin internet.  Ejecutar desde la carpeta QUINIELA:  python -m unittest -v"""
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from robot.db import conectar, guardar_partido, inicializar, recalcular_quiniela
from robot.explorador import explorar
from robot.proveedores import apifootball, espn
from robot.puntuacion import calcular_tabla, puede_editar

FIX = json.loads((Path(__file__).parent / "espn_muestra.json").read_text(encoding="utf-8"))


class TestESPN(unittest.TestCase):
    def setUp(self):
        self.p = {p["id_espn"]: p for p in espn.partidos_de(FIX, "mex.1")}

    def test_final_normal(self):
        p = self.p["1"]
        self.assertEqual((p["estado"], p["goles_local_90"], p["goles_visitante_90"]), ("final", 1, 0))
        self.assertEqual(p["local"], "Guadalajara")

    def test_en_juego(self):
        p = self.p["2"]
        self.assertEqual(p["estado"], "en_juego")
        self.assertEqual(p["minuto"], "67'")
        self.assertEqual((p["goles_local_90"], p["goles_visitante_90"]), (2, 1))

    def test_prorroga_cuenta_90(self):
        p = self.p["3"]  # 2-2 a los 90, 3-2 en prórroga
        self.assertEqual((p["goles_local"], p["goles_visitante"]), (3, 2))
        self.assertEqual((p["goles_local_90"], p["goles_visitante_90"]), (2, 2))
        self.assertFalse(p["revisar"])

    def test_prorroga_sin_desglose_pide_revision(self):
        self.assertTrue(self.p["5"]["revisar"])

    def test_pospuesto(self):
        self.assertEqual(self.p["4"]["estado"], "pospuesto")
        self.assertIsNone(self.p["4"]["goles_local"])

    def test_programado(self):
        p = self.p["6"]
        self.assertEqual(p["estado"], "programado")
        self.assertEqual(p["inicio_utc"], "2026-11-29T01:00:00Z")

    def test_calendario(self):
        info = espn.info_liga(FIX)
        self.assertEqual(info["dias_con_partidos"][0], date(2026, 11, 22))
        self.assertEqual(info["fase"], "Apertura - Quarterfinals")


class TestApiFootball(unittest.TestCase):
    def test_prorroga_y_temporada(self):
        fx = {"fixture": {"id": 9, "date": "2026-11-22T23:00:00+00:00", "status": {"short": "AET", "elapsed": 120}},
              "teams": {"home": {"name": "Guadalajara"}, "away": {"name": "Cruz Azul"}},
              "goals": {"home": 2, "away": 1}, "score": {"fulltime": {"home": 1, "away": 1}}}
        p = apifootball.normalizar(fx, "mex.1")
        self.assertEqual((p["estado"], p["goles_local_90"], p["goles_visitante_90"]), ("final", 1, 1))
        self.assertEqual(apifootball.temporada_para(date(2027, 2, 1), False), 2026)
        self.assertEqual(apifootball.temporada_para(date(2027, 2, 1), True), 2027)


class TestPuntuacion(unittest.TestCase):
    def test_desempate_y_anulados(self):
        partidos = {
            1: {"estado": "final", "goles_local_90": 1, "goles_visitante_90": 0},
            2: {"estado": "final", "goles_local_90": 3, "goles_visitante_90": 1},  # estelar
            3: {"estado": "cancelado", "goles_local_90": None, "goles_visitante_90": None},
        }
        pron = {10: {1: "L", 2: "L", 3: "L"}, 20: {1: "L", 2: "L", 3: "V"},
                30: {1: "L", 2: "L"}, 40: {1: "E", 2: "E"}}
        des = {10: (2, 1), 20: (3, 1), 30: (2, 1)}
        filas, provisional = calcular_tabla(partidos, pron, des, [10, 20, 30, 40], estelar_id=2)
        orden = [(f.usuario_id, f.posicion, f.puntos) for f in filas]
        self.assertEqual(orden, [(20, 1, 2), (10, 2, 2), (30, 2, 2), (40, 4, 0)])
        self.assertFalse(provisional)

    def test_en_vivo_es_provisional(self):
        partidos = {1: {"estado": "en_juego", "goles_local_90": 0, "goles_visitante_90": 1}}
        filas, provisional = calcular_tabla(partidos, {1: {1: "V"}}, {}, [1], None)
        self.assertEqual(filas[0].puntos, 1)
        self.assertTrue(provisional)

    def test_bloqueo_al_pitazo(self):
        ahora = datetime(2026, 11, 28, 20, 0, tzinfo=timezone.utc)
        p = {"estado": "programado", "inicio_utc": "2026-11-28T20:00:00Z"}
        self.assertFalse(puede_editar(p, ahora))
        self.assertTrue(puede_editar(p, ahora - timedelta(seconds=1)))


class TestBaseDeDatos(unittest.TestCase):
    def test_explorar_y_respaldo_no_duplica(self):
        conn = conectar(":memory:")
        inicializar(conn)
        explorar(conn, dias=10, codigos=["mex.1"], descargador=lambda codigo, dia=None, **k: FIX,
                 resumidor=None)
        n = conn.execute("SELECT COUNT(*) FROM partidos").fetchone()[0]
        self.assertGreaterEqual(n, 1)
        # El respaldo trae el mismo partido con otro id y nombre ligeramente distinto: debe empatarlo.
        fila = conn.execute("SELECT * FROM partidos WHERE id_espn='1'").fetchone()
        fx = {"fixture": {"id": 777, "date": fila["inicio_utc"], "status": {"short": "FT"}},
              "teams": {"home": {"name": "CD Guadalajara"}, "away": {"name": "Cruz Azul"}},
              "goals": {"home": 1, "away": 0}, "score": {"fulltime": {"home": 1, "away": 0}}}
        guardar_partido(conn, apifootball.normalizar(fx, "mex.1"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM partidos").fetchone()[0], n)
        fila = conn.execute("SELECT * FROM partidos WHERE id_espn='1'").fetchone()
        self.assertEqual((fila["id_apifootball"], fila["local"]), (777, "Guadalajara"))

    def test_manual_no_se_pisa(self):
        conn = conectar(":memory:")
        inicializar(conn)
        p = espn.partidos_de(FIX, "mex.1")[0]
        pid, _, _ = guardar_partido(conn, p)
        conn.execute("UPDATE partidos SET manual=1, goles_local_90=5 WHERE id=?", (pid,))
        guardar_partido(conn, p)
        self.assertEqual(conn.execute("SELECT goles_local_90 FROM partidos WHERE id=?", (pid,)).fetchone()[0], 5)

    def test_recalcular_cierra_quiniela(self):
        conn = conectar(":memory:")
        inicializar(conn)
        p = espn.partidos_de(FIX, "mex.1")[0]
        pid, _, _ = guardar_partido(conn, p)
        conn.execute("INSERT INTO grupos (nombre, codigo_invitacion) VALUES ('O','X')")
        conn.execute("INSERT INTO quinielas (grupo_id, nombre) VALUES (1,'Q')")
        conn.execute("INSERT INTO quiniela_partidos VALUES (1,?,1,0)", (pid,))
        conn.execute("INSERT INTO usuarios (nombre) VALUES ('A')")
        conn.execute("INSERT INTO participaciones (quiniela_id, usuario_id) VALUES (1,1)")
        conn.execute("INSERT INTO pronosticos (quiniela_id, usuario_id, partido_id, pick) VALUES (1,1,?,'L')", (pid,))
        filas = recalcular_quiniela(conn, 1)
        self.assertEqual(filas[0].puntos, 1)
        self.assertEqual(conn.execute("SELECT estado FROM quinielas").fetchone()[0], "cerrada")


REAL = json.loads((Path(__file__).parent / "espn_real_20261126.json").read_text(encoding="utf-8"))


def descargador_real(codigo, dia=None, **_):
    if dia is None:
        return REAL["base"][codigo]
    if codigo == "mex.1":
        return REAL["dias_mex1"].get(f"{dia:%Y%m%d}", {"events": []})
    return {"events": []}


def resumidor_real(codigo, id_evento):
    return REAL[f"resumen_{codigo}_{id_evento}"]


class TestDatosRealesESPN(unittest.TestCase):
    """Datos reales de ESPN del 26/11/2026 (liguilla Liga MX, Europa League en vivo, finales con prórroga)."""

    def setUp(self):
        self.conn = conectar(":memory:")
        inicializar(self.conn)
        self.hoy = datetime(2026, 11, 26, 17, 50, tzinfo=timezone.utc)  # 11:50 CDMX

    def test_liguilla_liga_mx(self):
        r = explorar(self.conn, dias=10, codigos=["mex.1"], descargador=descargador_real,
                     resumidor=resumidor_real, hoy=self.hoy)[0]
        self.assertTrue(r["activa"])
        self.assertEqual(r["fase"], "Apertura - Quarterfinals")
        filas = self.conn.execute("SELECT * FROM partidos ORDER BY inicio_utc").fetchall()
        # ayer (25/11) a +10 días: 2 finales del miércoles + 6 programados
        self.assertEqual(len(filas), 8)
        mty = [f for f in filas if f["local"] == "Monterrey"][0]
        self.assertEqual((mty["estado"], mty["goles_local_90"], mty["goles_visitante_90"]), ("final", 0, 0))
        prog = [f for f in filas if f["estado"] == "programado"]
        self.assertEqual(len(prog), 6)
        self.assertEqual(r["proximos"], 6)

    def test_en_vivo_europa(self):
        explorar(self.conn, dias=3, codigos=["uefa.europa"], descargador=descargador_real,
                 resumidor=resumidor_real, hoy=self.hoy)
        p = self.conn.execute("SELECT * FROM partidos WHERE id_espn='401915517'").fetchone()
        self.assertEqual((p["estado"], p["minuto"], p["goles_local"], p["goles_visitante"]),
                         ("en_juego", "19'", 0, 1))

    def test_prorroga_real_mundial(self):
        # Final Mundial 2026: España 1-0 Argentina con gol en prórroga -> a 90' fue 0-0 (empate)
        p = espn.partidos_de(REAL["base"]["fifa.world"], "fifa.world", resumidor_real)[0]
        self.assertEqual((p["goles_local"], p["goles_visitante"]), (1, 0))
        self.assertEqual((p["goles_local_90"], p["goles_visitante_90"]), (0, 0))
        self.assertFalse(p["revisar"])

    def test_penales_sin_resumen_queda_por_revisar(self):
        p = espn.partidos_de(REAL["base"]["concacaf.champions"], "concacaf.champions", None)[0]
        self.assertTrue(p["revisar"])


if __name__ == "__main__":
    unittest.main()
