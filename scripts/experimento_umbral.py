"""Selección del umbral con validación agrupada por subtipo de ataque.

El problema que resuelve: el holdout aleatorio del entrenamiento se parece
demasiado al entrenamiento (macro-F1 0.999), así que cualquier umbral entre 0.2
y 0.7 da lo mismo ahí. En KDDTest+ aparecen subtipos de ataque que no existen en
KDDTrain+, y el umbral elegido en un holdout fácil resulta demasiado alto.

Solución metodológica: validación cruzada agrupada por la etiqueta original de
NSL-KDD (23 subtipos). Al agrupar, ningún subtipo aparece a la vez en ajuste y
validación. La validación imita la condición de KDDTest+ y el umbral que sale de
ahí sí es informativo.

Uso:
    python -m scripts.experimento_umbral

No toca KDDTest+. Imprime el umbral recomendado y el macro-F1 fuera de fold.
"""

from __future__ import annotations

import time

import numpy as np
from motor.data import LABEL, TARGET, load_raw
from motor.preprocess import Preprocessor
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold

RANDOM_STATE = 42
N_ARBOLES = 200
N_FOLDS = 3
UMBRALES = np.arange(0.05, 0.96, 0.01)


def main() -> None:
    t0 = time.time()
    train = load_raw("KDDTrain+.txt")
    pp = Preprocessor().fit(train)
    X = pp.transform(train)
    y = train[TARGET].to_numpy()
    etiqueta = train[LABEL].astype(str).to_numpy()
    # Las filas normales son su propio grupo: agruparlas todas juntas dejaría
    # folds sin un solo registro normal. Los ataques se agrupan por subtipo, que
    # es lo que simula la aparición de familias nuevas en KDDTest+.
    grupos = np.array(
        [f"normal-{i}" if e == "normal" else e for i, e in enumerate(etiqueta)]
    )

    skf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    probas = np.zeros(len(y))
    cubierto = np.zeros(len(y), dtype=bool)

    for i, (idx_a, idx_v) in enumerate(skf.split(X, y, groups=grupos), start=1):
        rf = RandomForestClassifier(
            n_estimators=N_ARBOLES, n_jobs=-1, random_state=RANDOM_STATE,
            class_weight="balanced", max_features="sqrt",
        ).fit(X[idx_a], y[idx_a])
        probas[idx_v] = rf.predict_proba(X[idx_v])[:, 1]
        cubierto[idx_v] = True
        # Qué subtipos quedaron fuera del ajuste en este fold.
        fuera = sorted(set(grupos[idx_v]) - set(grupos[idx_a]))
        print(f"fold {i}: {len(idx_a):,} ajuste / {len(idx_v):,} validación, "
              f"{len(fuera)} subtipos no vistos ({', '.join(fuera[:4])}"
              f"{'...' if len(fuera) > 4 else ''})")

    mejor_f1, mejor_t = 0.0, 0.5
    for t in UMBRALES:
        f1 = f1_score(y[cubierto], (probas[cubierto] >= t).astype(int), average="macro")
        if f1 > mejor_f1:
            mejor_f1, mejor_t = float(f1), float(t)

    print()
    print(f"umbral recomendado = {mejor_t:.2f}")
    print(f"macro-F1 fuera de fold en ese umbral = {mejor_f1:.4f}")
    print(f"tiempo = {time.time() - t0:.0f}s")
    print()
    print("Curva alrededor del umbral elegido:")
    for t in np.arange(max(0.05, mejor_t - 0.10), min(0.95, mejor_t + 0.11), 0.05):
        f1 = f1_score(y[cubierto], (probas[cubierto] >= t).astype(int), average="macro")
        marca = "  <-- recomendado" if abs(t - mejor_t) < 0.005 else ""
        print(f"  umbral {t:.2f} -> macro-F1 {f1:.4f}{marca}")


if __name__ == "__main__":
    main()
