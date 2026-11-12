# Tablero (M4)

Panel de monitoreo de Red Centinela, en Streamlit. No carga modelos ni abre la
base de datos: consume la API REST (diseño del entregado 14). Eso lo deja en tres
dependencias y permite apuntarlo a local o a producción cambiando una URL.

## Vistas

| Vista | Qué hace |
|---|---|
| Resumen | Banda con las cinco cifras del servicio, estado verificado, alertas, artefactos y criterio de rendimiento, actividad por hora con actualización automática opcional (15 s), postura reciente (últimas 50), composición por clase y últimas predicciones |
| Analizar | Conexión individual con formulario guiado (campos clave) o las 41 características en JSON, o carga de un CSV de hasta 2,000 filas; descarga de plantilla y muestra; si el archivo trae `family`, compara contra la verdad y dibuja la matriz de confusión del lote |
| Historial | De 100 a 500 predicciones (límite de `/history`) con filtros por origen, clase, rango de p(ataque), ID y alerta; serie contra el umbral, distribuciones, simulador local de umbral, tabla de 60 registros y descarga en CSV o JSON |
| Modelo y métricas | Siete secciones: cabeza binaria con matriz de confusión (KDDTest+ o KDDTest-21), cinco clases con su matriz, detección contra clasificación, KDDTest-21, comparativa de modelos, holdout e Isolation Forest, costo computacional |
| Sistema | Los seis módulos M1-M6, la tabla de criterios con la cifra medida y el veredicto, y los ocho endpoints con verificación en vivo de los GET (código y milisegundos) |
| Ayuda | Cómo se ejecuta, contrato de la API, variables de entorno, glosario con búsqueda y código de color |
| Configuración (ajustes) | Tema claro u oscuro, color de acento, densidad, animaciones, intervalo de actualización, registros de Historial y tamaño de lote; restablecer y exportar en JSON. Vale para la sesión del navegador |

En la barra lateral hay dos interruptores para la defensa:

- **Recorrido de la demo:** el guion en siete pasos, arriba de cada vista, con qué
  mostrar y qué decir. "Siguiente" cambia de vista solo.
- **Modo presentación:** letra más grande y sin notas secundarias, para proyectar.

La navegación se agrupa en Operación (Resumen, Analizar, Historial), Modelo,
Proyecto (Sistema, Ayuda) y Ajustes (Configuración, que no es una vista de
monitoreo sino la pantalla de preferencias). Si la API responde sin modelos (modo degradado), las
vistas lo explican y los botones de predicción se deshabilitan.

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
  herramientas, sin detalles de error en pantalla) y `tablero/ui/estilos.py`.
  Tipografía Geist y Geist Mono. Paleta: acento elegible (azul centinela por omisión) para marca y acciones; verde azulado para normal o
  cumplido, ámbar para umbral o atención y rojo para ataque o incumplido.

## Acceso con usuario y contraseña

El tablero pide login cuando existe la variable `REDCENTINELA_TABLERO_USUARIOS`
(en Streamlit Cloud, como clave de primer nivel en los secretos de la app). Sin
ella queda en acceso abierto y la barra lateral lo avisa.

```powershell
python -m tablero.auth          # pide la contraseña y imprime el hash
$env:REDCENTINELA_TABLERO_USUARIOS = "mateo:admin:pbkdf2_sha256$...,jurado:lector:pbkdf2_sha256$..."
streamlit run tablero/app.py
```

- `admin` puede todo. `lector` ve todas las vistas, pero Predecir, el lote y
  el mensaje de prueba de Telegram quedan deshabilitados con la explicación.
- Hash PBKDF2-SHA256 de la biblioteca estándar: sin dependencias nuevas y sin
  contraseñas en el repositorio. Se acepta `usuario:rol:contraseña` en texto
  plano para una demo rápida, y el tablero lo marca como inseguro.
- Cinco intentos fallidos bloquean el formulario 60 s en esa sesión; la sesión
  dura 8 horas. El bloqueo es por sesión del navegador, no por IP.

## Pruebas

```powershell
python -m pytest tests\test_tablero.py tests\test_auth_tablero.py tests\test_guia_tablero.py -q
```

Veintidós pruebas: contrato del cliente, validación de CSV, montaje de las
seis vistas con `AppTest` contra una API inexistente y dos pruebas de los
botones (reverificación del manifiesto y ausencia del botón de Telegram cuando
no hay credenciales). Lo que se verifica es que el tablero explique el fallo en
pantalla en vez de reventar con una traza, y que cada botón haga algo real.
