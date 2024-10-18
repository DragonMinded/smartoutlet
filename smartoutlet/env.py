import os


def network_timeout() -> float:
    try:
        return float(os.environ.get("NETWORK_TIMEOUT", "1.0"))
    except TypeError:
        return 1.0


def verbose_mode() -> bool:
    try:
        return bool(os.environ.get("VERBOSE_LOGGING", ""))
    except TypeError:
        return False
