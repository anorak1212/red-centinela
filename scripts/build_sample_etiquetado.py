"""Construye la muestra etiquetada que usa el script de humo.

De dónde sale: KDDTest+.txt, el conjunto que NUNCA se usa para entrenar. Se
toman 30 conexiones normales y 30 ataques repartidos entre las cuatro familias,
con la columna `label` y `family` incluidas. Así el script de humo puede afirmar
"30 de 30 ataques detectados" contra una verdad conocida y no contra una
suposición.

Uso:
    python -m scripts.build_sample_etiquetado
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from motor.data import FEATURE_NAMES, LABEL, load_raw

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "datasets" / "sample_etiquetado.csv"
POR_FAMILIA = 30
POR_NORMAL = 30
SEMILLA = 7


def main() -> None:
    df = load_raw("KDDTest+.txt")
    partes = [df[df["family"] == "normal"].sample(n=POR_NORMAL, random_state=SEMILLA)]
    for familia in ("dos", "probe", "r2l", "u2r"):
        sub = df[df["family"] == familia]
        if sub.empty:
            print(f"aviso: KDDTest+ no tiene filas de la familia {familia}")
            continue
        partes.append(sub.sample(n=min(POR_FAMILIA, len(sub)), random_state=SEMILLA))

    muestra = pd.concat(partes).sample(frac=1.0, random_state=SEMILLA).reset_index(drop=True)

    for col in ("protocol_type", "service", "flag"):
        muestra[col] = muestra[col].astype(str).str.lower()

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    muestra[FEATURE_NAMES + [LABEL, "family"]].to_csv(SALIDA, index=False)

    ataques = int((muestra["family"] != "normal").sum())
    print(f"escrito {SALIDA.name}: {len(muestra)} filas, {ataques} ataques, "
          f"{len(muestra) - ataques} normales")
    print("reparto por familia:", muestra["family"].value_counts().to_dict())


if __name__ == "__main__":
    main()
