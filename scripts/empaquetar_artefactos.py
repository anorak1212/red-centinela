"""Empaqueta los artefactos del modelo para publicarlos como release.

Los .joblib no viven en Git: 80 MB en el historial harían el clon lento y
GitHub rechaza archivos de más de 100 MB. El paquete se sube a un release y el
build del servicio lo baja con `scripts/descargar_artefactos.py`.

    python scripts/empaquetar_artefactos.py

Imprime el SHA-256 que hay que pegar en REDCENTINELA_MODELOS_SHA256.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tarfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motor.data import MODEL_DIR
from motor.ensemble import verificar_manifiesto

# Los cinco archivos del manifiesto. `metrics.json` es un informe derivado y no
# va: se regenera al evaluar y no lo consume el servicio para predecir.
ARCHIVOS = [
    "iforest.joblib",
    "preprocessor.joblib",
    "rf.joblib",
    "rf_multi.joblib",
    "metadata.json",
    "manifiesto.json",
]


def empaquetar(dir_modelos: Path, salida: Path) -> Path:
    ok = verificar_manifiesto(dir_modelos)
    if not ok.get("ok"):
        raise RuntimeError(f"los artefactos no coinciden con el manifiesto: {ok.get('detalle')}")
    faltan = [n for n in ARCHIVOS if not (dir_modelos / n).exists()]
    if faltan:
        raise RuntimeError(f"faltan artefactos: {', '.join(faltan)}")

    salida.parent.mkdir(parents=True, exist_ok=True)
    with (
        salida.open("wb") as crudo,
        gzip.GzipFile(filename="", mode="wb", fileobj=crudo, mtime=0) as comprimido,
        tarfile.open(fileobj=comprimido, mode="w") as tar,
    ):
        for nombre in ARCHIVOS:
            ruta = dir_modelos / nombre
            info = tar.gettarinfo(str(ruta), arcname=nombre)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with ruta.open("rb") as fh:
                tar.addfile(info, fh)
    return salida


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=None, help="carpeta de modelos (por omisión motor/models)")
    parser.add_argument(
        "--salida", default=None, help="archivo .tar.gz (por omisión dist/modelos_red_centinela.tar.gz)"
    )
    args = parser.parse_args(argv)
    dir_modelos = Path(args.dir) if args.dir else MODEL_DIR
    version = "sin-version"
    meta = dir_modelos / "metadata.json"
    if meta.exists():
        try:
            version = str(json.loads(meta.read_text(encoding="utf-8")).get("version", version))
        except ValueError:
            pass
    salida = Path(args.salida) if args.salida else RAIZ / "dist" / "modelos_red_centinela.tar.gz"

    try:
        paquete = empaquetar(dir_modelos, salida)
    except RuntimeError as exc:
        print(f"[paquete] error: {exc}", file=sys.stderr)
        return 1

    mb = paquete.stat().st_size / (1024 * 1024)
    print(f"[paquete] {paquete} ({mb:.1f} MB) · versión {version}")
    print(f"[paquete] SHA-256: {sha256_de(paquete)}")
    print(
        "[paquete] siguiente paso: súbelo como release en GitHub\n"
        "  gh release create modelos-v1 dist/modelos_red_centinela.tar.gz\n"
        "y define REDCENTINELA_MODELOS_URL y REDCENTINELA_MODELOS_SHA256 en el servicio."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
