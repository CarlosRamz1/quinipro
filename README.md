# QuiniPro

Quinielas de fútbol con tu grupo: picks L/E/V que se bloquean al pitazo, partido estelar para desempatar,
tabla en vivo y resultados automáticos (ESPN, respaldo API-Football). La app **no maneja dinero**.

## Probar en tu laptop (Windows)

1. Doble clic en **`iniciar.bat`**. Instala lo necesario, arranca el robot de datos (otra ventana)
   y la app, y abre `http://localhost:8000`.
2. La primera vez, en otra terminal en esta carpeta:
   ```
   admin.bat super "Carlos Ramírez"
   ```
   Te da **tu enlace personal de súper admin**. Ábrelo en el navegador (y guárdalo: es tu llave).
3. Para tener algo que jugar de inmediato:
   ```
   admin.bat demo
   ```
   Crea el grupo "Los Compas" con los próximos partidos reales y te da el enlace de invitación.

Desde otro celular en la **misma red WiFi** puedes entrar con `http://<IP-de-tu-laptop>:8000`
(la instalación como app y las notificaciones requieren HTTPS: eso llega en el VPS).

La base de datos queda en `%LOCALAPPDATA%\QuiniPro\quiniela.db` (fuera de OneDrive a propósito).

## Cómo se usa

| Quién | Qué hace |
|---|---|
| **Tú (súper admin)** | Generas enlaces para que alguien cree un grupo (`Perfil → Panel súper admin`), corriges marcadores "por revisar" (afectan a todos los grupos) y ves todos los grupos. |
| **Dueño del grupo** | Arma quinielas (`Admin → Armar siguiente`), elige el estelar, comparte la invitación, marca pagos, nombra co-admins, puede transferir el grupo. |
| **Co-admin** | Igual que el dueño, menos quitarle permisos al dueño o transferir. |
| **Participante** | Llena sus picks y ve la tabla. |

Nadie, ni los admins, ve los picks ajenos antes del pitazo. Reglas completas: `docs/REGLAS.md`.

## Comandos

```
python -m unittest -v              # 25 pruebas (robot + API)
python probar.py --todas           # qué ligas están activas, con datos reales
python probar.py --demo            # simulación de puntuación sin internet
python -m robot.main               # robot 24/7
python -m uvicorn app.main:app     # servidor (API + PWA)
python -m app.admin --help         # súper admin, códigos de grupo, enlaces, demo
```
Variables: `QUINIELA_DB` (ruta de la base), `QUINIPRO_URL` (dirección pública para los enlaces),
`API_FOOTBALL_KEY` (respaldo opcional).

## Estructura

```
app/main.py          API (FastAPI) + sirve la PWA
app/admin.py         comandos de administración
app/seguridad.py     tokens sin contraseña (solo se guarda el hash)
web/                 PWA: index.html, app.js, estilos.css, sw.js, manifest, iconos
robot/               datos: ESPN/API-Football, explorador, vigilante 24/7, puntuación, esquema SQLite
tests/               pruebas automáticas (incluye datos reales de ESPN del 26/11/2026)
docs/REGLAS.md       reglas del juego y permisos
iniciar.bat          arranque local con doble clic
admin.bat            comandos de admin con la misma base que iniciar.bat
```

## Pendiente (siguientes fases)

- Subir al VPS con HTTPS (Caddy) y servicios que se reinician solos.
- Notificaciones push ("cierra en 15 min", "caíste al 6°").
- APK de Android (TWA) con Android Studio.
