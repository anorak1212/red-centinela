"""Evaluación final sobre KDDTest+ y KDDTest-21.

    python -m motor.evaluate

Escribe:
    motor/models/metrics.json        cifras que consume la API y el tablero
    docs/INFORME_METRICAS.md         informe legible, generado desde las cifras

Reglas:
- KDDTest+ se usa UNA vez, aquí. Nada de este script ajusta hiperparámetros.
- Se reporta por separado lo binario (normal contra ataque) y lo multiclase
  (5 clases), porque son dos preguntas distintas y confundirlas fue el error
  de la versión 0.3.
- KDDTest-21 es el subconjunto de KDDTest+ que excluye el nivel de dificultad 21.
  Verificado sobre el archivo en disco: 22,544 registros con dificultad entre 0 y
  21; los 10,694 con dificultad exactamente 21 son los que se retiran, y quedan
  11,850, que es el tamaño publicado de KDDTest-21.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .data import CLASSES, MODEL_DIR, TARGET, TARGET_MULTI, load_raw
from .ensemble import cargar_modelos, predecir, predecir_multiclase

DOCS = Path(__file__).resolve().parents[1] / "docs"
METRICS = MODEL_DIR / "metrics.json"


def _bloque_binario(y, yhat, proba) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y, yhat)), 4),
        "macro_f1": round(float(f1_score(y, yhat, average="macro")), 4),
        "weighted_f1": round(float(f1_score(y, yhat, average="weighted")), 4),
        "precision_ataque": round(float(precision_score(y, yhat, pos_label=1,
                                                       zero_division=0)), 4),
        "recall_ataque": round(float(recall_score(y, yhat, pos_label=1,
                                                  zero_division=0)), 4),
        "auc_roc": round(float(roc_auc_score(y, proba)), 4),
        "matriz_confusion": confusion_matrix(y, yhat, labels=[0, 1]).tolist(),
        "filas": len(y),
        "ataques_reales": int(y.sum()),
    }


def _bloque_multiclase(y, yhat) -> dict:
    rep = classification_report(
        y, yhat, labels=list(range(len(CLASSES))), target_names=CLASSES,
        output_dict=True, zero_division=0,
    )
    return {
        "accuracy": round(float(accuracy_score(y, yhat)), 4),
        "macro_f1": round(float(f1_score(y, yhat, average="macro",
                                         zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y, yhat, average="weighted",
                                            zero_division=0)), 4),
        "por_clase": {
            c: {
                "precision": round(float(rep[c]["precision"]), 4),
                "recall": round(float(rep[c]["recall"]), 4),
                "f1": round(float(rep[c]["f1-score"]), 4),
                "soporte": int(rep[c]["support"]),
            }
            for c in CLASSES
        },
        "matriz_confusion": confusion_matrix(
            y, yhat, labels=list(range(len(CLASSES)))
        ).tolist(),
        "filas": len(y),
    }


def _latencia(modelos, df, repeticiones: int = 60) -> dict:
    pp = modelos["preprocessor"]
    fila = df.head(1)
    X1 = pp.transform(fila)
    probas = []
    for _ in range(repeticiones):
        t = time.perf_counter()
        modelos["rf"].predict_proba(X1)
        probas.append((time.perf_counter() - t) * 1000)
    lote = pp.transform(df.head(500))
    t = time.perf_counter()
    modelos["rf"].predict_proba(lote)
    ms_lote = (time.perf_counter() - t) * 1000 / len(lote)
    return {
        "ms_por_fila_sola": round(float(np.mean(probas)), 2),
        "ms_por_fila_en_lote_500": round(float(ms_lote), 3),
        "repeticiones": repeticiones,
        "nota": "medido en la máquina de desarrollo; el despliegue puede diferir",
    }


def main() -> None:
    modelos = cargar_modelos(verificar=True)
    md = modelos["metadata"]
    pp = modelos["preprocessor"]
    umbral = float(md["umbral_decision"])

    test = load_raw("KDDTest+.txt")
    X = pp.transform(test)
    ybin = test[TARGET].to_numpy()
    ymulti = test[TARGET_MULTI].to_numpy()

    yhat_bin, proba = predecir(modelos, X, umbral)
    yhat_multi, _ = predecir_multiclase(modelos, X)

    binario = _bloque_binario(ybin, yhat_bin, proba)
    multiclase = _bloque_multiclase(ymulti, yhat_multi)

    # Recall por familia usando el detector binario: de los ataques reales de
    # cada familia, cuántos se marcaron como ataque.
    recall_familia = {}
    for i, clase in enumerate(CLASSES[1:], start=1):
        sel = (ymulti == i)
        if sel.sum():
            recall_familia[clase] = {
                "recall_deteccion": round(float(yhat_bin[sel].mean()), 4),
                "recall_clasificacion": round(
                    float((yhat_multi[sel] == i).mean()), 4),
                "registros": int(sel.sum()),
            }

    # KDDTest-21: se excluye el nivel de dificultad 21 (verificado: 11,850 filas).
    sel21 = test["difficulty"].to_numpy() < 21
    kdd21 = {
        "filas": int(sel21.sum()),
        "criterio": "dificultad < 21 (se excluye el nivel 21)",
        "binario": _bloque_binario(ybin[sel21], yhat_bin[sel21], proba[sel21]),
        "multiclase": _bloque_multiclase(ymulti[sel21], yhat_multi[sel21]),
    }

    iforest = modelos["iforest"]
    scores = iforest.score_samples(X)
    auc_if = float(roc_auc_score(ybin, -scores))
    k = max(1, int(0.10 * len(ybin)))
    recall10 = float(ybin[np.argsort(scores)[:k]].mean())

    metricas = {
        "version_motor": md["version"],
        "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "modelo_produccion": {
            "nombre": "RandomForest",
            "cabezas": ["binaria normal/ataque", "multiclase de 5 clases"],
            "umbral_decision": umbral,
            "clases": CLASSES,
            "verificacion_integridad": modelos["manifiesto"]["ok"],
        },
        "binario_kddtest": binario,
        "multiclase_kddtest": multiclase,
        "kddtest21": kdd21,
        "recall_por_familia": recall_familia,
        "iforest": {
            "auc_roc": round(auc_if, 4),
            "recall_ataques_top10_por_ciento": round(recall10, 4),
            "nota": "no supervisado, entrenado solo con tráfico normal; "
                    "no decide la etiqueta, ordena rareza",
        },
        "holdout_entrenamiento": {
            "macro_f1_binario": md["macro_f1_binario_holdout"],
            "macro_f1_multiclase": md["macro_f1_multiclase_holdout"],
            "weighted_f1_multiclase": md["weighted_f1_multiclase_holdout"],
            "nota": "misma distribución del entrenamiento; NO es una prueba "
                    "independiente y no debe citarse como cumplimiento de PERF-003",
        },
        "latencia": _latencia(modelos, test),
        "tiempos_entrenamiento_segundos": md["tiempos_entrenamiento_segundos"],
        "comparativa_modelos": md["comparativa"],
    }

    METRICS.write_text(json.dumps(metricas, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"metrics.json escrito ({len(json.dumps(metricas))} bytes)")
    print(f"binario macro-F1={binario['macro_f1']}  AUC={binario['auc_roc']}")
    print(f"multiclase macro-F1={multiclase['macro_f1']} "
          f"weighted-F1={multiclase['weighted_f1']}")

    _escribir_informe(metricas)


def _tabla(filas: list[tuple[str, object]]) -> str:
    out = ["| Métrica | Valor |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in filas]
    return "\n".join(out)


def _escribir_informe(m: dict) -> None:
    b = m["binario_kddtest"]
    mc = m["multiclase_kddtest"]
    k21 = m["kddtest21"]
    lineas = [
        "# INFORME_METRICAS.md",
        "",
        "Resultados del motor de detección de Red Centinela. Todas las cifras "
        "de este documento salen de `motor/models/metrics.json`, generado por "
        "`python -m motor.evaluate` el " + m["generado"] + ". Si una cifra de "
        "otro documento no coincide con esta tabla, la de aquí es la que vale.",
        "",
        "## 1. Qué se mide y con qué datos",
        "",
        "El motor tiene dos cabezas y se reportan por separado:",
        "",
        "- **Binaria**: normal contra ataque, sobre los 22,544 registros de KDDTest+.",
        "- **Multiclase**: normal, dos, probe, r2l y u2r, sobre el mismo conjunto.",
        "",
        "KDDTest+ contiene familias de ataque que no aparecen en KDDTrain+. Eso "
        "hace que el rendimiento en prueba sea mucho menor que en entrenamiento, "
        "y es una propiedad conocida del dataset, no un defecto del modelo.",
        "",
        "## 2. Resultado binario en KDDTest+",
        "",
        _tabla([
            ("Exactitud", b["accuracy"]),
            ("Macro-F1", b["macro_f1"]),
            ("Weighted-F1", b["weighted_f1"]),
            ("Precisión de ataque", b["precision_ataque"]),
            ("Recall de ataque", b["recall_ataque"]),
            ("AUC-ROC", b["auc_roc"]),
            ("Registros", b["filas"]),
            ("Ataques reales", b["ataques_reales"]),
        ]),
        "",
        f"Matriz de confusión (filas normal, ataque): {b['matriz_confusion']}",
        "",
        "## 3. Resultado multiclase en KDDTest+",
        "",
        "| Clase | Precisión | Recall | F1 | Soporte |",
        "|---|---|---|---|---|",
    ]
    for clase, v in mc["por_clase"].items():
        lineas.append(
            f"| {clase} | {v['precision']} | {v['recall']} | {v['f1']} | {v['soporte']} |"
        )
    lineas += [
        "",
        f"Macro-F1 {mc['macro_f1']}, weighted-F1 {mc['weighted_f1']}, "
        f"exactitud {mc['accuracy']} sobre {mc['filas']} registros.",
        "",
        "Las clases r2l y u2r tienen soporte pequeño y recall bajo. No es un "
        "error de implementación: son los ataques con menos ejemplos en "
        "entrenamiento (995 y 52 registros) y en prueba aparecen variantes "
        "que no existen en el conjunto de entrenamiento.",
        "",
        "## 4. KDDTest-21",
        "",
        "Subconjunto de KDDTest+ que excluye el nivel de dificultad 21: 11,850 de "
        "los 22,544 registros. Es el conjunto que la literatura usa para medir "
        "ataques conocidos y separar el efecto de las variantes nuevas.",
        "",
        _tabla([
            ("Registros", k21["filas"]),
            ("Macro-F1 binario", k21["binario"]["macro_f1"]),
            ("Exactitud binaria", k21["binario"]["accuracy"]),
            ("Macro-F1 multiclase", k21["multiclase"]["macro_f1"]),
            ("Weighted-F1 multiclase", k21["multiclase"]["weighted_f1"]),
        ]),
        "",
        "## 5. Recall por familia",
        "",
        "| Familia | Registros | Recall detección (ataque o no) | Recall clasificación (familia correcta) |",
        "|---|---|---|---|",
    ]
    for clase, v in m["recall_por_familia"].items():
        lineas.append(
            f"| {clase} | {v['registros']} | {v['recall_deteccion']} | "
            f"{v['recall_clasificacion']} |"
        )
    lineas += [
        "",
        "## 6. Isolation Forest",
        "",
        _tabla([
            ("AUC-ROC", m["iforest"]["auc_roc"]),
            ("Recall de ataques en el 10 por ciento más anómalo",
             m["iforest"]["recall_ataques_top10_por_ciento"]),
        ]),
        "",
        "Es apoyo no supervisado: no decide la etiqueta. Sirve para señalar "
        "tráfico raro aunque se parezca a algo ya visto.",
        "",
        "## 7. Holdout de entrenamiento",
        "",
        "| Métrica en holdout | Valor |",
        "|---|---|",
        f"| Macro-F1 binario | {m['holdout_entrenamiento']['macro_f1_binario']} |",
        f"| Macro-F1 multiclase | {m['holdout_entrenamiento']['macro_f1_multiclase']} |",
        f"| Weighted-F1 multiclase | {m['holdout_entrenamiento']['weighted_f1_multiclase']} |",
        "",
        "Estas cifras son altas porque el holdout sale de la misma distribución "
        "del entrenamiento. Se publican para comparar contra KDDTest+, no como "
        "prueba de generalización.",
        "",
        "## 8. Latencia y tiempos",
        "",
        _tabla([
            ("Milisegundos por fila suelta", m["latencia"]["ms_por_fila_sola"]),
            ("Milisegundos por fila en lote de 500",
             m["latencia"]["ms_por_fila_en_lote_500"]),
            ("Segundos de entrenamiento del RF binario",
             m["tiempos_entrenamiento_segundos"]["rf_binario"]),
            ("Segundos de entrenamiento del RF multiclase",
             m["tiempos_entrenamiento_segundos"]["rf_multiclase"]),
            ("Segundos de entrenamiento del Isolation Forest",
             m["tiempos_entrenamiento_segundos"]["iforest"]),
        ]),
        "",
        "## 9. Comparativa de modelos (no desplegados)",
        "",
        "| Modelo | Filas de entrenamiento | Macro-F1 binario | Exactitud | Segundos |",
        "|---|---|---|---|---|",
    ]
    for c in m["comparativa_modelos"]:
        lineas.append(
            f"| {c['modelo']} | {c['filas_entrenamiento']} | {c['macro_f1_binario']} | "
            f"{c['accuracy']} | {c['segundos_entrenamiento']} |"
        )
    lineas += [
        "",
        "LinearSVC y KNN se midieron sobre una submuestra de 25,000 filas y una "
        "muestra de evaluación de 8,000. KNN guarda todos los vectores de "
        "entrenamiento: 62.5 MB en disco y memoria proporcional en ejecución, "
        "inviable en el plan gratuito. Por eso el modelo desplegado es el "
        "Random Forest.",
        "",
        "## 10. Limitaciones que hay que decir en voz alta",
        "",
        "- Los datos son de 1999. Un modelo entrenado con ellos describe ataques "
        "de hace veinticinco años.",
        "- KDDTest+ incluye ataques que no están en entrenamiento. El recall de "
        "r2l es el más castigado y no se arregla con hiperparámetros.",
        "- El umbral de decisión se calibró sobre el holdout del entrenamiento. "
        "En KDDTest+ el rendimiento óptimo del umbral sería otro; ajustarlo "
        "aquí sería hacer trampa, así que no se hizo.",
        "- La métrica de referencia del proyecto (PERF-003) pedía un macro-F1 "
        "mayor o igual a 0.90 sobre KDDTest+. Con estos datos y esta literatura "
        "no es alcanzable; ver SOLICITUD_CAMBIO_PERF-003.md.",
        "",
        "Documento generado automáticamente desde metrics.json. Redacción "
        "asistida por inteligencia artificial; las cifras son salida de "
        "`motor.evaluate`, no estimaciones.",
    ]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "INFORME_METRICAS.md").write_text("\n".join(lineas) + "\n",
                                              encoding="utf-8")
    print("docs/INFORME_METRICAS.md escrito")


if __name__ == "__main__":
    main()
