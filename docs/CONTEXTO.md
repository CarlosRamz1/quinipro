# QuiniPro — Contexto completo del proyecto

> Versión pública del documento de contexto (sin datos de infraestructura). Última actualización: 26/11/2026.
> Reglas del juego y permisos al detalle: `docs/REGLAS.md`.

## 1. Qué es y por qué

App de **quinielas de fútbol** para grupos (empezó para la oficina de Carlos; debe soportar muchos grupos y
cientos de personas). Reemplaza los papelitos: picks en el celular, cierre automático al pitazo, tabla en vivo
y resultados que llegan solos.

- **Nombre:** QuiniPro (logo: letras "QP" en Kanit ExtraBold Italic, negro sobre verde lima).
  Nombres descartados: Pitazo (albur), Quiniela Pro (ya existe en App Store).
- **No se cobra ni se maneja dinero.** La app solo muestra quién pagó (lo marca el admin). Decisión firme:
  cobrar comisión del pozo implicaría permisos de SEGOB y obligaciones antilavado.
- **Objetivo de calidad:** diseño y experiencia "para ganar un concurso de UI/UX". Moderno, sencillo, oscuro.
- **Dueño:** Carlos Ramírez (súper admin). Empresa paraguas: Automata (automataia.net).

## 2. Estado actual (en producción)

- **URL:** https://quinipro.automataia.net (PWA instalable; Carlos ya la tiene instalada).
- **Código:** https://github.com/CarlosRamz1/quinipro (rama `main`) y copia local en
  `C:\Users\carl-\OneDrive\Documentos\AUTOMATA\QUINIELA`.
- **Diseño de referencia:** lienzo de Claude Design "Quiniela · Diseño de pantallas"
  (https://claude.ai/artifact/C6WTV2xMZxZMv7gjBo2puC): Entrada, Jornada, Partido en vivo, Tabla, Admin y logo.
- **Pruebas:** 26 automáticas (`python -m unittest -v`), incluyen datos reales de ESPN del 26/11/2026.

### Funciona hoy
- Entrada por **enlace de invitación** + nombre (sin contraseñas; sesión con token, en BD solo el hash).
- **Jornada:** botones Local / Empate / Visita, se guarda solo; cada partido se **bloquea a su pitazo**;
  aviso de "cierra en X min"; **partido estelar** con marcador para desempate; aviso "¡Quiniela completa!";
  botón "Listo".
- **Picks revelados** solo después del pitazo (ni admins los ven antes; lo garantiza el servidor).
- **Tabla en vivo** (Server-Sent Events): podio, flechas sube/baja, buscador, tu lugar fijo abajo.
- **Inicio:** todas las quinielas activas de todos tus grupos (varias a la vez), con picks faltantes.
- **Admin del grupo:** armar quiniela (varias ligas, estrella = estelar), pagos con filtros y "marcar todos",
  copiar/cambiar invitación, miembros y roles, elegir qué quiniela administrar, zona de borrado.
- **Súper admin:** enlaces de un solo uso para que alguien cree grupo, corregir marcadores "por revisar",
  ver y borrar cualquier grupo.
- **Instalar en mi celular:** detecta Android / iPhone Safari / iPhone en otro navegador / computadora y
  muestra pasos con dibujitos; tarjeta en la Jornada que se puede posponer 7 días.
- **Barra de navegación flotante** tipo cápsula con efecto vidrio; la sección activa es una píldora lima.

## 3. Reglas clave (resumen)

- L/E/V, 1 punto por acierto, cuenta el **resultado a 90'** (prórroga y penales no).
- Desempate: marcador exacto del estelar → menor distancia de goles → comparten lugar.
- Pospuesto/suspendido/cancelado = **anulado para todos**.
- Roles: **súper admin** (Carlos; único que corrige marcadores, porque los partidos son compartidos entre
  grupos, y único que autoriza crear grupos) · **dueño** (quien crea el grupo) · **co-admin** (lo nombra el
  dueño; no borra ni cambia roles) · **participante**. Un grupo nunca se queda sin dueño.

## 4. Arquitectura

```
robot/      Python puro (sin dependencias)
  proveedores/espn.py         fuente principal: JSON público de ESPN, gratis, sin llave (no oficial)
  proveedores/apifootball.py  respaldo opcional (plan gratis 100/día, variable API_FOOTBALL_KEY)
  explorador.py               cada 6 h: revisa las 13 ligas del catálogo, guarda partidos, marca activas
  main.py                     24/7: con partidos en juego consulta cada 60 s; si no, duerme hasta el siguiente
  puntuacion.py               reglas puras (puntos, desempate, bloqueo)
  db.py / schema.sql          SQLite (WAL); tabla de posiciones precalculada con posición anterior
  catalogo.py                 ligas: mex.1, mex.2, eng.1, esp.1, ita.1, ger.1, fra.1, usa.1,
                              uefa.champions, uefa.europa, concacaf.champions, conmebol.libertadores, fifa.world
app/        FastAPI: main.py (API + sirve la PWA), admin.py (comandos), seguridad.py (tokens)
web/        PWA sin frameworks: index.html, app.js (rutas #/...), estilos.css, sw.js, manifest, iconos
tests/      unittest (robot + API)
```

Endpoints principales: `/api/unirse`, `/api/yo`, `/api/grupos/...`, `/api/quinielas/{id}` (+ `/picks`,
`/desempate`, `/tabla`, `/partidos/{pid}`, `/pagos`, `/eventos` SSE), `/api/super/...`. Documentación
automática en `/api/docs`.

## 5. Infraestructura

Producción corre en un VPS con Docker (proyecto `quinipro`: web, robot y respaldo diario) detrás de un proxy
con HTTPS automático. El código se descarga de este repositorio por commit al arrancar los contenedores.
Los datos del servidor, credenciales y el procedimiento de despliegue están en el **documento privado de
contexto** (proyecto "Quiniela" de Claude y carpeta local de Carlos), no en este repositorio.

### Local (Windows)
`iniciar.bat` (instala, arranca robot + app, abre localhost:8000) y `admin.bat super|codigo|enlace|demo`.
La base local va en `%LOCALAPPDATA%\QuiniPro\quiniela.db` (fuera de OneDrive a propósito).

## 6. Lecciones aprendidas (no repetir errores)

- ESPN responde **403 si el User-Agent contiene "Bot"** → se usa `quiniela/1.0`.
- El scoreboard de ESPN **no trae goles por tiempo**; para prórroga se consulta
  `/summary?event=ID` (`header.competitions[0].competitors[].linescores[].displayValue`).
  Si aun así no hay desglose, el partido queda "por revisar" para el súper admin.
- ESPN agrupa los días en horario de EE. UU.: se consultan el día del partido y el anterior.
- SQLite con FastAPI: `check_same_thread=False` (la conexión se abre y usa en hilos distintos).
- SQLite dentro de OneDrive da errores de disco: usar `QUINIELA_DB` fuera de OneDrive.
- El Docker Manager de Hostinger **no construye imágenes** desde `build:`; por eso el compose usa una imagen
  base y baja el código al arrancar.
- Al copiar archivos a la laptop de Carlos, verificar con md5 (una copia llegó vieja una vez).
- Probar la UI con Playwright + Chrome en el contenedor; las fuentes y escudos externos no cargan ahí (normal).

## 7. Diseño (sistema visual)

- Fondo `#0A0D12`, superficie `#12171F` / `#1A212B`, líneas `#232B36` / `#2A3340`.
- Texto `#F2F5F8`, secundario `#C9D2DC`, gris `#8B97A6`.
- Acento **lima `#D4FF3A`** (único acento), dorado estelar `#FFC53D`, naranja en vivo `#FF7A50`.
- Tipografía: Inter (texto), Space Grotesk (títulos y números), **Kanit 800 itálica solo para la marca**.
- Botones ≥ 44 px, sin emojis en la interfaz (íconos SVG de trazo), escudos de ESPN con siglas de respaldo.

## 8. Pendientes / ideas (en orden sugerido)

1. **Notificaciones push** ("cierra en 15 min", "caíste al 6°"); en iPhone requiere app instalada e iOS 16.4+.
2. **Chat de pique ("trash talk")** por grupo con avisos automáticos de cambios en la tabla. Idea que venía de
   una conversación previa con Gemini; Carlos pidió dejarlo para después.
3. Reglas opcionales por quiniela: comodín x2, marcador exacto (3/1), dobles estilo Progol.
4. **APK de Android** (Trusted Web Activity) con Android Studio; opcional, la PWA ya se instala.
5. Fútbol americano (ESPN tiene NFL con el mismo formato; en NFL casi no hay empates → solo L/V).
6. Logo definitivo (Carlos lo dejó con el provisional QP en Kanit itálica).
