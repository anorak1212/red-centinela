"""Entrenamiento del motor de detección y serialización de artefactos.

    python -m motor.train

Produce en motor/models/:
    rf.joblib         Random Forest binario (producción: normal contra ataque)
    rf_multi.joblib   Random Forest de 5 clases (producción: familia de ataque)
    iforest.joblib    Isolation Forest sobre tráfico normal (apoyo no supervisado)
    preprocessor.joblib
    metadata.json     parámetros, umbral, categorías y tiempos
    manifiesto.json   SHA-256 de cada artefacto

Regla metodológica: el umbral de decisión y la selección de hiperparámetros se
hacen sobre un holdout del entrenamiento. KDDTest+ no se toca aquí; solo se
usa una vez, en motor/evaluate.py, para el informe final.
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

from .data import CLASSES, MODEL_DIR, PROC_DIR, TARGET, TARGET_MULTI, load_raw
from .ensemble import construir_manifiesto, sha256
from .preprocess import Preprocessor

RANDOM_STATE = 42
N_ARBOLES = 300
SUBSAMPLE_COMPARATIVA = 25_000
FILAS_EVAL_COMPARATIVA = 8_000
UMBRALES = np.arange(0.20, 0.71, 0.01)


def _guardar_caches(x: np.ndarray, y: np.ndarray, nombre: str) -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    np.save(PROC_DIR / f"{nombre}.X.npy", x)
    np.save(PROC_DIR / f"{nombre}.y.npy", y)


def _calibrar_umbral(proba_holdout: np.ndarray, y_holdout: np.ndarray) -> dict:
    """Umbral que maximiza el macro-F1 binario sobre el holdout del train.

    El holdout se usa para elegir el umbral y para reportarlo. No hay fuga:
    los modelos que producen esta probabilidad jamás vieron esas filas.
    """
    mejor_f1, mejor_t = 0.0, 0.5
    for t in UMBRALES:
        f1 = f1_score(y_holdout, (proba_holdout >= t).astype(int), average="macro")
        if f1 > mejor_f1:
            mejor_f1, mejor_t = float(f1), round(float(t), 2)
    return {"umbral_decision": mejor_t,
            "macro_f1_binario_holdout": round(mejor_f1, 4)}


def _comparativa(Xa, ya, Xh, yh, yh_multi) -> list[dict]:
    """LinearSVC y KNN sobre una submuestra: solo para el informe."""
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(Xa), size=min(SUBSAMPLE_COMPARATIVA, len(Xa)), replace=False)
    Xs, ys = Xa[idx], ya[idx]
    idx_h = rng.choice(len(Xh), size=min(FILAS_EVAL_COMPARATIVA, len(Xh)), replace=False)
    Xe, ye = Xh[idx_h], yh[idx_h]

    filas = []
    for nombre, modelo in (
        ("linear_svc", LinearSVC(max_iter=5000, random_state=RANDOM_STATE,
                                 class_weight="balanced")),
        ("knn7", KNeighborsClassifier(n_neighbors=7, n_jobs=-1,
                                      weights="distance")),
    ):
        t = time.time()
        modelo.fit(Xs, ys)
        yhat = modelo.predict(Xe)
        filas.append({
            "modelo": nombre,
            "filas_entrenamiento": len(Xs),
            "macro_f1_binario": round(float(f1_score(ye, yhat, average="macro")), 4),
            "accuracy": round(float((yhat == ye).mean()), 4),
            "segundos_entrenamiento": round(time.time() - t, 1),
            "nota": "solo comparativa; no se despliega",
        })
        print(f"  comparativa {nombre}: macro-F1 {filas[-1]['macro_f1_binario']}")
    return filas


def main() -> None:
    t0 = time.time()
    train = load_raw("KDDTrain+.txt")
    print(f"train={len(train):,}  clases={train[TARGET_MULTI].value_counts().to_dict()}")

    pp = Preprocessor().fit(train)
    Xtr = pp.fit_transform(train)
    ybin = train[TARGET].to_numpy()
    ymulti = train[TARGET_MULTI].to_numpy()
    _guardar_caches(Xtr, ybin, "train")
    print(f"matriz {Xtr.shape} en {time.time() - t0:.1f}s")

    # ------------------------------------------------------------------
    # 1. Holdout interno para calibrar el umbral y medir sin fuga
    # ------------------------------------------------------------------
    Xa, Xh, yba, ybh, yma, ymh = train_test_split(
        Xtr, ybin, ymulti, test_size=0.25, stratify=ymulti, random_state=RANDOM_STATE
    )
    print(f"holdout {len(Xh):,} filas; ajuste {len(Xa):,} filas")

    t = time.time()
    rf_a = RandomForestClassifier(
        n_estimators=N_ARBOLES, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight="balanced", max_features="sqrt",
    ).fit(Xa, yba)
    cal = _calibrar_umbral(rf_a.predict_proba(Xh)[:, 1], ybh)
    cal["segundos_holdout_rf_binario"] = round(time.time() - t, 1)
    print(f"umbral={cal['umbral_decision']}  macro-F1 binario holdout="
          f"{cal['macro_f1_binario_holdout']}")

    t = time.time()
    rfm_a = RandomForestClassifier(
        n_estimators=N_ARBOLES, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight="balanced_subsample", max_features="sqrt",
    ).fit(Xa, yma)
    macro_multi_holdout = float(f1_score(ymh, rfm_a.predict(Xh), average="macro"))
    weighted_multi_holdout = float(
        f1_score(ymh, rfm_a.predict(Xh), average="weighted")
    )
    cal["macro_f1_multiclase_holdout"] = round(macro_multi_holdout, 4)
    cal["weighted_f1_multiclase_holdout"] = round(weighted_multi_holdout, 4)
    cal["segundos_holdout_rf_multiclase"] = round(time.time() - t, 1)
    print(f"macro-F1 5 clases holdout={macro_multi_holdout:.4f}")

    # La escala del SVM se calcula SOLO con el conjunto de ajuste, no con el
    # holdout que evalúa: era el único punto de fuga real del pipeline viejo.
    svm_aux = LinearSVC(max_iter=5000, random_state=RANDOM_STATE,
                        class_weight="balanced").fit(Xa, yba)
    d = svm_aux.decision_function(Xa)
    cal["svm_proba_scale"] = (float(d.min()), float(d.max()))
    del svm_aux, d, rf_a, rfm_a

    print("Comparativa SVM y KNN sobre submuestra (solo informe)...")
    comparativa = _comparativa(Xa, yba, Xh, ybh, ymh)
    del Xa, Xh

    # ------------------------------------------------------------------
    # 2. Modelos definitivos sobre todo el entrenamiento
    # ------------------------------------------------------------------
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pp, MODEL_DIR / "preprocessor.joblib")

    print("Entrenando Random Forest binario...")
    t = time.time()
    rf = RandomForestClassifier(
        n_estimators=N_ARBOLES, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight="balanced", max_features="sqrt",
    ).fit(Xtr, ybin)
    joblib.dump(rf, MODEL_DIR / "rf.joblib")
    t_rf = round(time.time() - t, 1)
    print(f"  OK en {t_rf}s")

    print("Entrenando Random Forest multiclase...")
    t = time.time()
    rf_multi = RandomForestClassifier(
        n_estimators=N_ARBOLES, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight="balanced_subsample", max_features="sqrt",
    ).fit(Xtr, ymulti)
    joblib.dump(rf_multi, MODEL_DIR / "rf_multi.joblib")
    t_rfm = round(time.time() - t, 1)
    print(f"  OK en {t_rfm}s")

    print("Entrenando Isolation Forest sobre tráfico normal...")
    t = time.time()
    normales = Xtr[ybin == 0]
    iforest = IsolationForest(
        n_estimators=200, contamination="auto", random_state=RANDOM_STATE, n_jobs=-1
    ).fit(normales)
    joblib.dump(iforest, MODEL_DIR / "iforest.joblib")
    t_if = round(time.time() - t, 1)
    print(f"  OK en {t_if}s")

    metadata = {
        "version": "1.0.0",
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "semilla": RANDOM_STATE,
        "n_features": pp.n_features(),
        "feature_names": pp.feature_names(),
        "dataset_train": "NSL-KDD KDDTrain+",
        "dataset_test": "NSL-KDD KDDTest+",
        "filas_train": len(train),
        "modelo_produccion": "RandomForest",
        "modelos": ["rf", "rf_multi", "iforest"],
        "comparativa": comparativa,
        "clases": CLASSES,
        "target_binario": TARGET,
        "target_multiclase": TARGET_MULTI,
        "categorias": {c: v for c, v in pp.cat_categories_.items()},
        "tiempos_entrenamiento_segundos": {
            "rf_binario": t_rf, "rf_multiclase": t_rfm, "iforest": t_if,
        },
        **cal,
    }
    (MODEL_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifiesto = construir_manifiesto()
    manifiesto["metadata_sha256"] = sha256(MODEL_DIR / "metadata.json")
    manifiesto["version"] = metadata["version"]
    (MODEL_DIR / "manifiesto.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nListo en {time.time() - t0:.1f}s. Artefactos en {MODEL_DIR}")
    print(f"Manifiesto SHA-256 con {len(manifiesto['archivos'])} archivos.")


if __name__ == "__main__":
    main()
