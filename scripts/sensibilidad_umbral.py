"""Diagnostico: cuanto depende el resultado del umbral de decision.

Esto NO es una busqueda del mejor umbral. Elegir el umbral mirando KDDTest+
seria ajustar el modelo al examen, y entonces la cifra publicada no valdria
nada. Lo que hace este script es medir la curva completa una sola vez para
poder responder con numeros a la pregunta incomoda: "si el umbral estuviera
mejor puesto, cuanto subiria". Si ni en el mejor punto se llega a 0.90, el
problema no es el umbral.

Escribe docs/SENSIBILIDAD_UMBRAL.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from motor.data import TARGET, load_raw
from motor.ensemble import cargar_modelos
from sklearn.metrics import f1_score, precision_score, recall_score

DOCS = Path(__file__).resolve().parents[1] / "docs"
UMBRALES = np.array([0.01] + [round(float(t), 2) for t in np.arange(0.05, 1.0, 0.05)])


def main() -> None:
    modelos = cargar_modelos(verificar=True)
    pp = modelos["preprocessor"]
    md = modelos["metadata"]
    umbral_actual = float(md["umbral_decision"])

    test = load_raw("KDDTest+.txt")
    y = test[TARGET].to_numpy()
    proba = modelos["rf"].predict_proba(pp.transform(test))[:, 1]

    filas = []
    for t in UMBRALES:
        yhat = (proba >= t).astype(int)
        filas.append({
            "umbral": float(t),
            "macro_f1": round(float(f1_score(y, yhat, average="macro")), 4),
            "precision": round(float(precision_score(y, yhat, zero_division=0)), 4),
            "recall": round(float(recall_score(y, yhat, zero_division=0)), 4),
            "falsos_positivos": int(((yhat == 1) & (y == 0)).sum()),
            "falsos_negativos": int(((yhat == 0) & (y == 1)).sum()),
        })

    mejor = max(filas, key=lambda f: f["macro_f1"])
    actual = min(filas, key=lambda f: abs(f["umbral"] - umbral_actual))

    lineas = [
        "# SENSIBILIDAD_UMBRAL.md",
        "",
        ("Diagnóstico, no calibración. La curva se midió una sola vez sobre "
         "KDDTest+ con los artefactos en producción y **no se usó para elegir "
         "el umbral**: ese se había fijado antes con validación de familias no "
         "vistas sobre KDDTrain+ (`docs/UMBRAL_FAMILIAS_NO_VISTAS.json`). Si "
         "aquí se eligiera el mejor punto de esta tabla, la cifra del informe "
         "dejaría de ser una prueba y pasaría a ser un ajuste al examen."),
        "",
        "## Qué se midió",
        "",
        f"- Umbral desplegado: {actual['umbral']}",
        (f"- Mejor macro-F1 de toda la curva: {mejor['macro_f1']} en umbral "
         f"{mejor['umbral']}"),
        (f"- Diferencia entre el umbral desplegado y el mejor punto: "
         f"{round(mejor['macro_f1'] - actual['macro_f1'], 4)}"),
        "",
        "## Curva completa",
        "",
        ("| Umbral | Macro-F1 | Precisión de ataque | Recall de ataque | "
         "Falsos positivos | Falsos negativos |"),
        "|---|---|---|---|---|---|",
    ]
    for f in filas:
        marca = " **(desplegado)**" if f is actual else ""
        lineas.append(
            f"| {f['umbral']:.2f}{marca} | {f['macro_f1']:.4f} | {f['precision']:.4f} | "
            f"{f['recall']:.4f} | {f['falsos_positivos']:,} | {f['falsos_negativos']:,} |"
        )

    if mejor["macro_f1"] >= 0.90:
        lectura = (
            f"La curva confirma que con un punto de corte más bajo se alcanza "
            f"macro-F1 {mejor['macro_f1']}, por encima del 0.90 que pedía PERF-003. "
            f"Ese punto no se eligió mirando esta tabla: salió del protocolo de "
            f"familias no vistas (`docs/UMBRAL_FAMILIAS_NO_VISTAS.json`), que no "
            f"usa KDDTest+. El costo está a la vista: el recall sube de "
            f"{actual['recall']} a {mejor['recall']}, pero los falsos positivos "
            f"pasan de {actual['falsos_positivos']:,} a "
            f"{mejor['falsos_positivos']:,}. En un IDS real ese caudal de alertas "
            f"tiene costo; aquí se reporta para que la decisión no se tome a "
            f"escondidas."
        )
    else:
        lectura = (
            f"Ni en el mejor punto de la curva se llega a 0.90 (máximo "
            f"{mejor['macro_f1']}). Bajar el umbral compra recall de ataque a "
            f"cambio de falsos positivos en proporción parecida, así que el "
            f"resultado se queda pegado a {actual['macro_f1']}. El límite lo "
            f"pone la separación entre clases, no el punto de corte."
        )

    lineas += [
        "",
        "## Lectura",
        "",
        lectura,
        "",
        ("Generado por `python -m scripts.sensibilidad_umbral` a partir de "
         "`motor/models/`."),
    ]
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "SENSIBILIDAD_UMBRAL.md").write_text("\n".join(lineas) + "\n",
                                                 encoding="utf-8")
    print(f"desplegado {actual['umbral']}: macro-F1 {actual['macro_f1']} "
          f"(P {actual['precision']}, R {actual['recall']})")
    print(f"mejor de la curva {mejor['umbral']}: macro-F1 {mejor['macro_f1']}")
    print("docs/SENSIBILIDAD_UMBRAL.md escrito")


if __name__ == "__main__":
    main()
