"""FASE C v2: búsqueda acotada para mejorar macro-F1 binario y r2l/u2r sin fuga.
- CV interna en KDDTrain+, preprocesador/SMOTENC solo en train del fold.
- Umbral elegido en validación. KDDTest+ NO se usa (solo en evaluate final, una vez).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTENC
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold

from motor.data import CATEGORICAL, CLASSES, FEATURE_NAMES, MODEL_DIR, TARGET, TARGET_MULTI, load_raw
from motor.ensemble import construir_manifiesto, sha256
from motor.preprocess import Preprocessor

RANDOM_STATE = 42
UMBRALES = np.arange(0.20, 0.71, 0.005)
CAT_INDICES = [FEATURE_NAMES.index(c) for c in CATEGORICAL]
CLASE_IDX = {c: i for i, c in enumerate(CLASSES)}


def _mejor_umbral(y_true, proba):
    mejor_t, mejor_f1 = 0.5, -1.0
    for t in UMBRALES:
        f1 = float(f1_score(y_true, (proba >= t).astype(int), average="macro"))
        if f1 > mejor_f1:
            mejor_f1, mejor_t = f1, float(t)
    return round(mejor_t, 3), float(mejor_f1)


def _smote(X_df, y_multi, r2l_t, u2r_t, seed):
    counts = pd.Series(y_multi).value_counts().to_dict()
    n_r2l = counts.get(CLASE_IDX["r2l"], 0)
    n_u2r = counts.get(CLASE_IDX["u2r"], 0)
    estrategia = {}
    if n_r2l > 1 and r2l_t > n_r2l:
        estrategia[CLASE_IDX["r2l"]] = min(r2l_t, counts.get(0, r2l_t))
    if n_u2r > 1 and u2r_t > n_u2r:
        estrategia[CLASE_IDX["u2r"]] = min(u2r_t, counts.get(0, u2r_t))
    if not estrategia:
        return X_df, y_multi
    k = max(1, min(5, n_u2r - 1 if n_u2r > 1 else 5, n_r2l - 1 if n_r2l > 1 else 5))
    try:
        sm = SMOTENC(categorical_features=CAT_INDICES, sampling_strategy=estrategia,
                     random_state=seed, k_neighbors=k)
        X_res, y_res = sm.fit_resample(X_df[FEATURE_NAMES], y_multi)
        return pd.DataFrame(X_res, columns=FEATURE_NAMES), np.asarray(y_res)
    except Exception as exc:  # noqa: BLE001
        print(f"    [SMOTENC omitido: {type(exc).__name__}: {exc}]")
        return X_df, y_multi


def cv_binario(cfg, train, n_splits=3):
    y_multi = train[TARGET_MULTI].to_numpy()
    y_bin = train[TARGET].to_numpy()
    X_df = train[FEATURE_NAMES].reset_index(drop=True)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    folds = []
    for i, (tr, va) in enumerate(skf.split(X_df, y_multi), 1):
        print(f"  bin fold {i}/{n_splits} {cfg['nombre']}...")
        Xtr, ym = _smote(X_df.iloc[tr], y_multi[tr], cfg["smote_r2l"], cfg["smote_u2r"], RANDOM_STATE + i)
        yb = (ym != 0).astype(int)
        pp = Preprocessor().fit(Xtr)
        Xa, Xv = pp.transform(Xtr), pp.transform(X_df.iloc[va])
        rf = RandomForestClassifier(
            n_estimators=cfg["n"], n_jobs=-1, random_state=RANDOM_STATE,
            class_weight=cfg["cw"], max_features=cfg.get("mf", "sqrt"),
            max_depth=cfg.get("md"), min_samples_leaf=cfg.get("msl", 1),
        ).fit(Xa, yb)
        proba = rf.predict_proba(Xv)[:, 1]
        umbral, mf1 = _mejor_umbral(y_bin[va], proba)
        folds.append({"umbral": umbral, "macro_f1": mf1})
    return {
        "nombre": cfg["nombre"],
        "macro_f1_binario_val": float(np.mean([f["macro_f1"] for f in folds])),
        "umbral": float(np.median([f["umbral"] for f in folds])),
        "folds": folds,
    }


def cv_multi(cfg, train, n_splits=3):
    y_multi = train[TARGET_MULTI].to_numpy()
    X_df = train[FEATURE_NAMES].reset_index(drop=True)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    folds = []
    for i, (tr, va) in enumerate(skf.split(X_df, y_multi), 1):
        print(f"  multi fold {i}/{n_splits} {cfg['nombre']}...")
        Xtr, ym = _smote(X_df.iloc[tr], y_multi[tr], cfg["smote_r2l"], cfg["smote_u2r"], RANDOM_STATE + i)
        pp = Preprocessor().fit(Xtr)
        Xa, Xv = pp.transform(Xtr), pp.transform(X_df.iloc[va])
        rfm = RandomForestClassifier(
            n_estimators=cfg["n"], n_jobs=-1, random_state=RANDOM_STATE,
            class_weight=cfg["cw"], max_features=cfg.get("mf", "sqrt"),
            max_depth=cfg.get("md"), min_samples_leaf=cfg.get("msl", 1),
        ).fit(Xa, ym)
        yhat = rfm.predict(Xv)
        mf1 = float(f1_score(y_multi[va], yhat, average="macro", zero_division=0))
        rep = classification_report(y_multi[va], yhat, labels=list(range(5)), target_names=CLASSES,
                                    output_dict=True, zero_division=0)
        folds.append({"macro_f1": mf1, "r2l": rep["r2l"]["recall"], "u2r": rep["u2r"]["recall"]})
    return {
        "nombre": cfg["nombre"],
        "macro_f1_multiclase_val": float(np.mean([f["macro_f1"] for f in folds])),
        "recall_r2l": float(np.mean([f["r2l"] for f in folds])),
        "recall_u2r": float(np.mean([f["u2r"] for f in folds])),
        "folds": folds,
    }


def entrenar_final(mejor_bin, mejor_multi, train):
    y_multi = train[TARGET_MULTI].to_numpy()
    X_df = train[FEATURE_NAMES]
    # Binario
    Xb, ymb = _smote(X_df, y_multi, mejor_bin["smote_r2l"], mejor_bin["smote_u2r"], RANDOM_STATE)
    ybb = (ymb != 0).astype(int)
    pp_b = Preprocessor().fit(Xb)
    Xtr_b = pp_b.transform(Xb)
    rf = RandomForestClassifier(
        n_estimators=mejor_bin["n"], n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=mejor_bin["cw"], max_features=mejor_bin.get("mf", "sqrt"),
        max_depth=mejor_bin.get("md"), min_samples_leaf=mejor_bin.get("msl", 1),
    ).fit(Xtr_b, ybb)

    # Multiclase (puede usar distinto resample) - pero un solo preprocessor debe usarse en producción
    # Para compatibilidad, usamos el preprocessor del binario ajustado sobre TODO train sin SMOTE
    # de forma consistente? Mejor: entrenar ambos con mismo pp fit sobre train completo resampleado
    # según multi para consistencia de features; pero binario necesita su propio ajuste.
    # En producción se usa un solo preprocessor.joblib. Simplificación: usar mismo esquema que v1 (uno).
    Xm, ymm = _smote(X_df, y_multi, mejor_multi["smote_r2l"], mejor_multi["smote_u2r"], RANDOM_STATE)
    pp = Preprocessor().fit(Xm)
    Xtr_m = pp.transform(Xm)
    ybm = (ymm != 0).astype(int)
    # reentrenar binario con mismo preprocessor/espacio para compatibilidad
    rf = RandomForestClassifier(
        n_estimators=mejor_bin["n"], n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=mejor_bin["cw"], max_features=mejor_bin.get("mf", "sqrt"),
        max_depth=mejor_bin.get("md"), min_samples_leaf=mejor_bin.get("msl", 1),
    ).fit(Xtr_m, ybm)
    rf_multi = RandomForestClassifier(
        n_estimators=mejor_multi["n"], n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=mejor_multi["cw"], max_features=mejor_multi.get("mf", "sqrt"),
        max_depth=mejor_multi.get("md"), min_samples_leaf=mejor_multi.get("msl", 1),
    ).fit(Xtr_m, ymm)
    normales = Xtr_m[ybm == 0]
    iforest = IsolationForest(n_estimators=200, contamination="auto", random_state=RANDOM_STATE, n_jobs=-1).fit(normales)

    # umbral binario recalibrado en holdout interno rápido (del train, sin KDDTest+)
    from sklearn.model_selection import train_test_split
    Xa2, Xh2, yba2, ybh2, yma2, ymh2 = train_test_split(Xtr_m, ybm, ymm, test_size=0.2,
                                                         stratify=ymm, random_state=RANDOM_STATE)
    rf_tmp = RandomForestClassifier(
        n_estimators=min(200, mejor_bin["n"]), n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=mejor_bin["cw"], max_features=mejor_bin.get("mf", "sqrt"),
        max_depth=mejor_bin.get("md"), min_samples_leaf=mejor_bin.get("msl", 1),
    ).fit(Xa2, yba2)
    umbral, _ = _mejor_umbral(ybh2, rf_tmp.predict_proba(Xh2)[:, 1])
    del rf_tmp
    return pp, rf, rf_multi, iforest, umbral, int(len(Xtr_m))


def guardar(pp, rf, rf_multi, iforest, umbral, train, info):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pp, MODEL_DIR / "preprocessor.joblib")
    joblib.dump(rf, MODEL_DIR / "rf.joblib")
    joblib.dump(rf_multi, MODEL_DIR / "rf_multi.joblib")
    joblib.dump(iforest, MODEL_DIR / "iforest.joblib")
    metadata = {
        "version": "1.2.0-fasec2",
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "semilla": RANDOM_STATE,
        "n_features": pp.n_features(),
        "feature_names": pp.feature_names(),
        "dataset_train": "NSL-KDD KDDTrain+",
        "dataset_test": "NSL-KDD KDDTest+",
        "filas_train": int(len(train)),
        "modelo_produccion": "RandomForest",
        "modelos": ["rf", "rf_multi", "iforest"],
        "comparativa": [],
        "clases": CLASSES,
        "target_binario": TARGET,
        "target_multiclase": TARGET_MULTI,
        "categorias": {c: v for c, v in pp.cat_categories_.items()},
        "tiempos_entrenamiento_segundos": info.get("tiempos", {}),
        "umbral_decision": float(umbral),
        "macro_f1_binario_holdout": 0.0,
        "macro_f1_multiclase_holdout": 0.0,
        "weighted_f1_multiclase_holdout": 0.0,
        "nota_seleccion": "FASE C v2: hiperparámetros/umbral por CV interna en KDDTrain+; KDDTest+ usado solo en evaluate final",
        "cv_info": info,
        "svm_proba_scale": [0.0, 1.0],
    }
    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    manifiesto = construir_manifiesto()
    manifiesto["metadata_sha256"] = sha256(MODEL_DIR / "metadata.json")
    manifiesto["version"] = metadata["version"]
    (MODEL_DIR / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    t0 = time.time()
    train = load_raw("KDDTrain+.txt")
    print(f"Train {len(train)}")

    peso_multi = {0: 1, 1: 1, 2: 1, 3: 12, 4: 20}
    cands_bin = [
        {"nombre": "bin_base", "n": 300, "cw": "balanced", "smote_r2l": 0, "smote_u2r": 0},
        {"nombre": "bin_base_msl2", "n": 300, "cw": "balanced", "smote_r2l": 0, "smote_u2r": 0, "msl": 2},
        {"nombre": "bin_smote_suave", "n": 300, "cw": "balanced", "smote_r2l": 3000, "smote_u2r": 500},
        {"nombre": "bin_400_msl2", "n": 400, "cw": "balanced", "smote_r2l": 0, "smote_u2r": 0, "msl": 2},
    ]
    cands_multi = [
        {"nombre": "multi_base", "n": 300, "cw": "balanced_subsample", "smote_r2l": 0, "smote_u2r": 0},
        {"nombre": "multi_reforzado", "n": 300, "cw": peso_multi, "smote_r2l": 0, "smote_u2r": 0},
        {"nombre": "multi_smote_ref", "n": 300, "cw": peso_multi, "smote_r2l": 3000, "smote_u2r": 500},
        {"nombre": "multi_smote_med_ref", "n": 400, "cw": peso_multi, "smote_r2l": 6000, "smote_u2r": 1000, "msl": 2},
    ]

    res_bin = [cv_binario(c, train) for c in cands_bin]
    res_bin.sort(key=lambda x: x["macro_f1_binario_val"], reverse=True)
    mejor_bin = next(c for c in cands_bin if c["nombre"] == res_bin[0]["nombre"])
    print("BIN:", [(r["nombre"], round(r["macro_f1_binario_val"], 5), r["umbral"]) for r in res_bin])

    res_multi = [cv_multi(c, train) for c in cands_multi]
    res_multi.sort(key=lambda x: (x["macro_f1_multiclase_val"], x["recall_r2l"] + x["recall_u2r"]), reverse=True)
    mejor_multi = next(c for c in cands_multi if c["nombre"] == res_multi[0]["nombre"])
    print("MULTI:", [(r["nombre"], round(r["macro_f1_multiclase_val"], 5), round(r["recall_r2l"], 4), round(r["recall_u2r"], 4)) for r in res_multi])

    print("Entrenando final...")
    t = time.time()
    pp, rf, rf_multi, iforest, umbral, filas = entrenar_final(mejor_bin, mejor_multi, train)
    tiempos = {"total_final_s": round(time.time() - t, 1)}
    info = {"mejor_bin": res_bin[0], "mejor_multi": res_multi[0], "tiempos": tiempos}
    guardar(pp, rf, rf_multi, iforest, umbral, train, info)

    out = {"segundos_total": round(time.time() - t0, 1), "bin": res_bin, "multi": res_multi, "elegidos": {"bin": res_bin[0]["nombre"], "multi": res_multi[0]["nombre"], "umbral": umbral}}
    Path("docs/FASE_C_v2_experimento.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Listo", out["elegidos"], "s", out["segundos_total"])
    print("Siguiente (UNA vez): python -m motor.evaluate")


if __name__ == "__main__":
    main()
