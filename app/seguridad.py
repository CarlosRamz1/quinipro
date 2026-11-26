"""Sesiones sin contraseña: cada usuario tiene un token aleatorio; en la base solo se guarda su hash."""
import hashlib
import secrets


def nuevo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def nuevo_codigo(largo: int = 8) -> str:
    # Sin letras que se confunden (0/O, 1/I/L) para dictarlo por WhatsApp sin errores.
    alfabeto = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(largo))
