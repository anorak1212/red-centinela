"""Pruebas del acceso al tablero: hash, roles, bloqueo y pantalla de login."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from tablero import auth

RAIZ = Path(__file__).resolve().parents[1]
API_MUERTA = "http://127.0.0.1:9"


def test_hash_verifica_y_rechaza():
    secreto = auth.generar_hash("clave-segura", iteraciones=1_000)
    assert secreto.startswith("pbkdf2_sha256$1000$")
    assert auth.verificar("clave-segura", secreto)
    assert not auth.verificar("otra", secreto)


def test_cargar_usuarios_ignora_entradas_invalidas():
    usuarios = auth.cargar_usuarios(
        "Ana:admin:x1, beto:lector:x2, malo:superusuario:x3, sinrol, :admin:x4"
    )
    assert set(usuarios) == {"ana", "beto"}
    assert usuarios["ana"].rol == "admin"
    assert usuarios["beto"].texto_plano


def test_autenticar_con_hash_y_nombre_sin_mayusculas():
    secreto = auth.generar_hash("clave-segura", iteraciones=1_000)
    usuarios = auth.cargar_usuarios(f"ana:admin:{secreto}")
    assert auth.autenticar(usuarios, " ANA ", "clave-segura").nombre == "ana"
    assert auth.autenticar(usuarios, "ana", "mal") is None
    assert auth.autenticar(usuarios, "nadie", "clave-segura") is None


def test_bloqueo_tras_intentos_fallidos():
    estado: dict = {}
    for _ in range(auth.INTENTOS_MAXIMOS):
        auth.registrar_fallo(estado)
    assert auth.segundos_bloqueado(estado) > 0


def test_lector_no_puede_escribir(monkeypatch):
    monkeypatch.setenv(auth.VARIABLE, "ana:admin:x, beto:lector:y")
    estado: dict = {}
    assert not auth.puede_escribir(estado)
    auth.iniciar_sesion(estado, auth.cargar_usuarios()["beto"])
    assert not auth.puede_escribir(estado)
    auth.iniciar_sesion(estado, auth.cargar_usuarios()["ana"])
    assert auth.puede_escribir(estado)


def test_sin_configurar_es_acceso_abierto(monkeypatch):
    monkeypatch.delenv(auth.VARIABLE, raising=False)
    assert not auth.configurado()
    assert auth.puede_escribir({})


@pytest.fixture
def app_con_usuarios(monkeypatch):
    monkeypatch.setenv(auth.VARIABLE, "ana:admin:clave-ana, beto:lector:clave-beto")
    at = AppTest.from_file(str(RAIZ / "tablero" / "app.py"), default_timeout=120)
    at.session_state["api_url"] = API_MUERTA
    return at


def test_app_pide_login_y_no_muestra_vistas(app_con_usuarios):
    at = app_con_usuarios
    at.run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Usuario", "Contraseña"]
    assert not any("URL de la API" in t.label for t in at.text_input)


def test_login_incorrecto_y_correcto(app_con_usuarios):
    at = app_con_usuarios
    at.run()
    at.text_input[0].input("ana")
    at.text_input[1].input("mal")
    at.button[0].click().run()
    assert any("incorrectos" in e.value for e in at.error)

    at.text_input[0].input("ana")
    at.text_input[1].input("clave-ana")
    at.button[0].click().run()
    assert not at.exception
    assert any("URL de la API" in t.label for t in at.text_input)
    assert any(b.label == "Salir" for b in at.button)

    next(b for b in at.button if b.label == "Salir").click().run()
    assert [t.label for t in at.text_input] == ["Usuario", "Contraseña"]
