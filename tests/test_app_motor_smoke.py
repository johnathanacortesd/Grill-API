# -*- coding: utf-8 -*-
"""Smoke de la app (Streamlit AppTest). Grill-API: un solo motor, OpenAI Luna
(gpt-6-luna); sin selector de motor ni nada de Claude Haiku en la pantalla."""
import os
import unittest

from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')
MOTOR = 'Motor de clasificación'


def _app(con_clave_openai=True):
    at = AppTest.from_file(APP, default_timeout=60)
    at.secrets['APP_PASSWORD'] = 'prueba'
    if con_clave_openai:
        at.secrets['OPENAI_API_KEY'] = 'sk-dummy'
    at.secrets['REGIONES_CSV_URL'] = 'http://localhost/regiones.csv'
    at.secrets['INTERNET_CSV_URL'] = 'http://localhost/internet.csv'
    at.session_state['password_correct'] = True
    return at.run()


def _textos(at):
    return [e.value for e in at.error] + [c.value for c in at.caption] + \
        [m.value for m in at.markdown] + [r.label for r in at.radio] + \
        [c.label for c in at.checkbox]


class TestAppSoloLuna(unittest.TestCase):
    def test_carga_sin_selector_de_motor(self):
        at = _app()
        self.assertFalse(at.exception)
        self.assertFalse([r for r in at.radio if r.label == MOTOR])
        self.assertTrue(any('OpenAI Luna (gpt-6-luna)' in c.value for c in at.caption))
        modelo = [t for t in at.text_input if t.key == 'modelo_fijo']
        self.assertEqual(len(modelo), 1)
        self.assertEqual(modelo[0].value, 'gpt-6-luna')

    def test_nada_de_haiku_en_pantalla(self):
        at = _app()
        textos = ' '.join(_textos(at))
        self.assertNotIn('ANTHROPIC_API_KEY', textos)
        self.assertNotIn('Haiku', textos)
        self.assertFalse(any('Reutilizar clasificaciones previas' in c.label for c in at.checkbox))

    def test_sin_clave_openai_muestra_error(self):
        at = _app(con_clave_openai=False)
        self.assertFalse(at.exception)
        self.assertTrue(any('OPENAI_API_KEY' in e.value for e in at.error))

    def test_pkl_disponibles(self):
        at = _app()
        self.assertTrue(any('Modelos PKL del cliente' in m.value for m in at.markdown))


if __name__ == '__main__':
    unittest.main()
