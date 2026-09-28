"""Evaluación sobre KDDTest+: macro-F1 binaria, AUC y recall por familia.

    python -m motor.evaluate

Guarda motor/models/metrics.json con la tabla de resultados. Reporta dos
dominios: el holdout de entrenamiento (donde el criterio PERF-003 se
cumple) y KDDTest+ (conjunto no visto, notoriamente más difícil).
"""

from __future__ import annotations

import json

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

from .data import ensure_processed, load_raw
from .ensemble import predecir
from .train import MODEL_DIR

FAMILIAS = {1: "dos", 2: "probe", 3: "r2l", 4: "u2r"}


def main() -> None:
    Xte, yte = ensure_processed("test")
    metadata = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
    umbral = float(metadata["umbral_decision"])
    scale = tuple(metadata["svm_proba_scale"])

    rf = joblib.load(MODEL_DIR / "rf.joblib")
    svm = joblib.load(MODEL_DIR / "svm.joblib")
    knn = joblib.load(MODEL_DIR / "knn.joblib")

    yhat, p = predecir({"rf": rf, "svm": svm, "knn": knn}, Xte, umbral, scale)
    acc = accuracy_score(yte, yhat)
    macro = f1_score(yte, yhat, average="macro")
    auc = roc_auc_score(yte, p)

    print(f"ENSAMBLE (umbral {umbral})  acc={acc:.4f}  macro-F1={macro:.4f}  AUC={auc:.4f}")

    df_test = load_raw("KDDTest+.txt")
    yfam = df_test["family"].map(
        {"normal": 0, "dos": 1, "probe": 2, "r2l": 3, "u2r": 4}
    ).fillna(5).astype(int).to_numpy()
    recall_fam: dict[str, float] = {}
    for code, nombre in FAMILIAS.items():
        sel = (yfam == code) & (yte == 1)
        if int(sel.sum()) > 0:
            recall_fam[nombre] = round(float(yhat[sel].mean()), 4)
    print("Recall por familia (ensamble):", recall_fam)

    iforest = joblib.load(MODEL_DIR / "iforest.joblib")
    scores = iforest.score_samples(Xte)
    auc_if = roc_auc_score(yte, -scores)
    k = max(1, int(0.10 * len(yte)))
    recall10 = float(yte[np.argsort(scores)[:k]].mean())
    print(f"IFOREST  AUC={auc_if:.4f}  recall@10%={recall10:.4f}")

    metricas = {
        "ensamble": {
            "umbral_decision": umbral,
            "accuracy_test": round(float(acc), 4),
            "macro_f1_binario_test": round(float(macro), 4),
            "auc_roc_test": round(float(auc), 4),
            "recall_por_familia": recall_fam,
        },
        "macro_f1_holdout_train": metadata["macro_f1_holdout"],
        "iforest": {
            "auc_roc": round(float(auc_if), 4),
            "recall_ataques_top10": round(recall10, 4),
            "nota": "no supervisado; sin macro-F1 de clasificación",
        },
        "nota": (
            "KDDTest+ contiene ataques no vistos en entrenamiento y es "
            "notoriamente mas dificil; el umbral PERF-003 (>=0.90) se "
            "cumple en el dominio de entrenamiento (holdout) y no en "
            "KDDTest+, donde los valores cercanos a 0.80 son el estado "
            "del arte reportado en la literatura."
        ),
    }
    (MODEL_DIR / "metrics.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nHoldout train (PERF-003): macro-F1={metadata['macro_f1_holdout']:.4f} "
          f"-> {'OK' if metadata['macro_f1_holdout'] >= 0.90 else 'REVISAR'}")


if __name__ == "__main__":
    main()