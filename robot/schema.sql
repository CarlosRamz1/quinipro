-- Esquema de la Quiniela (SQLite). Fechas en UTC, formato ISO 8601.
PRAGMA foreign_keys = ON;

-- Ligas/torneos soportados. El explorador marca cuáles están activas.
CREATE TABLE IF NOT EXISTS competiciones (
    codigo              TEXT PRIMARY KEY,          -- código ESPN, ej. 'mex.1'
    nombre              TEXT NOT NULL,
    pais                TEXT,
    apifootball_id      INTEGER,                   -- para el respaldo
    temporada_anual     INTEGER NOT NULL DEFAULT 0,-- 1 = temporada ene-dic (MLS, Libertadores)
    habilitada          INTEGER NOT NULL DEFAULT 1,-- la ofrecemos en la app
    activa              INTEGER NOT NULL DEFAULT 0,-- tiene partidos en los próximos días
    temporada           TEXT,
    fase                TEXT,
    proximo_partido_utc TEXT,
    actualizado_utc     TEXT
);

CREATE TABLE IF NOT EXISTS partidos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    competicion         TEXT NOT NULL REFERENCES competiciones(codigo),
    id_espn             TEXT UNIQUE,
    id_apifootball      INTEGER UNIQUE,
    fuente              TEXT NOT NULL,             -- última fuente: espn | apifootball | manual
    inicio_utc          TEXT NOT NULL,
    local               TEXT NOT NULL,
    visitante           TEXT NOT NULL,
    local_abrev         TEXT,
    visitante_abrev     TEXT,
    local_logo          TEXT,
    visitante_logo      TEXT,
    estado              TEXT NOT NULL CHECK (estado IN
                          ('programado','en_juego','final','pospuesto','suspendido','cancelado')),
    minuto              TEXT,                      -- "36'", "HT", etc.
    goles_local         INTEGER,                   -- marcador mostrado
    goles_visitante     INTEGER,
    goles_local_90      INTEGER,                   -- marcador que cuenta (90')
    goles_visitante_90  INTEGER,
    revisar             INTEGER NOT NULL DEFAULT 0,-- el admin debe confirmar
    manual              INTEGER NOT NULL DEFAULT 0,-- corregido a mano: el robot no lo pisa
    actualizado_utc     TEXT
);
CREATE INDEX IF NOT EXISTS ix_partidos_inicio ON partidos(inicio_utc);
CREATE INDEX IF NOT EXISTS ix_partidos_estado ON partidos(estado);

CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    telefono        TEXT UNIQUE,
    token_hash      TEXT UNIQUE,                   -- sesión sin contraseña (se guarda solo el hash)
    es_superadmin   INTEGER NOT NULL DEFAULT 0,    -- solo se asigna desde el servidor (app.admin)
    creado_utc      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Un grupo = una oficina / grupo de amigos.
CREATE TABLE IF NOT EXISTS grupos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    codigo_invitacion   TEXT NOT NULL UNIQUE,
    creado_por          INTEGER REFERENCES usuarios(id),
    creado_utc          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS miembros (
    grupo_id    INTEGER NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rol         TEXT NOT NULL DEFAULT 'participante' CHECK (rol IN ('dueno','coadmin','participante')),
    unido_utc   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (grupo_id, usuario_id)
);

-- Códigos que el súper admin entrega para que alguien pueda crear un grupo (un solo uso).
CREATE TABLE IF NOT EXISTS codigos_grupo (
    codigo      TEXT PRIMARY KEY,
    nota        TEXT,
    creado_utc  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    usado_por   INTEGER REFERENCES usuarios(id),
    usado_utc   TEXT
);

-- Registro de cambios de permisos y acciones de administración.
CREATE TABLE IF NOT EXISTS bitacora (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_id    INTEGER REFERENCES grupos(id) ON DELETE CASCADE,
    actor_id    INTEGER REFERENCES usuarios(id),
    accion      TEXT NOT NULL,
    objetivo_id INTEGER,
    detalle     TEXT,
    creado_utc  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS quinielas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_id    INTEGER NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    nombre      TEXT NOT NULL,                     -- "Liga MX · Cuartos de final"
    tipo        TEXT NOT NULL DEFAULT 'jornada' CHECK (tipo IN ('jornada','mixta','torneo')),
    estado      TEXT NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta','en_juego','cerrada')),
    cuota_texto TEXT,                              -- solo informativo, ej. "$50"
    creado_utc  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS quiniela_partidos (
    quiniela_id INTEGER NOT NULL REFERENCES quinielas(id) ON DELETE CASCADE,
    partido_id  INTEGER NOT NULL REFERENCES partidos(id),
    es_estelar  INTEGER NOT NULL DEFAULT 0,
    orden       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (quiniela_id, partido_id)
);
-- Solo un estelar por quiniela.
CREATE UNIQUE INDEX IF NOT EXISTS ux_un_estelar
    ON quiniela_partidos(quiniela_id) WHERE es_estelar = 1;

-- Quién juega cada quiniela y si ya pagó (lo marca el admin).
CREATE TABLE IF NOT EXISTS participaciones (
    quiniela_id INTEGER NOT NULL REFERENCES quinielas(id) ON DELETE CASCADE,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    pagado      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (quiniela_id, usuario_id)
);

CREATE TABLE IF NOT EXISTS pronosticos (
    quiniela_id     INTEGER NOT NULL REFERENCES quinielas(id) ON DELETE CASCADE,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    partido_id      INTEGER NOT NULL REFERENCES partidos(id),
    pick            TEXT NOT NULL CHECK (pick IN ('L','E','V')),
    actualizado_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (quiniela_id, usuario_id, partido_id)
);

-- Marcador pronosticado del partido estelar.
CREATE TABLE IF NOT EXISTS desempates (
    quiniela_id     INTEGER NOT NULL REFERENCES quinielas(id) ON DELETE CASCADE,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    goles_local     INTEGER NOT NULL CHECK (goles_local BETWEEN 0 AND 20),
    goles_visitante INTEGER NOT NULL CHECK (goles_visitante BETWEEN 0 AND 20),
    actualizado_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (quiniela_id, usuario_id)
);

-- Tabla de posiciones precalculada (la recalcula el robot con cada gol).
CREATE TABLE IF NOT EXISTS posiciones (
    quiniela_id     INTEGER NOT NULL REFERENCES quinielas(id) ON DELETE CASCADE,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    posicion        INTEGER NOT NULL,
    posicion_anterior INTEGER,                     -- para las flechas de sube/baja
    puntos          INTEGER NOT NULL,
    exacto_estelar  INTEGER NOT NULL DEFAULT 0,
    distancia       INTEGER,
    provisional     INTEGER NOT NULL DEFAULT 1,    -- 1 mientras haya partidos sin terminar
    actualizado_utc TEXT NOT NULL,
    PRIMARY KEY (quiniela_id, usuario_id)
);
