# Tablero (M4)

Panel de monitoreo de Red Centinela, en Streamlit. No carga modelos ni abre la
base de datos: consume la API REST (diseño del entregado 14). Eso lo deja en tres
dependencias y permite apuntarlo a local o a producción cambiando una URL.

## Vistas

| Vista | Qué hace |
|---|---|
| Resumen | Banda con las cinco cifras del servicio, estado verificado, actividad por hora, composición por clase, últimas predicciones y el estado de alertas, artefactos y criterio de rendimiento |
| Analizar | Conexión individual con las 41 características editables en JSON, o carga de un CSV de hasta 2,000 filas; si el archivo trae columna `family`, compara la predicción con la verdad y separa detección de clasificación |
| Historial | De 100 a 1,000 predicciones con filtros por origen y clase, serie de p(ataque) contra el umbral, distribuciones, tabla de 60 registros, vista de las características y descarga en CSV |
| Modelo y métricas | Siete secciones: cabeza binaria con matriz de confusión, cinco clases con su matriz, detección contra clasificación, KDDTest-21, comparativa de modelos, holdout e Isolation Forest, costo computacional |
| Sistema | Los seis módulos M1-M6, los ocho endpoints y la tabla de criterios con la cifra medida y el veredicto, incluidos los que no se cumplen |
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

Veintidós pruebas: contrato del cliente, validación de CSV, montaje de las
seis vistas con `AppTest` contra una API inexistente y dos pruebas de los
botones (reverificación del manifiesto y ausencia del botón de Telegram cuando
no hay credenciales). Lo que se verifica es que el tablero explique el fallo en
pantalla en vez de reventar con una traza, y que cada botón haga algo real.
