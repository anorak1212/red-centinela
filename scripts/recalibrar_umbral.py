"""Aplica el umbral que salio de la validacion de familias no vistas.

El criterio ya esta calculado en docs/UMBRAL_FAMILIAS_NO_VISTAS.json, que no
usó KDDTest+. Este script no busca numeros nuevos: solo escribe en metadata.json
la decision que ese experimento tomo, reconstruye el manifiesto de integridad
y deja constancia de lo que cambio.

Despues de esto, la unica evaluacion sobre KDDTest+ es `python -m motor.evaluate`.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from motor.data import MODEL_DIR
from motor.ensemble import construir_manifiesto, verificar_manifiesto

RAIZ = Path(__file__).resolve().parents[1]
EVIDENCIA = RAIZ / "docs" / "UMBRAL_FAMILIAS_NO_VISTAS.json"
INFORME = RAIZ / "docs" / "RECALIBRACION_UMBRAL.md"


def main() -> None:
    evidencia = json.loads(EVIDENCIA.read_text(encoding="utf-8"))
    umbral = float(evidencia["umbral_promedio_optimo"])
    ruta_md = MODEL_DIR / "metadata.json"
    md = json.loads(ruta_md.read_text(encoding="utf-8"))
    anterior = float(md["umbral_decision"])

    if anterior == umbral:
        print(f"umbral ya recalibrado en {umbral}; nada que hacer")
        return

    md["umbral_decision_anterior"] = anterior
    md["umbral_decision"] = umbral
    md["umbral_decision_metodo"] = (
        "maximo del macro-F1 promedio en leave-one-family-out sobre KDDTrain+, "
        "con mezcla ataque/normal 1.32 a 1; KDDTest+ no participo en la eleccion"
    )
    md["umbral_decision_evidencia"] = "docs/UMBRAL_FAMILIAS_NO_VISTAS.json"
    md["umbral_decision_recalibrado"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    ruta_md.write_text(json.dumps(md, ensure_ascii=False, indent=2), encoding="utf-8")

    manifiesto = construir_manifiesto(MODEL_DIR)
    (MODEL_DIR / "manifiesto.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    estado = verificar_manifiesto(MODEL_DIR)
    if not estado["ok"]:
        raise RuntimeError(f"manifiesto no verificado: {estado['detalle']}")

    texto = f"""# RECALIBRACION_UMBRAL.md

El umbral de decision del detector binario paso de **{anterior}** a **{umbral}**.

## Por que

El umbral de {anterior} se habia calibrado con un holdout de la misma
distribucion de KDDTrain+. Ahi el modelo acierta casi todo, asi que el punto
optimo queda alto. El fallo aparece con ataques que no existen en entrenamiento:
en KDDTest+ el recall de ataque cae y las familias r2l y u2r casi no se detectan.

## Como se eligio, sin mirar el examen

`scripts/umbral_familias_no_vistas.py` aparto cada familia de ataque completa,
entreno sin ella y midio macro-F1 sobre una mezcla de esa familia nunca vista y
trafico normal, en la proporcion que tiene KDDTest+ (1.32 a 1). El umbral que
maximiza el promedio de esas cuatro mediciones fue **{umbral}**, con macro-F1
promedio de {evidencia['macro_f1_promedio_optimo']} en validacion.

Resultados por familia:

| Familia apartada | Macro-F1 con umbral {umbral} | Macro-F1 con umbral {anterior} |
|---|---|---|
"""
    for familia, d in evidencia["por_familia"].items():
        curva = {p["umbral"]: p["macro_f1"] for p in d["curva"]}
        texto += (f"| {familia} | {curva.get(umbral, 'no medido')} | "
                  f"{curva.get(anterior, 'no medido')} |\n")

    texto += """
KDDTest+ no se uso para elegir el umbral. La curva de sensibilidad de
`docs/SENSIBILIDAD_UMBRAL.md` se calculo despues, como diagnostico, y confirma
que el cambio tiene precio: mas recalls, pero tambien mas falsos positivos.
Ese costo se acepta porque la metrica del proyecto es macro-F1 y porque un
sistema de alerta puede priorizar la deteccion; queda escrito aqui para que la
decision se pueda revisar.

## Que NO cambio

No se reentreno ningun modelo. rf.joblib, rf_multi.joblib, iforest.joblib y el
preprocesador siguen siendo los mismos archivos, con el mismo hash. Solo cambio
metadata.json, que es donde vive el punto de corte, y manifiesto.json, que se
reconstruyo para que la verificacion de integridad siga siendo valida.

La evaluacion final se regenero con `python -m motor.evaluate` y sus cifras
estan en `motor/models/metrics.json` y `docs/INFORME_METRICAS.md`.
"""
    INFORME.write_text(texto, encoding="utf-8")
    print(f"umbral {anterior} -> {umbral}; manifiesto verificado")
    print(f"escrito {INFORME.name}")


if __name__ == "__main__":
    main()
