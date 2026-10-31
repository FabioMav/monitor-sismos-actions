"""
test_analizar.py
Al menos 4 pruebas, con datos chicos propios, sin tocar la red ni depender de
cuantos sismos haya hoy en el feed real del USGS.

Correr con: python -m unittest discover -v
"""
import csv
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

import analizar


FILAS_EJEMPLO = [
    {"time": "2026-10-30T10:00:00.000Z", "mag": "4.5", "place": "10km N of Testville", "id": "ev1", "type": "earthquake"},
    {"time": "2026-10-30T12:30:00.000Z", "mag": "2.8", "place": "5km S of Testville", "id": "ev2", "type": "earthquake"},
    {"time": "2026-10-29T23:15:00.000Z", "mag": "6.1", "place": "20km W of Sampleton", "id": "ev3", "type": "earthquake"},
    # no es un sismo: debe filtrarse por type
    {"time": "2026-10-29T08:00:00.000Z", "mag": "3.0", "place": "Quarry X", "id": "ev4", "type": "quarry blast"},
]


class TestValidarMagnitud(unittest.TestCase):
    def test_calculo_conocido_max_y_conteo(self):
        """Dado un conjunto chico y conocido, el conteo y la magnitud maxima deben ser exactos."""
        sismos = analizar.procesar_sismos(FILAS_EJEMPLO)
        # 3 de las 4 filas son type=earthquake (ev1, ev2, ev3); ev4 (quarry blast) se excluye
        self.assertEqual(len(sismos), 3)
        magnitud_maxima = max(s["mag"] for s in sismos)
        self.assertEqual(magnitud_maxima, 6.1)

    def test_rechazo_de_magnitud_invalida(self):
        """Un valor de magnitud no numerico debe ser rechazado (ValueError), no convertido a 0."""
        with self.assertRaises(ValueError):
            analizar.validar_magnitud("no-es-un-numero")
        with self.assertRaises(ValueError):
            analizar.validar_magnitud("")
        with self.assertRaises(ValueError):
            analizar.validar_magnitud(None)
        # un valor valido sigue funcionando
        self.assertEqual(analizar.validar_magnitud("5.2"), 5.2)


class TestColumnasObligatorias(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_deteccion_de_columna_ausente(self):
        """Si falta una columna obligatoria (p. ej. 'mag'), debe detenerse con un error claro."""
        ruta = os.path.join(self.tmpdir, "datos_incompletos.csv")
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=["time", "place", "id", "type"])  # falta 'mag'
            escritor.writeheader()
            escritor.writerow({"time": "2026-10-30T10:00:00.000Z", "place": "X", "id": "ev1", "type": "earthquake"})

        with self.assertRaises(analizar.DatoIndispensableInvalido):
            analizar.leer_filas(ruta)

    def test_sin_sismos_validos_se_detiene(self):
        """Si todas las filas son invalidas o no son sismos, tambien debe detenerse (no inventa datos)."""
        filas_todas_invalidas = [
            {"time": "fecha-rara", "mag": "no-numero", "place": "X", "id": "ev1", "type": "earthquake"},
        ]
        with self.assertRaises(analizar.DatoIndispensableInvalido):
            analizar.procesar_sismos(filas_todas_invalidas)


class TestGeneracionDeInforme(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cwd_original = os.getcwd()
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.cwd_original)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_generacion_del_informe_con_datos_de_ejemplo(self):
        """Con un CSV chico de ejemplo, main() debe producir public/index.html con el contenido esperado."""
        with open("datos.csv", "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=["time", "mag", "place", "id", "type"])
            escritor.writeheader()
            for fila in FILAS_EJEMPLO:
                escritor.writerow(fila)

        analizar.main()

        self.assertTrue(os.path.exists("public/index.html"))
        with open("public/index.html", encoding="utf-8") as f:
            contenido = f.read()

        self.assertIn("Monitor de sismos recientes", contenido)
        self.assertIn("Fabio Mavric", contenido)
        self.assertIn("6.1", contenido)  # magnitud maxima de los datos de ejemplo
        self.assertIn("Sampleton", contenido)  # el sismo de mayor magnitud debe aparecer en la tabla
        self.assertIn("UTC", contenido)
        self.assertNotIn("Quarry X", contenido)  # no es type=earthquake, no debe aparecer

    def test_html_escapado_en_lugares(self):
        """Un 'place' con caracteres especiales no debe romper el HTML generado."""
        filas = [
            {"time": "2026-10-30T10:00:00.000Z", "mag": "3.3",
             "place": "5km N of <Test> & Co.", "id": "ev-esp", "type": "earthquake"},
        ]
        sismos = analizar.procesar_sismos(filas)
        contenido = analizar.generar_html(sismos, datetime.now(timezone.utc))
        self.assertNotIn("<Test>", contenido)  # debe estar escapado, no crudo
        self.assertIn("&lt;Test&gt;", contenido)


if __name__ == "__main__":
    unittest.main()
