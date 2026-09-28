"""Descarga el dataset NSL-KDD a datasets/raw/.

    python scripts/download_nslkdd.py

Fuente espejo: repositorio público jmnwong/NSL-KDD-Dataset. Los datos crudos
no se versionan en git (ver .gitignore); este script los repone.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

MIRROR = "https://raw.githubusercontent.com/jmnwong/NSL-KDD-Dataset/master/"
ARCHIVOS = ["KDDTrain+.txt", "KDDTest+.txt", "KDDTrain+_20Percent.txt"]
RAW = Path(__file__).resolve().parents[1] / "datasets" / "raw"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for nombre in ARCHIVOS:
        destino = RAW / nombre
        if destino.exists() and destino.stat().st_size > 1_000:
            print(f"ya existe {nombre} ({destino.stat().st_size:,} bytes)")
            continue
        print(f"descargando {nombre}...")
        urllib.request.urlretrieve(MIRROR + nombre, destino)
        print(f"  ok ({destino.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()