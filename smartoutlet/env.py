import os


def network_timeout() -> float:
    try:
        return float(os.environ.get("NETWORK_TIMEOUT", "1.0"))
    except TypeError:
        return 1.0
