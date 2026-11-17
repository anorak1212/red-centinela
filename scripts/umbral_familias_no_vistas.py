"""Calibracion del umbral de decision pensando en ataques que no se han visto.

El umbral actual (0.42) se eligio maximizando el macro-F1 de un holdout sacado
de la MISMA distribucion del entrenamiento. Ahi el modelo acierta casi todo
(0.9992), asi que el umbral optimo queda alto. KDDTest+ no se parece a eso:
contiene variantes que el modelo nunca vio y el recall de ataque cae a 0.68.

Este script elige el umbral con un criterio distinto: se aparta una familia
completa de ataque, se entrena sin ella y se mide el macro-F1 sobre una mezcla
de esa familia (nunca vista) y trafico normal, con la misma proporcion
ataque/normal que tiene KDDTest+ (12,833 contra 9,711, o sea 1.32 a 1). El
umbral que sobrevive a familias no vistas es mas bajo que el del holdout, y
tiene que serlo: ante la duda conviene marcar.

KDDTest+ no se toca. La evaluacion final sigue siendo `python -m motor.evaluate`.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from motor.data import CLASSES, TARGET, TARGET_MULTI, load_raw
from motor.preprocess import Preprocessor
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

RANDOM_STATE = 42
N_ARBOLES = 200
UMBRALES = np.round(np.arange(0.01, 0.71, 0.01), 3)
PROPORCION_TEST = 12833 / 9711
SALIDA = Path(__file__).resolve().parents[1] / "docs" / "UMBRAL_FAMILIAS_NO_VISTAS.json"


def _curva(y, proba) -> list[tuple[float, float]]:
    return [(float(t), float(f1_score(y, (proba >= t).astype(int), average="macro")))
            for t in UMBRALES]


def main() -> None:
    df = load_raw("KDDTrain+.txt")
    ybin = df[TARGET].to_numpy()
    ymulti = df[TARGET_MULTI].to_numpy()
    print(f"train {len(df):,} filas")

    por_familia: dict[str, dict] = {}
    for familia in CLASSES[1:]:
        idx = CLASSES.index(familia)
        mascara = ymulti == idx
        df_resto = df[~mascara].reset_index(drop=True)
        y_resto = ybin[~mascara]
        ym_resto = ymulti[~mascara]

        df_aj, df_cal, ya, _yc = train_test_split(
            df_resto, y_resto, test_size=0.2, stratify=ym_resto,
            random_state=RANDOM_STATE,
        )
        pp = Preprocessor().fit(df_aj)
        Xa, Xc = pp.transform(df_aj), pp.transform(df_cal)
        yc = df_cal[TARGET].to_numpy()

        t = time.time()
        rf = RandomForestClassifier(
            n_estimators=N_ARBOLES, n_jobs=-1, random_state=RANDOM_STATE,
            class_weight="balanced", max_features="sqrt",
        ).fit(Xa, ya)
        print(f"\n--- familia {familia} ({int(mascara.sum()):,} filas): "
              f"RF en {time.time() - t:.0f}s")

        # Normales del holdout: el pozo contra el que se mide la precision.
        normales = Xc[yc == 0]
        # Ataques de la familia apartada, que el modelo no vio nunca.
        Xv = pp.transform(df[mascara].reset_index(drop=True))

        n_ataques = min(len(Xv), int(len(normales) * PROPORCION_TEST))
        rng = np.random.default_rng(RANDOM_STATE)
        sel_ataques = rng.choice(len(Xv), size=n_ataques, replace=False)
        n_normales = round(n_ataques / PROPORCION_TEST)
        sel_normales = rng.choice(len(normales), size=n_normales, replace=False)

        p_v = rf.predict_proba(Xv[sel_ataques])[:, 1]
        p_n = rf.predict_proba(normales[sel_normales])[:, 1]
        proba = np.concatenate([p_n, p_v])
        y = np.concatenate([np.zeros(len(p_n), dtype=int), np.ones(len(p_v), dtype=int)])

        curva = _curva(y, proba)
        mejor_t, mejor_f1 = max(curva, key=lambda t: t[1])
        f1_en_042 = dict(curva).get(0.42)
        por_familia[familia] = {
            "filas_familia": int(mascara.sum()),
            "mezcla": {"ataques": len(p_v), "normales": len(p_n)},
            "umbral_optimo": mejor_t,
            "macro_f1_optimo": round(mejor_f1, 4),
            "macro_f1_en_042": round(f1_en_042, 4) if f1_en_042 else None,
            "curva": [{"umbral": t, "macro_f1": round(f, 4)} for t, f in curva],
        }
        print(f"  optimo umbral {mejor_t} -> macro-F1 {mejor_f1:.4f} | "
              f"en 0.42 -> {f1_en_042}")
        # Se guarda la curva completa de cada familia para promediar despues.
        if not hasattr(main, "_acumulado"):
            main._acumulado = []
        main._acumulado.append(curva)

    # Umbral que maximiza el macro-F1 promedio entre familias no vistas.
    acumulado = getattr(main, "_acumulado", [])
    promedio = []
    if acumulado:
        for i, t in enumerate(UMBRALES):
            promedio.append((float(t), float(np.mean([c[i][1] for c in acumulado]))))
    mejor_global = max(promedio, key=lambda t: t[1])
    salida = {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "protocolo": "leave-one-family-out sobre KDDTrain+; mezcla ataque/normal "
                     "con la proporcion de KDDTest+ (1.32 a 1); KDDTest+ no se uso",
        "por_familia": por_familia,
        "umbral_promedio_optimo": mejor_global[0],
        "macro_f1_promedio_optimo": round(mejor_global[1], 4),
        "promedio_curva": [{"umbral": t, "macro_f1": round(f, 4)} for t, f in promedio],
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== resumen por familia ===")
    for fam, d in por_familia.items():
        print(f"  {fam:6s} optimo {d['umbral_optimo']:.2f} -> {d['macro_f1_optimo']:.4f}"
              f"  |  en 0.42 -> {d['macro_f1_en_042']}")
    print(f"promedio: umbral {mejor_global[0]:.2f} -> macro-F1 {mejor_global[1]:.4f}")
    f1_042_prom = dict(promedio).get(0.42)
    print(f"promedio en 0.42: {f1_042_prom}")
    print(f"escrito {SALIDA.name}")


if __name__ == "__main__":
    main()
