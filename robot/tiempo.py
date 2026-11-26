"""Utilidades de fecha. Todo se guarda en UTC; se muestra en hora del centro de México.

México no tiene horario de verano desde 2022, así que usamos UTC-6 fijo
(evita depender del paquete tzdata en Windows).
"""
from datetime import datetime, timedelta, timezone

MX = timezone(timedelta(hours=-6), "CDMX")


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def a_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def de_iso(texto: str) -> datetime:
    t = texto.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def a_mx(texto_o_dt) -> str:
    dt = de_iso(texto_o_dt) if isinstance(texto_o_dt, str) else texto_o_dt
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    d = dt.astimezone(MX)
    return f"{dias[d.weekday()]} {d:%d/%m %H:%M}"
