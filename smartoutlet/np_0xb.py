import random
import sys
import time
from typing import Dict, Optional

from .interface import OutletInterface
from .env import network_jitter, network_retries, network_timeout, network_wait, verbose_mode


class NP0XBOutlet(OutletInterface):
    def __init__(
        self,
        host: str,
        outlet_count: int,
        outlet: int,
        username: str,
        password: str,
    ) -> None:
        if outlet < 1 or outlet > outlet_count:
            raise Exception("Out of bounds outlet number!")

        self.host = host
        self.outlet = outlet
        self.username = username
        self.password = password

        # Import these here to pay less cost in import time.
        import requests
        import xml.etree.ElementTree as ET

        self.requests = requests
        self.ET = ET

    def serialize(self) -> Dict[str, object]:
        return {
            "host": self.host,
            "outlet": self.outlet,
            "username": self.username,
            "password": self.password,
        }

    def __getResponseImpl(self, uri: str) -> Optional[str]:
        try:
            resp = self.requests.get(uri, timeout=network_timeout())
            response = resp.content.decode("utf-8").strip()

            if resp.status_code != 200:
                if verbose_mode():
                    print(
                        f"Error talking to {self.host} outlet {self.outlet}: outlet returned {resp.status_code} with response {response}",
                        file=sys.stderr,
                    )
                return None

            return response
        except (
            self.requests.exceptions.ConnectTimeout,
            self.requests.exceptions.ConnectionError,
        ):
            if verbose_mode():
                print(f"Error talking to {self.host} outlet {self.outlet}: connection timeout to host", file=sys.stderr)
            return None

    def __getResponse(self, uri: str, retries: int = 0) -> Optional[str]:
        if retries < 0:
            retries = 0

        for _ in range(retries + 1):
            response = self.__getResponseImpl(uri)
            if response is not None:
                return response
            time.sleep(network_wait() + (network_jitter() * random.random()))
        return None

    def getState(self, force_legacy: bool = False) -> Optional[bool]:
        # We allow a force-legacy option here, because we call getState from within
        # setState, and if we have to call this we already know that it's a legacy
        # NP-0XB. So, stop wasting time figuring that out a second time!
        if not force_legacy:
            response = self.__getResponse(f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?$A5", retries=network_retries()) or "$"
        else:
            # Shouldn't ever get to the bottom stanza, but lets be sure anyway.
            response = "$"

        # There are two types of response here, if it returns "Success!" then
        # it doesn't respond to the correct documented protocol.
        if force_legacy or response == "Success!":
            relay = f"rly{self.outlet - 1}"
            response = self.__getResponse(
                f"http://{self.username}:{self.password}@{self.host}/status.xml",
                retries=network_retries(),
            ) or ""

            try:
                root = self.ET.fromstring(response)
                if root.tag == "response":
                    for child in root:
                        if child.tag == relay:
                            return child.text != "0"
            except self.ET.ParseError:
                pass

            if verbose_mode():
                print(f"Error querying {self.host} outlet {self.outlet}: unparseable output {response}", file=sys.stderr)
            return None

        if "$" in response:
            if verbose_mode():
                print(f"Error querying {self.host} outlet {self.outlet}: unparseable output {response}", file=sys.stderr)
            return None
        if (len(response) < (self.outlet - 1)) or not response.isnumeric():
            if verbose_mode():
                print(f"Error querying {self.host} outlet {self.outlet}: unparseable output {response}", file=sys.stderr)
            return None
        return response[-self.outlet] == "1"

    def setState(self, state: bool) -> None:
        response = self.__getResponse(
            f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?$A3 {self.outlet} {'1' if state else '0'}",
            retries=0,
        ) or ""

        if response == "Success!":
            # This outlet is not responding to the correct documented protocol,
            # we must query the status and then flip the relay if needed.
            actual = self.getState(force_legacy=True)
            if actual is None:
                # Couldn't query, so don't want to mess with toggling the relay.
                return

            if actual != state:
                # Need to toggle
                self.__getResponse(
                    f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?rly={self.outlet - 1}",
                    retries=0,
                )
