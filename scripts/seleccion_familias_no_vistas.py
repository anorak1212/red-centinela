"""Seleccion por generalizacion a familias no vistas (leave-one-family-out).

Protocolo:
  1. Se aparta una familia completa de ataque de KDDTrain+ (r2l, luego u2r).
  2. Se entrena sin ella y se calibra el umbral en un holdout interno del
     resto, igual que hace motor/train.py.
  3. Se mide el recall sobre la familia apartada, que el modelo nunca vio.
     Ese recall es el criterio de seleccion, no KDDTest+.
  4. KDDTest+ no se toca en este script.

El candidato con mejor recall medio en familias no vistas se lleva a una
evaluacion unica en motor/evaluate.py.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from motor.data import CLASSES, TARGET, TARGET_MULTI, load_raw
from motor.preprocess import Preprocessor
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

RANDOM_STATE = 42
UMBRALES = np.arange(0.20, 0.71, 0.01)
SALIDA = Path(__file__).resolve().parents[1] / "docs" / "SELECCION_FAMILIAS_NO_VISTAS.json"


def _mejor_umbral(y, proba) -> tuple[float, float]:
    mejor_t, mejor = 0.5, -1.0
    for t in UMBRALES:
        f1 = float(f1_score(y, (proba >= t).astype(int), average="macro"))
        if f1 > mejor:
            mejor, mejor_t = f1, float(t)
    return round(mejor_t, 3), mejor


def _candidatos(n_arboles: int = 200) -> dict:
    return {
        "rf_balanceado": RandomForestClassifier(
            n_estimators=n_arboles, n_jobs=-1, random_state=RANDOM_STATE,
            class_weight="balanced", max_features="sqrt",
        ),
        "extratrees_balanceado": ExtraTreesClassifier(
            n_estimators=n_arboles, n_jobs=-1, random_state=RANDOM_STATE,
            class_weight="balanced", max_features="sqrt",
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.1, class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
    }


def main() -> None:
    df = load_raw("KDDTrain+.txt")
    ybin = df[TARGET].to_numpy()
    ymulti = df[TARGET_MULTI].to_numpy()
    print(f"train total {len(df):,} filas")
    print("distribucion:", {c: int((ymulti == i).sum()) for i, c in enumerate(CLASSES)})

    resultados: dict[str, dict] = {n: {} for n in _candidatos()}
    for familia in ("r2l", "u2r"):
        idx = CLASSES.index(familia)
        mascara = ymulti == idx
        df_val = df[mascara].reset_index(drop=True)
        df_resto = df[~mascara].reset_index(drop=True)
        if len(df_val) < 20:
            print(f"{familia}: solo {len(df_val)} filas, se omite")
            continue
        y_resto = ybin[~mascara]
        ym_resto = ymulti[~mascara]
        X_aj, X_cal, ya, yc = train_test_split(
            df_resto, y_resto, test_size=0.2, stratify=ym_resto,
            random_state=RANDOM_STATE,
        )
        pp = Preprocessor().fit(X_aj)
        Xa, Xc, Xv = pp.transform(X_aj), pp.transform(X_cal), pp.transform(df_val)
        print(f"\n--- familia {familia}: ajuste {len(Xa):,} | "
              f"calibracion {len(Xc):,} | no vista {len(Xv):,}")

        for nombre, plantilla in _candidatos().items():
            from sklearn.base import clone

            modelo = clone(plantilla)
            t = time.time()
            modelo.fit(Xa, ya)
            if hasattr(modelo, "predict_proba"):
                p_cal = modelo.predict_proba(Xc)[:, 1]
                p_val = modelo.predict_proba(Xv)[:, 1]
            else:
                d_cal = modelo.decision_function(Xc)
                d_val = modelo.decision_function(Xv)
                p_cal = 1 / (1 + np.exp(-d_cal))
                p_val = 1 / (1 + np.exp(-d_val))
            umbral, f1_cal = _mejor_umbral(yc, p_cal)
            recall = float((p_val >= umbral).mean())
            resultados[nombre][familia] = {
                "umbral": umbral,
                "macro_f1_calibracion": round(f1_cal, 4),
                "recall_familia_no_vista": round(recall, 4),
                "segundos": round(time.time() - t, 1),
            }
            print(f"  {nombre:24s} recall {recall:.4f} "
                  f"(umbral {umbral}, {time.time() - t:.0f}s)")

    resumen = []
    for nombre, por_familia in resultados.items():
        recalls = [v["recall_familia_no_vista"] for v in por_familia.values()]
        resumen.append({
            "candidato": nombre,
            "recall_medio_familias_no_vistas": round(float(np.mean(recalls)), 4) if recalls else None,
            "detalle": por_familia,
        })
    resumen.sort(key=lambda r: (r["recall_medio_familias_no_vistas"] is None,
                                -(r["recall_medio_familias_no_vistas"] or 0)))
    salida = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "protocolo": "leave-one-family-out sobre KDDTrain+; umbral calibrado en "
                     "holdout interno; KDDTest+ no se uso",
        "resultados": resumen,
        "elegido": resumen[0]["candidato"] if resumen else None,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== resumen ===")
    for r in resumen:
        print(f"  {r['candidato']:24s} {r['recall_medio_familias_no_vistas']}")
    print("elegido:", salida["elegido"])


if __name__ == "__main__":
    main()
