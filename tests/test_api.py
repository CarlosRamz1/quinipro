"""Pruebas de la API (sin internet).  python -m unittest -v"""
import os
import tempfile
import unittest
from datetime import timedelta

_tmp = tempfile.mkdtemp()
os.environ.setdefault("QUINIELA_DB", os.path.join(_tmp, "import.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import admin  # noqa: E402
from app.main import crear_app  # noqa: E402
from robot.db import conectar, guardar_partido, recalcular_quiniela  # noqa: E402
from robot.tiempo import a_iso, ahora_utc  # noqa: E402


def _partido(n, horas, estado="programado", gl=None, gv=None):
    return {"competicion": "mex.1", "id_espn": f"t{n}", "fuente": "espn",
            "inicio_utc": a_iso(ahora_utc() + timedelta(hours=horas)), "local": f"Local {n}", "visitante": f"Visita {n}",
            "local_abrev": "LOC", "visitante_abrev": "VIS", "local_logo": None, "visitante_logo": None,
            "estado": estado, "minuto": None, "goles_local": gl, "goles_visitante": gv,
            "goles_local_90": gl, "goles_visitante_90": gv, "revisar": False}


class TestFlujoCompleto(unittest.TestCase):
    def setUp(self):
        self.ruta = os.path.join(tempfile.mkdtemp(), "q.db")
        self.app = crear_app(self.ruta)
        self.c = TestClient(self.app)
        self.conn = conectar(self.ruta)
        self.sup_id, self.sup_tok = admin.crear_super(self.conn, "Carlos")
        self.pids = [guardar_partido(self.conn, _partido(i, 24 + i))[0] for i in range(4)]
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def h(self, tok):
        return {"Authorization": f"Bearer {tok}"}

    def _grupo_con_quiniela(self):
        codigo = admin.crear_codigo(self.conn, "prueba")
        r = self.c.post("/api/grupos", json={"codigo": codigo, "nombre": "Los Compas", "tu_nombre": "Ana López"})
        self.assertEqual(r.status_code, 200, r.text)
        dueno = r.json()["token"]
        gid = r.json()["id"]
        r = self.c.post(f"/api/grupos/{gid}/quinielas", headers=self.h(dueno),
                        json={"nombre": "Fin de semana", "partidos": self.pids, "estelar": self.pids[0]})
        self.assertEqual(r.status_code, 200, r.text)
        return gid, r.json()["id"], dueno

    def test_crear_grupo_requiere_codigo(self):
        r = self.c.post("/api/grupos", json={"nombre": "Grupo X", "tu_nombre": "Pepe"})
        self.assertEqual(r.status_code, 403)
        r = self.c.post("/api/grupos", json={"nombre": "Grupo del jefe"}, headers=self.h(self.sup_tok))
        self.assertEqual(r.status_code, 200)  # el súper admin no necesita código

    def test_codigo_de_un_solo_uso(self):
        codigo = admin.crear_codigo(self.conn, None)
        self.assertEqual(self.c.post("/api/grupos", json={"codigo": codigo, "nombre": "A", "tu_nombre": "Uno"}).status_code, 422)
        self.assertEqual(self.c.post("/api/grupos", json={"codigo": codigo, "nombre": "Grupo A", "tu_nombre": "Uno"}).status_code, 200)
        self.assertEqual(self.c.post("/api/grupos", json={"codigo": codigo, "nombre": "Grupo B", "tu_nombre": "Dos"}).status_code, 403)

    def test_flujo_de_juego(self):
        gid, qid, dueno = self._grupo_con_quiniela()
        inv = self.c.get(f"/api/grupos/{gid}", headers=self.h(dueno)).json()["codigo_invitacion"]
        self.assertEqual(self.c.get(f"/api/invitacion/{inv}").json()["grupo"], "Los Compas")
        beto = self.c.post("/api/unirse", json={"codigo": inv, "nombre": "Beto Pérez"}).json()["token"]

        # Un participante no ve el código de invitación ni puede administrar
        g = self.c.get(f"/api/grupos/{gid}", headers=self.h(beto)).json()
        self.assertIsNone(g["codigo_invitacion"])
        self.assertEqual(self.c.get(f"/api/quinielas/{qid}/pagos", headers=self.h(beto)).status_code, 403)

        for pid, pick in zip(self.pids, "LEVL"):
            self.assertEqual(self.c.put(f"/api/quinielas/{qid}/picks", headers=self.h(beto),
                                        json={"partido_id": pid, "pick": pick}).status_code, 200)
        self.c.put(f"/api/quinielas/{qid}/desempate", headers=self.h(beto), json={"goles_local": 2, "goles_visitante": 1})
        q = self.c.get(f"/api/quinielas/{qid}", headers=self.h(beto)).json()
        self.assertEqual(q["llenos"], 4)
        self.assertEqual(q["mi_desempate"], {"goles_local": 2, "goles_visitante": 1})

        # Antes del pitazo nadie ve picks ajenos, ni el dueño
        r = self.c.get(f"/api/quinielas/{qid}/partidos/{self.pids[0]}", headers=self.h(dueno)).json()
        self.assertFalse(r["revelado"])
        self.assertNotIn("picks", r)

        # Arranca el partido 0 y termina 2-1: se bloquea, se revela y Beto suma
        self.conn.execute("UPDATE partidos SET estado='final', inicio_utc=?, goles_local_90=2, goles_visitante_90=1 WHERE id=?",
                          (a_iso(ahora_utc() - timedelta(hours=2)), self.pids[0]))
        recalcular_quiniela(self.conn, qid)
        self.conn.commit()
        r = self.c.put(f"/api/quinielas/{qid}/picks", headers=self.h(beto), json={"partido_id": self.pids[0], "pick": "V"})
        self.assertEqual(r.status_code, 409)
        r = self.c.get(f"/api/quinielas/{qid}/partidos/{self.pids[0]}", headers=self.h(dueno)).json()
        self.assertTrue(r["revelado"])
        self.assertEqual(r["conteo"]["L"], 1)
        t = self.c.get(f"/api/quinielas/{qid}/tabla", headers=self.h(beto)).json()
        self.assertEqual(t["filas"][0]["nombre"], "Beto Pérez")
        self.assertEqual(t["filas"][0]["puntos"], 1)
        self.assertTrue(t["filas"][0]["exacto_estelar"])

        # Pagos
        self.assertEqual(self.c.put(f"/api/quinielas/{qid}/pagos", headers=self.h(dueno), json={"pagado": True}).status_code, 200)
        self.assertTrue(all(p["pagado"] for p in self.c.get(f"/api/quinielas/{qid}/pagos", headers=self.h(dueno)).json()))

    def test_roles(self):
        gid, qid, dueno = self._grupo_con_quiniela()
        inv = self.c.get(f"/api/grupos/{gid}", headers=self.h(dueno)).json()["codigo_invitacion"]
        r = self.c.post("/api/unirse", json={"codigo": inv, "nombre": "Carmen"})
        carmen = r.json()["token"]
        cid = self.c.get("/api/yo", headers=self.h(carmen)).json()["usuario"]["id"]
        dueno_id = self.c.get("/api/yo", headers=self.h(dueno)).json()["usuario"]["id"]
        # Carmen no puede hacerse admin sola
        self.assertEqual(self.c.put(f"/api/grupos/{gid}/miembros/{cid}/rol", headers=self.h(carmen),
                                    json={"rol": "coadmin"}).status_code, 403)
        self.assertEqual(self.c.put(f"/api/grupos/{gid}/miembros/{cid}/rol", headers=self.h(dueno),
                                    json={"rol": "coadmin"}).status_code, 200)
        # Co-admin puede ver pagos pero no puede sacar al dueño
        self.assertEqual(self.c.get(f"/api/quinielas/{qid}/pagos", headers=self.h(carmen)).status_code, 200)
        self.assertEqual(self.c.delete(f"/api/grupos/{gid}/miembros/{dueno_id}", headers=self.h(carmen)).status_code, 409)
        # Si el dueño se va, el grupo pasa a la co-admin
        self.c.post(f"/api/grupos/{gid}/salir", headers=self.h(dueno))
        self.assertEqual(self.c.get(f"/api/grupos/{gid}", headers=self.h(carmen)).json()["rol"], "dueno")

    def test_correccion_solo_super(self):
        gid, qid, dueno = self._grupo_con_quiniela()
        body = {"estado": "final", "goles_local_90": 1, "goles_visitante_90": 1}
        self.assertEqual(self.c.put(f"/api/super/partidos/{self.pids[1]}", headers=self.h(dueno), json=body).status_code, 403)
        r = self.c.put(f"/api/super/partidos/{self.pids[1]}", headers=self.h(self.sup_tok), json=body)
        self.assertEqual(r.json()["quinielas_recalculadas"], 1)
        self.assertEqual(self.conn.execute("SELECT manual FROM partidos WHERE id=?", (self.pids[1],)).fetchone()[0], 1)

    def test_no_elegir_partidos_ya_empezados(self):
        gid, qid, dueno = self._grupo_con_quiniela()
        viejo = guardar_partido(self.conn, _partido(9, -1, "en_juego", 0, 0))[0]
        self.conn.commit()
        r = self.c.post(f"/api/grupos/{gid}/quinielas", headers=self.h(dueno),
                        json={"nombre": "Otra", "partidos": [viejo, self.pids[2]], "estelar": self.pids[2]})
        self.assertEqual(r.status_code, 422)

    def test_sin_sesion(self):
        self.assertEqual(self.c.get("/api/yo").status_code, 401)
        self.assertEqual(self.c.get("/api/yo", headers=self.h("falso")).status_code, 401)


if __name__ == "__main__":
    unittest.main()
