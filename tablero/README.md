# Tablero (M4)

Panel de monitoreo de Red Centinela, en Streamlit. No carga modelos ni abre la
base de datos: consume la API REST (diseño del entregado 14). Eso lo deja en tres
dependencias y permite apuntarlo a local o a producción cambiando una URL.

## Vistas

| Vista | Qué hace |
|---|---|
| Resumen | Estado del servicio, conteos de predicciones y ataques, gráfica de probabilidad, composición por clase, estado de las alertas y reverificación de artefactos |
| Analizar | Conexión individual con las 41 características editables en JSON, o carga de un CSV de hasta 2,000 filas; si el archivo trae columna `family`, compara la predicción con la verdad |
| Historial | Últimas 50 a 500 predicciones con filtros por origen y clase, gráfica, descarga en CSV y vista de las características de un registro |
| Modelo y métricas | Cifras de KDDTest+, desglose por familia, KDDTest-21, holdout, latencia y comparativa de modelos |
| Ayuda | Cómo se ejecuta, contrato de la API, variables de entorno y qué significa cada cifra |

## Arranque

```powershell
# terminal 1: API (puerto 8000)
python -m cli serve

# terminal 2: tablero
streamlit run tablero/app.py
```

## Configuración

- `REDCENTINELA_API`: URL de la API. Por omisión `http://127.0.0.1:8000`. También
  se puede cambiar en la barra lateral sin reiniciar.
- En Streamlit Cloud, la variable va en los secretos de la app o en las variables
  de entorno del panel; el token de Telegram nunca se configura aquí, vive en la
  API.
- Tema y comportamiento visual: `.streamlit/config.toml` (claro, sin barra de
  herramientas, sin detalles de error en pantalla).

## Pruebas

```powershell
python -m pytest tests\test_tablero.py -q
```

Veintiuna pruebas: contrato del cliente, validación de CSV, montaje de las
cinco vistas con `AppTest` contra una API inexistente y dos pruebas de los
botones (reverificación del manifiesto y ausencia del botón de Telegram cuando
no hay credenciales). Lo que se verifica es que el tablero explique el fallo en
pantalla en vez de reventar con una traza, y que cada botón haga algo real.
