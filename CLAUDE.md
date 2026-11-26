# QuiniPro — instrucciones para Claude

Lee primero `docs/CONTEXTO.md` (qué es, estado, arquitectura, infraestructura, lecciones y pendientes)
y `docs/REGLAS.md` (reglas del juego y permisos).

Reglas de trabajo:
- Responde en español (México). El dueño es Carlos Ramírez.
- Antes de entregar: `python -m unittest -v` debe pasar. Si cambias la interfaz, sube `VERSION` en `web/sw.js`
  y revisa las pantallas con Playwright a 390×844.
- Nunca escribas tokens, contraseñas ni la llave de súper admin en el repositorio.
- Producción: proyecto Docker `quinipro` en el VPS de Carlos. El procedimiento de despliegue y los datos
  del servidor están en el documento privado de contexto (no en este repo). En el VPS corren otros
  proyectos: no los toques sin permiso explícito.
- La app no maneja dinero; nadie ve picks ajenos antes del pitazo; los partidos son compartidos entre grupos
  (solo el súper admin los corrige).
- Mantén el sistema visual: fondo oscuro, acento lima #D4FF3A, Inter / Space Grotesk, marca en Kanit itálica,
  sin emojis en la interfaz, botones de al menos 44 px.
- Si actualizas el estado del proyecto, actualiza también `docs/CONTEXTO.md`.
