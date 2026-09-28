# Tablero (M4)

Panel de monitoreo de Red Centinela construido con Streamlit. No carga
modelos: consume la API REST (diseño E14), por lo que primero hay que
arrancar `uvicorn api.main:app`.

## Vistas

| Pestaña | Qué hace |
|---|---|
| Predicción en vivo | Formulario con las 41 características del NSL-KDD; predice una fila y muestra etiqueta, probabilidad y progreso |
| Carga CSV por lote | Subir un CSV con las 41 columnas (igual que `datasets/sample_trafico.csv`); valida encabezado, predice hasta 2,000 filas contra `/predict/batch` y permite descargar el resultado |
| Historial | Últimas 200 predicciones: resumen, gráfica de probabilidad de ataque en el tiempo y tabla completa |

## Arranque

```powershell
# terminal 1: API (puerto por defecto 8000)
uvicorn api.main:app

# terminal 2: tablero
streamlit run tablero/app.py
```

Configuración:

- `REDCENTINELA_API` (opcional): URL de la API si no es `http://127.0.0.1:8000`.
- El botón de alertas (sidebar) llama a `alertas.telegram`; sin token configurado
  responde con motivo y no envía nada (M5, fase E5).

## Verificación

`pytest tests/test_tablero.py` valida el contrato de columnas, el parseo de
CSV (acepta el válido, rechaza encabezados incompletos) y el estado de la API
si está levantada.