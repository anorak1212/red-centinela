# Tablero (M4)

Interfaz web de monitoreo construida con Streamlit y desplegada en Streamlit Community Cloud.

## Funciones

- Carga manual de un archivo CSV de tráfico de prueba (módulo M2, ingesta de contexto).
- Consulta del historial a través de la API (`/history`), nunca directo a la base de datos.
- Visualización de predicciones y métricas del modelo.

## Criterios

- Disponibilidad: >= 95 % en pruebas continuas, >= 99 % en el horario de la defensa (DASH-009).
- Sin autenticación en esta versión: decisión de alcance declarada como riesgo aceptado (requisito UX-014 marcado Won't, amenaza AM-01 del análisis STRIDE).

## Estado

Pendiente, corresponde al entregable E4 del cronograma.