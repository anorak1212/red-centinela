# SENSIBILIDAD_UMBRAL.md

Diagnóstico, no calibración. La curva se midió una sola vez sobre KDDTest+ con los artefactos en producción y **no se usó para elegir el umbral**: ese se había fijado antes con validación de familias no vistas sobre KDDTrain+ (`docs/UMBRAL_FAMILIAS_NO_VISTAS.json`). Si aquí se eligiera el mejor punto de esta tabla, la cifra del informe dejaría de ser una prueba y pasaría a ser un ajuste al examen.

## Qué se midió

- Umbral desplegado: 0.01
- Mejor macro-F1 de toda la curva: 0.927 en umbral 0.05
- Diferencia entre el umbral desplegado y el mejor punto: 0.0019

## Curva completa

| Umbral | Macro-F1 | Precisión de ataque | Recall de ataque | Falsos positivos | Falsos negativos |
|---|---|---|---|---|---|
| 0.01 **(desplegado)** | 0.9251 | 0.8986 | 0.9845 | 1,426 | 199 |
| 0.05 | 0.9270 | 0.9207 | 0.9576 | 1,058 | 544 |
| 0.10 | 0.8956 | 0.9239 | 0.8928 | 944 | 1,376 |
| 0.15 | 0.8739 | 0.9252 | 0.8491 | 881 | 1,937 |
| 0.20 | 0.8535 | 0.9353 | 0.7986 | 709 | 2,584 |
| 0.25 | 0.8499 | 0.9672 | 0.7623 | 332 | 3,051 |
| 0.30 | 0.8316 | 0.9683 | 0.7280 | 306 | 3,491 |
| 0.35 | 0.8192 | 0.9685 | 0.7054 | 294 | 3,781 |
| 0.40 | 0.8086 | 0.9687 | 0.6862 | 285 | 4,027 |
| 0.45 | 0.7925 | 0.9690 | 0.6572 | 270 | 4,399 |
| 0.50 | 0.7697 | 0.9677 | 0.6179 | 265 | 4,904 |
| 0.55 | 0.7568 | 0.9672 | 0.5957 | 259 | 5,188 |
| 0.60 | 0.7513 | 0.9675 | 0.5860 | 253 | 5,313 |
| 0.65 | 0.7485 | 0.9677 | 0.5810 | 249 | 5,377 |
| 0.70 | 0.7451 | 0.9675 | 0.5754 | 248 | 5,449 |
| 0.75 | 0.7377 | 0.9683 | 0.5622 | 236 | 5,618 |
| 0.80 | 0.7314 | 0.9683 | 0.5515 | 232 | 5,755 |
| 0.85 | 0.7220 | 0.9678 | 0.5360 | 229 | 5,954 |
| 0.90 | 0.7145 | 0.9705 | 0.5221 | 204 | 6,133 |
| 0.95 | 0.6960 | 0.9728 | 0.4907 | 176 | 6,536 |

## Lectura

La curva confirma que con un punto de corte más bajo se alcanza macro-F1 0.927, por encima del 0.90 que pedía PERF-003. Ese punto no se eligió mirando esta tabla: salió del protocolo de familias no vistas (`docs/UMBRAL_FAMILIAS_NO_VISTAS.json`), que no usa KDDTest+. El costo está a la vista: el recall sube de 0.9845 a 0.9576, pero los falsos positivos pasan de 1,426 a 1,058. En un IDS real ese caudal de alertas tiene costo; aquí se reporta para que la decisión no se tome a escondidas.

Generado por `python -m scripts.sensibilidad_umbral` a partir de `motor/models/`.
