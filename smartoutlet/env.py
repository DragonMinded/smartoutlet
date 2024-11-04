import os


def network_timeout() -> float:
    """
    The number of seconds, as a floating point number, before assuming an outstanding
    request to an outlet is lost and timing out. Note that you can put partial seconds
    here, such as 1.5 for one and a half seconds.
    """

    try:
        return float(os.environ.get("NETWORK_TIMEOUT", "1.0"))
    except TypeError:
        return 1.0


def network_wait() -> float:
    """
    The number of seconds to wait, when retrying, before sending the retry itself. Note
    that all retries will wait for exactly this time before attempting another query. The
    actual wait value is the value of this added to the calculated jitter from the below
    function.
    """

    try:
        return float(os.environ.get("NETWORK_WAIT", "0.1"))
    except TypeError:
        return 0.1


def network_jitter() -> float:
    """
    The maximum number of seconds to wait, when retrying, before sending the retry itself.
    Note that as the name implies, this is the maximum value, and a random value inbetween
    0.0 and this value will be chosen, when waiting for retries. This adds a bit of random
    jitter to requests, so if you have a unit that gets overwhelmed with SNMP requests you
    can spread things out randomly. The actual wait value is the value of this added to the
    static wait value from the above function.
    """

    try:
        return float(os.environ.get("NETWORK_JITTER", "0.0"))
    except TypeError:
        return 0.0


def network_retries() -> int:
    """
    The number of retries to perform after the initial request fails. Set to zero to never
    retry.
    """

    try:
        return int(os.environ.get("NETWORK_RETRIES", "2"))
    except TypeError:
        return 2


def verbose_mode() -> bool:
    """
    Whether verbose logging should be output to the log of choice (either stdout or to a
    uwsgi log file depending on how you're running this). Set this to any value to enable,
    leave out to disable.
    """

    try:
        return bool(os.environ.get("VERBOSE_LOGGING", ""))
    except TypeError:
        return False
