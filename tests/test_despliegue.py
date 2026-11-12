"""Pruebas del empaquetado y la descarga de artefactos para el despliegue.

Sin artefactos no hay servicio, así que esta cadena se prueba con archivos
falsos de tamaño ridículo: lo que se verifica es la lógica (manifiesto, SHA-256,
extracción plana), no el contenido de los modelos.
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest
from motor.ensemble import construir_manifiesto
from scripts import descargar_artefactos as descarga
from scripts import empaquetar_artefactos as empaque

REPO = Path(__file__).resolve().parents[1]
MODELOS_REALES = REPO / "motor" / "models"


def _modelos_falsos(destino: Path) -> Path:
    """Cinco artefactos mínimos con manifiesto válido."""
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ("rf.joblib", "rf_multi.joblib", "iforest.joblib", "preprocessor.joblib"):
        (destino / nombre).write_bytes(b"contenido-" + nombre.encode())
    (destino / "metadata.json").write_text(
        json.dumps({"version": "9.9.9", "modelos": ["rf"]}), encoding="utf-8"
    )
    manifiesto = construir_manifiesto(destino)
    (destino / "manifiesto.json").write_text(json.dumps(manifiesto), encoding="utf-8")
    return destino


def test_empaquetar_y_descomprimir_conservan_el_manifiesto(tmp_path):
    origen = _modelos_falsos(tmp_path / "origen")
    paquete = empaque.empaquetar(origen, tmp_path / "salida" / "modelos.tar.gz")

    destino = tmp_path / "destino"
    extraidos = descarga.descomprimir(paquete, destino)

    assert sorted(extraidos) == sorted(empaque.ARCHIVOS)
    ok, detalle = descarga.estado_actual(destino)
    assert ok, detalle
    assert (destino / "rf.joblib").read_bytes() == (origen / "rf.joblib").read_bytes()


def test_empaquetar_rechaza_artefacto_alterado(tmp_path):
    origen = _modelos_falsos(tmp_path / "origen")
    (origen / "rf.joblib").write_bytes(b"otra cosa")
    with pytest.raises(RuntimeError, match="no coinciden"):
        empaque.empaquetar(origen, tmp_path / "modelos.tar.gz")


def test_estado_actual_sin_manifiesto(tmp_path):
    ok, detalle = descarga.estado_actual(tmp_path)
    assert not ok
    assert "manifiesto" in detalle


def test_comprobar_sha256_acepta_el_correcto(tmp_path):
    ruta = tmp_path / "x.bin"
    ruta.write_bytes(b"abc")
    descarga.comprobar_sha256(ruta, hashlib.sha256(b"abc").hexdigest())
    descarga.comprobar_sha256(ruta, "")


def test_comprobar_sha256_rechaza_el_distinto(tmp_path):
    ruta = tmp_path / "x.bin"
    ruta.write_bytes(b"abc")
    with pytest.raises(RuntimeError, match="SHA-256 distinto"):
        descarga.comprobar_sha256(ruta, "0" * 64)


def test_mostrar_url_esconde_la_query():
    vista = descarga._mostrar(
        "https://github.com/o/r/releases/download/modelos-v1/modelos.tar.gz?token=secreto"
    )
    assert "secreto" not in vista
    assert vista.endswith("modelos.tar.gz")


def test_descomprimir_ignora_subcarpetas_y_ocultos(tmp_path):
    import gzip
    import tarfile

    paquete = tmp_path / "raro.tar.gz"
    with (
        gzip.open(paquete, "wb") as comprimido,
        tarfile.open(fileobj=comprimido, mode="w") as tar,
    ):
        archivo = tmp_path / "bueno.txt"
        archivo.write_text("bueno", encoding="utf-8")
        tar.add(str(archivo), arcname="bueno.txt")
        oculto = tmp_path / ".env"
        oculto.write_text("token", encoding="utf-8")
        tar.add(str(oculto), arcname=".env")
        carpeta = tmp_path / "carpeta"
        carpeta.mkdir()
        dentro = carpeta / "otro.txt"
        dentro.write_text("otro", encoding="utf-8")
        tar.add(str(dentro), arcname="carpeta/otro.txt")

    destino = tmp_path / "destino"
    extraidos = descarga.descomprimir(paquete, destino)
    assert extraidos == ["bueno.txt", "otro.txt"]
    nombres = {p.name for p in destino.iterdir()}
    assert nombres == {"bueno.txt", "otro.txt"}


@pytest.mark.skipif(not (MODELOS_REALES / "manifiesto.json").exists(),
                    reason="no hay artefactos reales que empaquetar")
def test_paquete_real_se_verifica(tmp_path):
    paquete = empaque.empaquetar(MODELOS_REALES, tmp_path / "modelos.tar.gz")
    assert paquete.stat().st_size > 1_000_000
    destino = tmp_path / "destino"
    descarga.descomprimir(paquete, destino)
    ok, detalle = descarga.estado_actual(destino)
    assert ok, detalle


def test_descargar_desde_http_local(tmp_path):
    origen = tmp_path / "publicado"
    origen.mkdir()
    (origen / "paquete.bin").write_bytes(b"x" * 1024)

    manejador = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(origen)
    )
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        puerto = servidor.server_address[1]
        destino = tmp_path / "bajado.bin"
        descarga.descargar(
            f"http://127.0.0.1:{puerto}/paquete.bin", destino, timeout=10
        )
        assert destino.read_bytes() == b"x" * 1024
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_descargar_falla_con_404(tmp_path):
    origen = tmp_path / "vacio"
    origen.mkdir()
    manejador = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(origen)
    )
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        puerto = servidor.server_address[1]
        with pytest.raises(RuntimeError, match="404"):
            descarga.descargar(
                f"http://127.0.0.1:{puerto}/no-existe.bin", tmp_path / "x.bin", timeout=10
            )
    finally:
        servidor.shutdown()
        servidor.server_close()
