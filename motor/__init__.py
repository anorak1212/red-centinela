"""Motor de detección de Red Centinela.

Pipeline de detección de tráfico de red anómalo sobre NSL-KDD:
carga, preprocesamiento, entrenamiento (RF, SVM, KNN, Isolation Forest),
evaluación (macro-F1, AUC) y serialización con joblib.

Uso:
    python -m motor.train      # entrena y guarda modelos en motor/models/
    python -m motor.evaluate   # evalúa sobre KDDTest+ y guarda métricas
"""

__version__ = "0.2.0"