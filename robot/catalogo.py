"""Catálogo de competiciones soportadas.

Agregar una liga = agregar una fila. El explorador decide solo cuáles están activas.
Los 13 códigos ESPN se verificaron en vivo el 26/11/2026 (todos responden con su temporada actual).
IDs de API-Football: confirmar con su endpoint /leagues antes de depender del respaldo.
"""

# (codigo_espn, nombre, pais, apifootball_id, temporada_anual)
COMPETICIONES = [
    ("mex.1",                 "Liga MX",                 "México",         262, False),
    ("mex.2",                 "Liga de Expansión MX",    "México",         263, False),
    ("eng.1",                 "Premier League",          "Inglaterra",      39, False),
    ("esp.1",                 "LaLiga",                  "España",         140, False),
    ("ita.1",                 "Serie A",                 "Italia",         135, False),
    ("ger.1",                 "Bundesliga",              "Alemania",        78, False),
    ("fra.1",                 "Ligue 1",                 "Francia",         61, False),
    ("usa.1",                 "MLS",                     "Estados Unidos", 253, True),
    ("uefa.champions",        "UEFA Champions League",   "Europa",           2, False),
    ("uefa.europa",           "UEFA Europa League",      "Europa",           3, False),
    ("concacaf.champions",    "Concacaf Champions Cup",  "Norteamérica",    16, True),
    ("conmebol.libertadores", "Copa Libertadores",       "Sudamérica",      13, True),
    ("fifa.world",            "Copa del Mundo",          "Mundial",          1, True),
]
