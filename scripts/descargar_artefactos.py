"""Trae los artefactos del modelo al servicio desplegado.

Los .joblib no se versionan (80 MB en total). Una plataforma que despliega
desde Git arrancaría sin modelo y `/health` respondería "degradado". Este script
se ejecuta en el build y baja un paquete publicado como release:

    REDCENTINELA_MODELOS_URL=https://github.com/<usuario>/<repo>/releases/download/modelos-v1/modelos.tar.gz
    REDCENTINELA_MODELOS_SHA256=<sha256 del paquete>
    python scripts/descargar_artefactos.py

Si los artefactos ya están en disco y el manifiesto coincide, no descarga nada.
Si no hay URL y tampoco artefactos, falla con un mensaje que dice qué falta; no
deja el servicio a medias.

Uso local (verificación):

    python scripts/descargar_artefactos.py --estado
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motor.data import MODEL_DIR
from motor.ensemble import verificar_manifiesto

NOMBRE_PAQUETE = "modelos_red_centinela.tar.gz"
MAX_BYTES = 300 * 1024 * 1024


def _mostrar(url: str) -> str:
    """URL sin query ni credenciales: nunca imprimir tokens de descarga."""
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}{partes.path}"


def estado_actual(dir_modelos: Path) -> tuple[bool, str]:
    """(ok, detalle) de los artefactos que ya están en disco."""
    if not (dir_modelos / "manifiesto.json").exists():
        return False, "no hay manifiesto.json"
    resultado = verificar_manifiesto(dir_modelos)
    if resultado.get("ok"):
        return True, "artefactos íntegros según el manifiesto"
    faltan = [n for n, d in (resultado.get("detalle") or {}).items() if d != "ok"]
    return False, f"manifiesto no coincide: {', '.join(faltan) or 'sin detalle'}"


def descargar(url: str, destino: Path, timeout: int = 180) -> Path:
    """Descarga el paquete a `destino` y devuelve la ruta."""
    import requests

    destino.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as r:
        if r.status_code != 200:
            raise RuntimeError(f"la descarga respondió {r.status_code} en {_mostrar(url)}")
        tamano = 0
        with destino.open("wb") as fh:
            for bloque in r.iter_content(chunk_size=1024 * 256):
                tamano += len(bloque)
                if tamano > MAX_BYTES:
                    raise RuntimeError("el paquete supera el máximo esperado de 300 MB")
                fh.write(bloque)
    return destino


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def comprobar_sha256(ruta: Path, esperado: str) -> None:
    if not esperado:
        return
    real = sha256_de(ruta)
    if real.lower() != esperado.strip().lower():
        raise RuntimeError(
            f"SHA-256 distinto: esperado {esperado.strip().lower()[:16]}..., "
            f"obtenido {real[:16]}..."
        )


def descomprimir(paquete: Path, dir_modelos: Path) -> list[str]:
    """Extrae solo archivos planos; ignora subcarpetas del paquete."""
    dir_modelos.mkdir(parents=True, exist_ok=True)
    extraidos: list[str] = []
    with tarfile.open(paquete, "r:gz") as tar:
        for miembro in tar.getmembers():
            if not miembro.isfile():
                continue
            nombre = Path(miembro.name).name
            if not nombre or nombre.startswith("."):
                continue
            origen = tar.extractfile(miembro)
            if origen is None:
                continue
            with origen, (dir_modelos / nombre).open("wb") as destino:
                destino.write(origen.read())
            extraidos.append(nombre)
    return extraidos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estado", action="store_true", help="solo informa, no descarga")
    parser.add_argument("--dir", default=None, help="carpeta destino (por omisión motor/models)")
    args = parser.parse_args(argv)
    dir_modelos = Path(args.dir) if args.dir else MODEL_DIR

    ok, detalle = estado_actual(dir_modelos)
    if ok and not args.estado:
        print(f"[artefactos] ya presentes: {detalle}")
        return 0
    print(f"[artefactos] estado: {detalle}")
    if args.estado:
        return 0 if ok else 1

    url = os.environ.get("REDCENTINELA_MODELOS_URL", "").strip()
    if not url:
        print(
            "[artefactos] falta REDCENTINELA_MODELOS_URL. Publica el paquete con\n"
            "  python scripts/empaquetar_artefactos.py\n"
            "y súbelo como release del repositorio. También puedes entrenar en el\n"
            "servidor con `python -m motor.train` (tarda y consume memoria).",
            file=sys.stderr,
        )
        return 1

    esperado = os.environ.get("REDCENTINELA_MODELOS_SHA256", "")
    print(f"[artefactos] descargando {_mostrar(url)}")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            paquete = descargar(url, Path(tmp) / NOMBRE_PAQUETE)
            comprobar_sha256(paquete, esperado)
            extraidos = descomprimir(paquete, dir_modelos)
    except Exception as exc:  # noqa: BLE001 - el build debe fallar con motivo claro
        print(f"[artefactos] error: {exc}", file=sys.stderr)
        return 1

    ok, detalle = estado_actual(dir_modelos)
    print(f"[artefactos] extraídos {len(extraidos)}: {', '.join(sorted(extraidos))}")
    if not ok:
        print(f"[artefactos] verificación fallida: {detalle}", file=sys.stderr)
        return 1
    print(f"[artefactos] listo: {detalle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
