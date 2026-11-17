"""FASE C v3: reforzar familias raras (r2l/u2r) en el entrenamiento binario.
- CV interna en KDDTrain+; preprocesador/SMOTENC y pesos solo en train del fold.
- Umbral elegido en validación. KDDTest+ NO se usa (solo evaluate final, una vez).
Idea: dar más peso a filas r2l/u2r para que el detector binario aprenda sus patrones.
"""
from __future__ import annotations

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
IDX_R2L, IDX_U2R = CLASSES.index("r2l"), CLASSES.index("u2r")


def _mejor_umbral(y_true, proba):
    mejor_t, mejor_f1 = 0.5, -1.0
    for t in UMBRALES:
        f1 = float(f1_score(y_true, (proba >= t).astype(int), average="macro"))
        if f1 > mejor_f1:
            mejor_f1, mejor_t = f1, float(t)
    return round(mejor_t, 3), float(mejor_f1)


def _smote(X_df, y_multi, r2l_t, u2r_t, seed):
    counts = pd.Series(y_multi).value_counts().to_dict()
    n_r2l = counts.get(IDX_R2L, 0)
    n_u2r = counts.get(IDX_U2R, 0)
    estrategia = {}
    if n_r2l > 1 and r2l_t > n_r2l:
        estrategia[IDX_R2L] = min(r2l_t, counts.get(0, r2l_t))
    if n_u2r > 1 and u2r_t > n_u2r:
        estrategia[IDX_U2R] = min(u2r_t, counts.get(0, u2r_t))
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


def sample_weight_bin(y_multi, w_r2l=8.0, w_u2r=12.0):
    w = np.ones(len(y_multi), dtype=float)
    w[y_multi == IDX_R2L] = w_r2l
    w[y_multi == IDX_U2R] = w_u2r
    return w


def cv_eval(cand, train, n_splits=3):
    y_multi_all = train[TARGET_MULTI].to_numpy()
    y_bin_all = train[TARGET].to_numpy()
    X_df = train[FEATURE_NAMES].reset_index(drop=True)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    folds = []
    for i, (tr, va) in enumerate(skf.split(X_df, y_multi_all), 1):
        print(f"  fold {i}/{n_splits} {cand['nombre']}...")
        Xtr_df, ym = _smote(X_df.iloc[tr], y_multi_all[tr], cand["smote_r2l"], cand["smote_u2r"], RANDOM_STATE + i)
        yb = (ym != 0).astype(int)
        sw = sample_weight_bin(ym, cand["w_r2l"], cand["w_u2r"]) if cand["peso_bin"] else None
        pp = Preprocessor().fit(Xtr_df)
        Xa, Xv = pp.transform(Xtr_df), pp.transform(X_df.iloc[va])
        rf = RandomForestClassifier(
            n_estimators=cand["n"], n_jobs=-1, random_state=RANDOM_STATE,
            class_weight=cand.get("cw_bin", "balanced"), max_features="sqrt",
            min_samples_leaf=cand.get("msl", 1),
        )
        rf.fit(Xa, yb, sample_weight=sw)
        proba = rf.predict_proba(Xv)[:, 1]
        umbral, mf1_bin = _mejor_umbral(y_bin_all[va], proba)
        yhat_b = (proba >= umbral).astype(int)
        # recalls de detección por familia (binario)
        det = {}
        for fam, idx in [("r2l", IDX_R2L), ("u2r", IDX_U2R)]:
            sel = y_multi_all[va] == idx
            det[fam] = float(yhat_b[sel].mean()) if sel.any() else None
        # multiclas
        rfm = RandomForestClassifier(
            n_estimators=cand["n"], n_jobs=-1, random_state=RANDOM_STATE,
            class_weight=cand["cw_multi"], max_features="sqrt", min_samples_leaf=cand.get("msl", 1),
        ).fit(Xa, ym)
        yhat_m = rfm.predict(Xv)
        mf1_m = float(f1_score(y_multi_all[va], yhat_m, average="macro", zero_division=0))
        folds.append({"umbral": umbral, "mf1_bin": mf1_bin, "mf1_m": mf1_m, "det_r2l": det["r2l"], "det_u2r": det["u2r"]})
    def media(k):
        vals = [f[k] for f in folds if f[k] is not None]
        return float(np.mean(vals)) if vals else None
    return {
        "nombre": cand["nombre"], "folds": folds,
        "macro_f1_binario_val": media("mf1_bin"), "macro_f1_multiclase_val": media("mf1_m"),
        "det_r2l": media("det_r2l"), "det_u2r": media("det_u2r"),
        "umbral": float(np.median([f["umbral"] for f in folds])),
    }


def entrenar_final(cand, train, umbral):
    y_multi = train[TARGET_MULTI].to_numpy()
    X_df = train[FEATURE_NAMES]
    X_res, ym = _smote(X_df, y_multi, cand["smote_r2l"], cand["smote_u2r"], RANDOM_STATE)
    yb = (ym != 0).astype(int)
    sw = sample_weight_bin(ym, cand["w_r2l"], cand["w_u2r"]) if cand["peso_bin"] else None
    pp = Preprocessor().fit(X_res)
    Xtr = pp.transform(X_res)
    rf = RandomForestClassifier(
        n_estimators=cand["n"], n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=cand.get("cw_bin", "balanced"), max_features="sqrt", min_samples_leaf=cand.get("msl", 1),
    ).fit(Xtr, yb, sample_weight=sw)
    rf_multi = RandomForestClassifier(
        n_estimators=cand["n"], n_jobs=-1, random_state=RANDOM_STATE,
        class_weight=cand["cw_multi"], max_features="sqrt", min_samples_leaf=cand.get("msl", 1),
    ).fit(Xtr, ym)
    normales = Xtr[yb == 0]
    iforest = IsolationForest(n_estimators=200, contamination="auto", random_state=RANDOM_STATE, n_jobs=-1).fit(normales)
    return pp, rf, rf_multi, iforest


def guardar(pp, rf, rf_multi, iforest, umbral, train, info):
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pp, MODEL_DIR / "preprocessor.joblib")
    joblib.dump(rf, MODEL_DIR / "rf.joblib")
    joblib.dump(rf_multi, MODEL_DIR / "rf_multi.joblib")
    joblib.dump(iforest, MODEL_DIR / "iforest.joblib")
    metadata = {
        "version": "1.3.0-fasec3", "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "semilla": RANDOM_STATE, "n_features": pp.n_features(), "feature_names": pp.feature_names(),
        "dataset_train": "NSL-KDD KDDTrain+", "dataset_test": "NSL-KDD KDDTest+",
        "filas_train": int(len(train)), "modelo_produccion": "RandomForest",
        "modelos": ["rf", "rf_multi", "iforest"], "comparativa": [], "clases": CLASSES,
        "target_binario": TARGET, "target_multiclase": TARGET_MULTI,
        "categorias": {c: v for c, v in pp.cat_categories_.items()},
        "tiempos_entrenamiento_segundos": {}, "umbral_decision": float(umbral),
        "macro_f1_binario_holdout": 0.0, "macro_f1_multiclase_holdout": 0.0,
        "weighted_f1_multiclase_holdout": 0.0,
        "nota_seleccion": "FASE C v3: pesos reforzando r2l/u2r en binario, CV interna, KDDTest+ una sola vez",
        "cv_info": info, "svm_proba_scale": [0.0, 1.0],
    }
    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    manifiesto = construir_manifiesto()
    manifiesto["metadata_sha256"] = sha256(MODEL_DIR / "metadata.json")
    manifiesto["version"] = metadata["version"]
    (MODEL_DIR / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    t0 = time.time()
    train = load_raw("KDDTrain+.txt")
    peso_multi = {0: 1, 1: 1, 2: 1, 3: 12, 4: 20}
    cands = [
        {"nombre": "v1_fasec_ref", "n": 300, "peso_bin": False, "w_r2l": 1, "w_u2r": 1,
         "smote_r2l": 3000, "smote_u2r": 500, "cw_bin": "balanced", "cw_multi": peso_multi},
        {"nombre": "bin_peso_raro_suave", "n": 300, "peso_bin": True, "w_r2l": 6, "w_u2r": 15,
         "smote_r2l": 3000, "smote_u2r": 500, "cw_bin": "balanced", "cw_multi": peso_multi},
        {"nombre": "bin_peso_raro_fuerte", "n": 300, "peso_bin": True, "w_r2l": 10, "w_u2r": 25,
         "smote_r2l": 3000, "smote_u2r": 500, "cw_bin": "balanced", "cw_multi": peso_multi},
        {"nombre": "bin_peso_raro_smote_mas", "n": 350, "peso_bin": True, "w_r2l": 8, "w_u2r": 20,
         "smote_r2l": 5000, "smote_u2r": 800, "cw_bin": "balanced", "cw_multi": peso_multi, "msl": 2},
    ]
    resultados = []
    for c in cands:
        print(f"\n== {c['nombre']} ==")
        r = cv_eval(c, train)
        resultados.append(r)
        print(f"  bin={r['macro_f1_binario_val']:.5f} multi={r['macro_f1_multiclase_val']:.5f} det_r2l={r['det_r2l']} det_u2r={r['det_u2r']} thr={r['umbral']}")
    resultados.sort(key=lambda x: (x["macro_f1_binario_val"], (x["det_r2l"] or 0) + (x["det_u2r"] or 0)), reverse=True)
    mejor = resultados[0]
    mejor_c = next(c for c in cands if c["nombre"] == mejor["nombre"])
    print(f"\nMejor: {mejor['nombre']} umbral {mejor['umbral']}")
    pp, rf, rf_multi, iforest = entrenar_final(mejor_c, train, mejor["umbral"])
    guardar(pp, rf, rf_multi, iforest, mejor["umbral"], train, {"resultados": resultados, "elegido": mejor})
    Path("docs/FASE_C_v3_experimento.json").write_text(json.dumps({"segundos": round(time.time()-t0,1), "resultados": resultados, "elegido": mejor["nombre"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo en {time.time()-t0:.1f}s. UNA sola vez: python -m motor.evaluate")


if __name__ == "__main__":
    main()
