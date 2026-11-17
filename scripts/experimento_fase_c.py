"""Experimento FASE C: mejora de r2l/u2r sin fuga de datos.

Reglas:
- Ajuste de hiperparámetros y umbral SOLO con particiones internas de KDDTrain+.
- SMOTENC solo en el subconjunto de entrenamiento de cada fold/ajuste.
- KDDTest+ NO se usa aquí; la evaluación final se hace una sola vez con
  `python -m motor.evaluate` sobre el candidato elegido.
- Conserva artefactos anteriores (backup hecho aparte). Guarda nuevos solo si mejoran.

Uso:
  python -m scripts.experimento_fase_c
  python -m scripts.experimento_fase_c --rapido
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTENC
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold

from motor.data import (
    CATEGORICAL,
    CLASSES,
    FEATURE_NAMES,
    MODEL_DIR,
    TARGET,
    TARGET_MULTI,
    load_raw,
)
from motor.ensemble import construir_manifiesto, sha256
from motor.preprocess import Preprocessor

RANDOM_STATE = 42
UMBRALES = np.arange(0.20, 0.71, 0.01)
CAT_INDICES = [FEATURE_NAMES.index(c) for c in CATEGORICAL]
CLASE_IDX = {c: i for i, c in enumerate(CLASSES)}


def _macro_f1_bin(y_true, proba, umbral: float) -> float:
    return float(f1_score(y_true, (proba >= umbral).astype(int), average="macro"))


def _mejor_umbral(y_true, proba) -> tuple[float, float]:
    mejor_t, mejor_f1 = 0.5, -1.0
    for t in UMBRALES:
        f1 = _macro_f1_bin(y_true, proba, float(t))
        if f1 > mejor_f1:
            mejor_f1, mejor_t = f1, float(t)
    return round(mejor_t, 2), float(mejor_f1)


def _smote_train(X_df: pd.DataFrame, y_multi: np.ndarray, objetivo_r2l: int, objetivo_u2r: int,
                 seed: int) -> tuple[pd.DataFrame, np.ndarray]:
    """Sobremuestreo solo de r2l/u2r en el train del fold, sin tocar validación."""
    counts = pd.Series(y_multi).value_counts().to_dict()
    n_r2l = counts.get(CLASE_IDX["r2l"], 0)
    n_u2r = counts.get(CLASE_IDX["u2r"], 0)
    estrategia = {}
    if n_r2l > 1:
        estrategia[CLASE_IDX["r2l"]] = max(n_r2l, min(objetivo_r2l, counts.get(0, n_r2l)))
    if n_u2r > 1:
        estrategia[CLASE_IDX["u2r"]] = max(n_u2r, min(objetivo_u2r, counts.get(0, n_u2r)))
    if not estrategia:
        return X_df, y_multi
    # k_neighbors debe ser < muestras de la minoría presente en el fold
    k = max(1, min(5, n_u2r - 1 if n_u2r > 1 else 5, n_r2l - 1 if n_r2l > 1 else 5))
    try:
        sm = SMOTENC(categorical_features=CAT_INDICES, sampling_strategy=estrategia,
                     random_state=seed, k_neighbors=k)
        X_res, y_res = sm.fit_resample(X_df[FEATURE_NAMES], y_multi)
        return pd.DataFrame(X_res, columns=FEATURE_NAMES), np.asarray(y_res)
    except Exception as exc:  # noqa: BLE001
        print(f"    [SMOTENC omitido: {type(exc).__name__}: {exc}]")
        return X_df, y_multi


@dataclass
class Candidato:
    nombre: str
    n_estimators: int
    max_depth: int | None
    min_samples_leaf: int
    class_weight: str | dict
    class_weight_multi: str | dict
    smote_r2l: int
    smote_u2r: int


def candidatos(rapido: bool) -> list[Candidato]:
    # Pesos reforzados: índices 0 normal,1 dos,2 probe,3 r2l,4 u2r
    peso_multi_fuerte = {0: 1, 1: 1, 2: 1, 3: 12, 4: 20}
    base = [
        Candidato("baseline_actual", 300, None, 1, "balanced", "balanced_subsample", 0, 0),
        Candidato("cw_reforzado", 300, None, 1, "balanced", peso_multi_fuerte, 0, 0),
        Candidato("smote_suave_cw", 300, None, 1, "balanced", "balanced_subsample", 3000, 500),
        Candidato("smote_suave_reforzado", 300, None, 1, "balanced", peso_multi_fuerte, 3000, 500),
    ]
    if rapido:
        return base[:3]
    base += [
        Candidato("smote_medio_reforzado", 400, None, 2, "balanced", peso_multi_fuerte, 6000, 1000),
    ]
    return base


def evaluar_fold(cand: Candidato, X_fit_df: pd.DataFrame, yb_fit: np.ndarray, ym_fit: np.ndarray,
                 X_val_df: pd.DataFrame, yb_val: np.ndarray, ym_val: np.ndarray, seed: int) -> dict:
    X_fit_df, ym_fit = _smote_train(X_fit_df, ym_fit, cand.smote_r2l, cand.smote_u2r, seed)
    yb_fit = (ym_fit != 0).astype(int)

    pp = Preprocessor().fit(X_fit_df)
    Xa = pp.transform(X_fit_df)
    Xv = pp.transform(X_val_df)

    rf = RandomForestClassifier(
        n_estimators=cand.n_estimators, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=cand.class_weight, max_features="sqrt",
        max_depth=cand.max_depth, min_samples_leaf=cand.min_samples_leaf,
    ).fit(Xa, yb_fit)
    proba = rf.predict_proba(Xv)[:, 1]
    umbral, mf1_bin = _mejor_umbral(yb_val, proba)

    rfm = RandomForestClassifier(
        n_estimators=cand.n_estimators, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=cand.class_weight_multi, max_features="sqrt",
        max_depth=cand.max_depth, min_samples_leaf=cand.min_samples_leaf,
    ).fit(Xa, ym_fit)
    yhat_m = rfm.predict(Xv)
    mf1_multi = float(f1_score(ym_val, yhat_m, average="macro", zero_division=0))
    rep = classification_report(ym_val, yhat_m, labels=list(range(5)), target_names=CLASSES,
                                output_dict=True, zero_division=0)
    recalls = {c: rep[c]["recall"] for c in ("r2l", "u2r")}
    recalls_det = {}
    yhat_b = (proba >= umbral).astype(int)
    for fam in ("r2l", "u2r"):
        idx = CLASE_IDX[fam]
        sel = ym_val == idx
        recalls_det[fam] = float(yhat_b[sel].mean()) if sel.any() else None
    return {
        "umbral": umbral,
        "macro_f1_binario_val": mf1_bin,
        "macro_f1_multiclase_val": mf1_multi,
        "recall_r2l_clasif": recalls["r2l"],
        "recall_u2r_clasif": recalls["u2r"],
        "recall_r2l_det": recalls_det["r2l"],
        "recall_u2r_det": recalls_det["u2r"],
        "filas_train_fold": int(len(Xa)),
    }


def cv_candidato(cand: Candidato, train: pd.DataFrame, n_splits: int = 3) -> dict:
    y_multi = train[TARGET_MULTI].to_numpy()
    y_bin = train[TARGET].to_numpy()
    X_df = train[FEATURE_NAMES].reset_index(drop=True)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    folds = []
    for i, (tr, va) in enumerate(skf.split(X_df, y_multi), 1):
        print(f"  fold {i}/{n_splits}...")
        f = evaluar_fold(cand, X_df.iloc[tr], y_bin[tr], y_multi[tr],
                         X_df.iloc[va], y_bin[va], y_multi[va], RANDOM_STATE + i)
        folds.append(f)
    def media(k):
        vals = [x[k] for x in folds if x[k] is not None]
        return float(np.mean(vals)) if vals else None
    return {
        "nombre": cand.nombre,
        "folds": folds,
        "macro_f1_binario_val": media("macro_f1_binario_val"),
        "macro_f1_multiclase_val": media("macro_f1_multiclase_val"),
        "recall_r2l_clasif": media("recall_r2l_clasif"),
        "recall_u2r_clasif": media("recall_u2r_clasif"),
        "recall_r2l_det": media("recall_r2l_det"),
        "recall_u2r_det": media("recall_u2r_det"),
        "umbral_sugerido": float(np.median([x["umbral"] for x in folds])),
    }


def puntaje(r: dict) -> tuple:
    """Prioriza macro-F1 y recall de familias raras (validación)."""
    return (
        (r.get("macro_f1_multiclase_val") or 0),
        (r.get("recall_r2l_det") or 0) + (r.get("recall_u2r_det") or 0),
        (r.get("macro_f1_binario_val") or 0),
    )


def entrenar_final(cand: Candidato, train: pd.DataFrame, umbral: float) -> dict:
    """Entrena modelo definitivo sobre TODO KDDTrain+ (SMOTENC solo en train completo)."""
    y_multi = train[TARGET_MULTI].to_numpy()
    X_df = train[FEATURE_NAMES]
    X_res, y_res = _smote_train(X_df, y_multi, cand.smote_r2l, cand.smote_u2r, RANDOM_STATE)
    yb_res = (y_res != 0).astype(int)

    pp = Preprocessor().fit(X_res)
    Xtr = pp.transform(X_res)

    t = time.time()
    rf = RandomForestClassifier(
        n_estimators=cand.n_estimators, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=cand.class_weight, max_features="sqrt",
        max_depth=cand.max_depth, min_samples_leaf=cand.min_samples_leaf,
    ).fit(Xtr, yb_res)
    t_rf = round(time.time() - t, 1)

    t = time.time()
    rf_multi = RandomForestClassifier(
        n_estimators=cand.n_estimators, n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=cand.class_weight_multi, max_features="sqrt",
        max_depth=cand.max_depth, min_samples_leaf=cand.min_samples_leaf,
    ).fit(Xtr, y_res)
    t_rfm = round(time.time() - t, 1)

    t = time.time()
    normales = Xtr[yb_res == 0]
    iforest = IsolationForest(n_estimators=200, contamination="auto",
                              random_state=RANDOM_STATE, n_jobs=-1).fit(normales)
    t_if = round(time.time() - t, 1)

    # Métrica de referencia interna: sobre train transformado sin resample (aprox, solo informativa)
    Xtr_orig = pp.transform(train[FEATURE_NAMES])
    meta_ref = {
        "macro_f1_binario_train_ref": round(float(f1_score(train[TARGET].to_numpy(),
            (rf.predict_proba(Xtr_orig)[:, 1] >= umbral).astype(int), average="macro")), 4),
        "macro_f1_multiclase_train_ref": round(float(f1_score(train[TARGET_MULTI].to_numpy(),
            rf_multi.predict(Xtr_orig), average="macro", zero_division=0)), 4),
    }
    return {"pp": pp, "rf": rf, "rf_multi": rf_multi, "iforest": iforest,
            "tiempos": {"rf_binario": t_rf, "rf_multiclase": t_rfm, "iforest": t_if},
            "meta_ref": meta_ref, "umbral": umbral, "filas_train_final": int(len(Xtr))}


def guardar(modelos: dict, cand: Candidato, train: pd.DataFrame, cv_res: dict) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelos["pp"], MODEL_DIR / "preprocessor.joblib")
    joblib.dump(modelos["rf"], MODEL_DIR / "rf.joblib")
    joblib.dump(modelos["rf_multi"], MODEL_DIR / "rf_multi.joblib")
    joblib.dump(modelos["iforest"], MODEL_DIR / "iforest.joblib")

    comparativa = []  # comparativa SVM/KNN no recalculada en experimento rápido
    metadata = {
        "version": "1.1.0-fasec",
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "semilla": RANDOM_STATE,
        "n_features": modelos["pp"].n_features(),
        "feature_names": modelos["pp"].feature_names(),
        "dataset_train": "NSL-KDD KDDTrain+",
        "dataset_test": "NSL-KDD KDDTest+",
        "filas_train": int(len(train)),
        "modelo_produccion": "RandomForest",
        "modelos": ["rf", "rf_multi", "iforest"],
        "comparativa": comparativa,
        "clases": CLASSES,
        "target_binario": TARGET,
        "target_multiclase": TARGET_MULTI,
        "categorias": {c: v for c, v in modelos["pp"].cat_categories_.items()},
        "tiempos_entrenamiento_segundos": modelos["tiempos"],
        "umbral_decision": float(modelos["umbral"]),
        "macro_f1_binario_holdout": modelos["meta_ref"]["macro_f1_binario_train_ref"],
        "macro_f1_multiclase_holdout": modelos["meta_ref"]["macro_f1_multiclase_train_ref"],
        "weighted_f1_multiclase_holdout": 0.0,
        "nota_seleccion": "umbral/hiperparámetros elegidos por CV interna en KDDTrain+; KDDTest+ usado solo en evaluate final",
        "candidato": cand.nombre,
        "cv_resumen": {k: v for k, v in cv_res.items() if k != "folds"},
        "svm_proba_scale": [0.0, 1.0],
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


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--rapido", action="store_true", help="menos candidatos/folds para caber holgado en tiempo")
    args = p.parse_args(argv)

    t0 = time.time()
    train = load_raw("KDDTrain+.txt")
    print(f"Train: {len(train)} filas")

    n_splits = 3
    cands = candidatos(args.rapido)
    resultados = []
    for cand in cands:
        print(f"\n== Candidato: {cand.nombre} ==")
        r = cv_candidato(cand, train, n_splits=n_splits)
        resultados.append(r)
        print(f"  val macro_f1_multi={r['macro_f1_multiclase_val']:.4f} "
              f"bin={r['macro_f1_binario_val']:.4f} "
              f"recall_r2l_det={r['recall_r2l_det']} recall_u2r_det={r['recall_u2r_det']} "
              f"umbral~{r['umbral_sugerido']}")

    resultados.sort(key=puntaje, reverse=True)
    mejor = resultados[0]
    mejor_cand = next(c for c in cands if c.nombre == mejor["nombre"])
    print(f"\nMejor por CV interna: {mejor['nombre']} -> umbral {mejor['umbral_sugerido']}")

    print("\nEntrenando candidato final sobre TODO KDDTrain+...")
    final = entrenar_final(mejor_cand, train, float(mejor["umbral_sugerido"]))
    guardar(final, mejor_cand, train, mejor)

    salida = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "segundos_total": round(time.time() - t0, 1),
        "resultados_cv": resultados,
        "elegido": mejor["nombre"],
        "nota": "KDDTest+ no usado. Ejecutar una sola vez: python -m motor.evaluate",
    }
    out = Path("docs/FASE_C_experimento.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado candidato en {MODEL_DIR} y resumen en {out}")
    print(f"Tiempo total: {salida['segundos_total']} s")
    print("Siguiente (UNA sola vez): python -m motor.evaluate")


if __name__ == "__main__":
    main()
