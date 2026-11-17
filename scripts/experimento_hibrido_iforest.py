"""Experimento: usar el Isolation Forest como red de rescate en la deteccion.

Problema que ataca: el RF binario detecta el 67.7 por ciento de los ataques de
KDDTest+ porque r2l y u2r aparecen en variantes que nunca vio. El Isolation
Forest, entrenado solo con trafico normal, no necesita haber visto la familia:
solo sabe que ese vector no se parece a lo normal. Hoy no interviene en la
decision, es adorno.

Protocolo (KDDTest+ no se toca):
  1. Se aparta una familia completa de KDDTrain+ (r2l, luego u2r).
  2. Con el resto se entrena el RF binario y un Isolation Forest sobre las
     filas normales. El umbral del RF se calibra en un holdout interno.
  3. El umbral del Isolation Forest se fija por PRESUPUESTO DE FALSOS POSITIVOS
     medido sobre las filas normales del holdout: se marca anomalo el
     percentil que deja fuera ese presupuesto.
  4. Se mide el recall sobre la familia apartada, que es el caso dificil, con
     y sin la red de rescate.
  5. KDDTest+ se evalua despues, una sola vez, en motor/evaluate.py.

Criterio de decision: la regla de rescate solo entra a produccion si sube el
recall de familias no vistas sin destruir la precision del holdout.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from motor.data import CLASSES, TARGET, TARGET_MULTI, load_raw
from motor.preprocess import Preprocessor
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

RANDOM_STATE = 42
N_ARBOLES = 200
UMBRALES = np.arange(0.20, 0.71, 0.01)
PRESUPUESTOS = (0.01, 0.02, 0.05, 0.10)
SALIDA = Path(__file__).resolve().parents[1] / "docs" / "EXPERIMENTO_HIBRIDO_IFOREST.json"


def _mejor_umbral(y, proba) -> tuple[float, float]:
    mejor_t, mejor = 0.5, -1.0
    for t in UMBRALES:
        f1 = float(f1_score(y, (proba >= t).astype(int), average="macro"))
        if f1 > mejor:
            mejor, mejor_t = f1, float(t)
    return round(mejor_t, 3), mejor


def _umbral_anomalia(scores_normales: np.ndarray, presupuesto: float) -> float:
    """Corte de score que marca como anomalo a lo sumo `presupuesto` del normal.

    score_samples devuelve valores mas bajos cuanto mas raro es el vector, por
    eso el corte se toma por abajo.
    """
    return float(np.quantile(scores_normales, presupuesto))


def _bloque(y, p_rf, umbral_rf, scores, corte) -> dict:
    base = (p_rf >= umbral_rf)
    rescate = base | (scores <= corte)
    return {
        "recall_ataque": round(float(base.mean()), 4),
        "recall_ataque_con_rescate": round(float(rescate.mean()), 4),
    }


def main() -> None:
    df = load_raw("KDDTrain+.txt")
    ybin = df[TARGET].to_numpy()
    ymulti = df[TARGET_MULTI].to_numpy()
    print(f"train {len(df):,} filas")

    resultados: dict[str, dict] = {}
    for familia in ("r2l", "u2r"):
        idx = CLASSES.index(familia)
        mascara = ymulti == idx
        df_val = df[mascara].reset_index(drop=True)
        df_resto = df[~mascara].reset_index(drop=True)
        y_val_bin = ybin[mascara]
        y_resto_bin = ybin[~mascara]
        ym_resto = ymulti[~mascara]

        df_aj, df_cal, ya, yc, _yma, _ymc = train_test_split(
            df_resto, y_resto_bin, ym_resto, test_size=0.2,
            stratify=ym_resto, random_state=RANDOM_STATE,
        )
        pp = Preprocessor().fit(df_aj)
        Xa, Xc, Xv = pp.transform(df_aj), pp.transform(df_cal), pp.transform(df_val)
        print(f"\n--- familia {familia}: ajuste {len(Xa):,} | "
              f"holdout {len(Xc):,} | no vista {len(Xv):,}")

        t = time.time()
        rf = RandomForestClassifier(
            n_estimators=N_ARBOLES, n_jobs=-1, random_state=RANDOM_STATE,
            class_weight="balanced", max_features="sqrt",
        ).fit(Xa, ya)
        umbral_rf, _ = _mejor_umbral(yc, rf.predict_proba(Xc)[:, 1])
        p_c = rf.predict_proba(Xc)[:, 1]
        p_v = rf.predict_proba(Xv)[:, 1]
        print(f"  RF listo en {time.time() - t:.0f}s (umbral {umbral_rf})")

        t = time.time()
        iforest = IsolationForest(
            n_estimators=200, contamination="auto", random_state=RANDOM_STATE,
            n_jobs=-1,
        ).fit(Xa[ya == 0])
        s_c = iforest.score_samples(Xc)
        s_v = iforest.score_samples(Xv)
        print(f"  Isolation Forest listo en {time.time() - t:.0f}s")

        normales_c = yc == 0
        base_c = (p_c >= umbral_rf)
        fp_base = float(base_c[normales_c].mean())
        detalle = {
            "umbral_rf": umbral_rf,
            "recall_familia_no_vista_rf": _bloque(
                y_val_bin, p_v, umbral_rf, s_v, -np.inf)["recall_ataque"],
            "falsos_positivos_holdout_normal_rf": round(fp_base, 4),
            "macro_f1_holdout_rf": round(float(f1_score(
                yc, base_c.astype(int), average="macro")), 4),
            "presupuestos": {},
        }

        for ppto in PRESUPUESTOS:
            corte = _umbral_anomalia(s_c[normales_c], ppto)
            con_rescate_c = base_c | (s_c <= corte)
            con_rescate_v = (p_v >= umbral_rf) | (s_v <= corte)
            detalle["presupuestos"][f"{ppto:.0%}"] = {
                "corte_score": round(corte, 4),
                "recall_familia_no_vista": round(float(con_rescate_v.mean()), 4),
                "falsos_positivos_holdout_normal": round(
                    float(con_rescate_c[normales_c].mean()), 4),
                "macro_f1_holdout": round(float(f1_score(
                    yc, con_rescate_c.astype(int), average="macro")), 4),
            }
            d = detalle["presupuestos"][f"{ppto:.0%}"]
            print(f"  rescate {ppto:>4.0%}: recall no vista "
                  f"{detalle['recall_familia_no_vista_rf']:.4f} -> "
                  f"{d['recall_familia_no_vista']:.4f} | FP normal "
                  f"{fp_base:.4f} -> {d['falsos_positivos_holdout_normal']:.4f} | "
                  f"macro-F1 holdout {detalle['macro_f1_holdout_rf']} -> "
                  f"{d['macro_f1_holdout']}")
        resultados[familia] = detalle

    salida = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "protocolo": "leave-one-family-out sobre KDDTrain+; umbral del RF por "
                     "macro-F1 del holdout; corte de anomalia por presupuesto de "
                     "falsos positivos sobre normales del holdout; KDDTest+ no se uso",
        "resultados": resultados,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nescrito {SALIDA.name}")


if __name__ == "__main__":
    main()
