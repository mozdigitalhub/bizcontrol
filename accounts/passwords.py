import secrets


TEMP_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def generate_temp_password(length=12):
    length = max(int(length or 0), 8)
    return "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(length))
