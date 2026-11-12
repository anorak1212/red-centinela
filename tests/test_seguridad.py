"""Pruebas de los controles de seguridad de la API."""

from __future__ import annotations

from types import SimpleNamespace

from api.security import LimiteTasa, ip_cliente


def test_limite_permite_hasta_el_maximo():
    limite = LimiteTasa(maximo=3, ventana=60)
    assert [limite.permitir("1.1.1.1")[0] for _ in range(3)] == [True, True, True]


def test_limite_bloquea_al_exceder():
    limite = LimiteTasa(maximo=2, ventana=60)
    limite.permitir("1.1.1.1")
    limite.permitir("1.1.1.1")
    permitido, espera = limite.permitir("1.1.1.1")
    assert permitido is False
    assert espera >= 1


def test_limite_es_por_ip():
    limite = LimiteTasa(maximo=1, ventana=60)
    assert limite.permitir("1.1.1.1")[0] is True
    assert limite.permitir("2.2.2.2")[0] is True
    assert limite.permitir("1.1.1.1")[0] is False


def test_limite_expira_la_ventana():
    limite = LimiteTasa(maximo=1, ventana=0.05)
    assert limite.permitir("ip")[0] is True
    assert limite.permitir("ip")[0] is False
    import time

    time.sleep(0.08)
    assert limite.permitir("ip")[0] is True


def test_limite_limpiar():
    limite = LimiteTasa(maximo=1, ventana=60)
    limite.permitir("ip")
    limite.limpiar()
    assert limite.permitir("ip")[0] is True


def test_ip_cliente_usa_x_forwarded_for():
    req = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1"},
        client=SimpleNamespace(host="10.0.0.1"),
    )
    assert ip_cliente(req) == "203.0.113.7"


def test_ip_cliente_sin_cabecera():
    req = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
    assert ip_cliente(req) == "127.0.0.1"


def test_ip_cliente_sin_cliente():
    req = SimpleNamespace(headers={}, client=None)
    assert ip_cliente(req) == "desconocida"
