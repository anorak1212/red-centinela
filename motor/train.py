"""Entrenamiento de los cuatro modelos y serialización con joblib.

    python -m motor.train

Guarda en motor/models/: rf.joblib, svm.joblib, knn.joblib, iforest.joblib,
preprocessor.joblib y metadata.json. También deja la caché NumPy
(datasets/processed/) y calcula el umbral óptimo del ensamble sobre un
holdout estratificado (25 %) del entrenamiento.
"""

from __future__ import annotations

import json
import time

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import LinearSVC

from .data import MODEL_DIR, PROC_DIR, TARGET, load_raw
from .ensemble import proba_ensamble
from .preprocess import Preprocessor

RANDOM_STATE = 42


def _guardar_caches(x, y, nombre: str) -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    np.save(PROC_DIR / f"{nombre}.X.npy", x)
    np.save(PROC_DIR / f"{nombre}.y.npy", y)


def _calibrar_umbral(pp: Preprocessor, Xtr, ytr) -> dict:
    """Busca el umbral que maximiza macro-F1 en un holdout del train."""
    Xa, Xh, ya, yh = train_test_split(
        Xtr, ytr, test_size=0.25, stratify=ytr, random_state=RANDOM_STATE
    )
    rf = RandomForestClassifier(
        n_estimators=300, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight="balanced", max_features="sqrt",
    ).fit(Xa, ya)
    svm = LinearSVC(max_iter=5000, random_state=RANDOM_STATE,
                    class_weight="balanced").fit(Xa, ya)
    knn = KNeighborsClassifier(n_neighbors=7, n_jobs=-1).fit(Xa, ya)

    d = svm.decision_function(Xtr)
    scale = (float(d.min()), float(d.max()))
    ph = proba_ensamble(rf, svm, knn, Xh, scale)
    mejor = (0.0, 0.5)
    for t in np.arange(0.30, 0.70, 0.01):
        m = f1_score(yh, (ph >= t).astype(int), average="macro")
        if m > mejor[0]:
            mejor = (float(m), round(float(t), 2))
    print(f"  umbral calibrado={mejor[1]}  macro-F1 holdout={mejor[0]:.4f}")
    return {"umbral_decision": mejor[1], "macro_f1_holdout": round(mejor[0], 4),
            "svm_proba_scale": scale}


def main() -> None:
    t0 = time.time()
    train = load_raw("KDDTrain+.txt")
    test = load_raw("KDDTest+.txt")
    print(f"train={len(train):,}  test={len(test):,}  "
          f"ataques_train={train[TARGET].sum():,}  ataques_test={test[TARGET].sum():,}")

    pp = Preprocessor().fit(train)
    Xtr = pp.fit_transform(train)
    Xte = pp.transform(test)
    ytr, yte = train[TARGET].to_numpy(), test[TARGET].to_numpy()
    _guardar_caches(Xtr, ytr, "train")
    _guardar_caches(Xte, yte, "test")
    print(f"matriz: {Xtr.shape}  preproceso en {time.time() - t0:.1f}s")

    print("Calibrando umbral del ensamble sobre holdout...")
    cal = _calibrar_umbral(pp, Xtr, ytr)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pp, MODEL_DIR / "preprocessor.joblib")

    # Modelos definitivos sobre TODO el entrenamiento.
    print("Entrenando modelos finales...")
    rf = RandomForestClassifier(
        n_estimators=300, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight="balanced", max_features="sqrt",
    ).fit(Xtr, ytr)
    joblib.dump(rf, MODEL_DIR / "rf.joblib")
    print(f"  RandomForest OK  ({time.time() - t0:.1f}s)")

    svm = LinearSVC(max_iter=5000, random_state=RANDOM_STATE,
                    class_weight="balanced").fit(Xtr, ytr)
    joblib.dump(svm, MODEL_DIR / "svm.joblib")
    print(f"  LinearSVC OK  ({time.time() - t0:.1f}s)")

    knn = KNeighborsClassifier(n_neighbors=7, n_jobs=-1).fit(Xtr, ytr)
    joblib.dump(knn, MODEL_DIR / "knn.joblib")
    print(f"  KNN OK  ({time.time() - t0:.1f}s)")

    normales = train[train[TARGET] == 0]
    iforest = IsolationForest(
        n_estimators=200, contamination="auto", random_state=RANDOM_STATE, n_jobs=-1
    ).fit(pp.transform(normales))
    joblib.dump(iforest, MODEL_DIR / "iforest.joblib")
    print(f"  IsolationForest OK  ({time.time() - t0:.1f}s)")

    metadata = {
        "version": "0.3.0",
        "n_features": pp.n_features(),
        "feature_names": pp.feature_names(),
        "dataset_train": "NSL-KDD KDDTrain+",
        "dataset_test": "NSL-KDD KDDTest+",
        "filas_train": len(train),
        "filas_test": len(test),
        "modelos": ["ensamble(rf+knn+svm)", "rf", "svm", "knn", "iforest"],
        "target": TARGET,
        "categorias": {c: v for c, v in pp.cat_categories_.items()},
        **cal,
    }
    (MODEL_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nListo en {time.time() - t0:.1f}s. Modelos en {MODEL_DIR}")


if __name__ == "__main__":
    main()