"""Adaptadores de fuentes de datos. Todos regresan partidos con el mismo formato:

{
  "competicion", "id_espn" | "id_apifootball", "fuente", "inicio_utc",
  "local", "visitante", "local_abrev", "visitante_abrev", "local_logo", "visitante_logo",
  "estado", "minuto", "goles_local", "goles_visitante",
  "goles_local_90", "goles_visitante_90", "revisar"
}
"""


class ErrorFuente(Exception):
    """La fuente no respondió o respondió algo inválido."""
