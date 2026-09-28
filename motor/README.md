# Motor ML (M1)

Pipeline completo de detección sobre NSL-KDD:

- `data.py`: carga del dataset (43 columnas oficiales), familias de ataque y etiqueta binaria.
- `preprocess.py`: one-hot de `protocol_type`, `service`, `flag` + estandarización de las 38 numéricas → matriz de 122 características.
- `train.py`: entrena RF (300 árboles), LinearSVC, KNN (7 vecinos) e Isolation Forest (solo normal) sobre todo el entrenamiento; calibra el umbral del ensamble sobre un holdout estratificado del 25 %.
- `ensemble.py`: probabilidad promedio de RF+KNN+SVM (SVM escalado a [0,1]) y decisión binaria con umbral calibrado.
- `evaluate.py`: macro-F1, AUC y recall por familia sobre KDDTest+; guarda `models/metrics.json`.
- `models/`: artefactos `joblib` + `metadata.json` + `metrics.json` (no versionados los `.joblib`, se regeneran con `python -m motor.train`).

## Flujo

```powershell
python scripts/download_nslkdd.py   # una vez
python -m motor.train               # entrena + serializa + calibra umbral
python -m motor.evaluate            # métricas sobre KDDTest+
```

## Resultados (v0.3.0)

| Métrica | Holdout train | KDDTest+ |
|---|---|---|
| macro-F1 binaria | 0.998 | 0.788 |
| AUC ROC | — | 0.965 |
| Recall DoS / Probe | — | 0.84 / 0.81 |

KDDTest+ incluye ataques no vistos en entrenamiento (r2l y u2r nuevos), por eso el recall de esas familias es bajo; es el comportamiento esperado y documentado en la literatura del dataset.