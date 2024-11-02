import os


def network_timeout() -> float:
    try:
        return float(os.environ.get("NETWORK_TIMEOUT", "1.0"))
    except TypeError:
        return 1.0


def network_retries() -> int:
    try:
        return int(os.environ.get("NETWORK_RETRIES", "2"))
    except TypeError:
        return 2


def verbose_mode() -> bool:
    try:
        return bool(os.environ.get("VERBOSE_LOGGING", ""))
    except TypeError:
        return False
