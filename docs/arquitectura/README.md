# Arquitectura (diseño lógico)

Artefactos de diseño técnico de Red Centinela, versionados junto al código.

- `E14_Diseno_Logico_V2.json`: modelo de datos de la arquitectura (zonas Z1 a Z5, componentes, flujos de comunicación, acuerdos de nivel de servicio y seguridad). Fuente de verdad de esta carpeta.
- `E14_Diseno_Logico_V2.mmd`: el mismo diseño en Mermaid. Coherente con el entregable E13 (DFD) y con el análisis STRIDE del entregable E12.
- `E14_Diseno_Logico_V2.svg`: diagrama vectorial renderizado desde el JSON.

Notas de la versión 2: P3 (servicio de alertas) reintroducido con envío asíncrono; Neon declarado con acceso por credencial y no como red aislada; el tablero consulta la base solo por `/history`; `qos_prioridad` retirado de flujos de Internet; zonas unificadas con E12/E13.