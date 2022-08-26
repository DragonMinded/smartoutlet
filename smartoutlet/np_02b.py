import requests
import xml.etree.ElementTree as ET
from typing import ClassVar, Dict, Optional, cast

from .interface import OutletInterface


class NP02BOutlet(OutletInterface):
    type: ClassVar[str] = "np-02b"

    def __init__(
        self,
        *,
        host: str,
        outlet: int,
        username: str = "admin",
        password: str = "admin",
    ) -> None:
        self.host = host
        self.outlet = outlet
        self.username = username
        self.password = password

    def serialize(self) -> Dict[str, object]:
        return {
            'host': self.host,
            'outlet': self.outlet,
            'username': self.username,
            'password': self.password,
        }

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> OutletInterface:
        return NP02BOutlet(
            host=cast(str, vals['host']),
            outlet=cast(int, vals['outlet']),
            username=cast(str, vals['username']),
            password=cast(str, vals['password']),
        )

    def getState(self) -> Optional[bool]:
        try:
            response = requests.get(
                f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?$A5",
                timeout=1.0,
            ).content.decode('utf-8').strip()
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            return None

        # There are two types of response here, if it returns "Success!" then
        # it doesn't respond to the correct documented protocol.
        if response == "Success!":
            relay = f"rly{self.outlet - 1}"
            response = requests.get(
                f"http://{self.username}:{self.password}@{self.host}/status.xml",
                timeout=1.0
            ).content.decode('utf-8')

            root = ET.fromstring(response)
            if root.tag == "response":
                for child in root:
                    if child.tag == relay:
                        return child.text != '0'
            return None

        if '$' in response:
            return None
        if len(response) < (self.outlet - 1):
            return None
        return response[-self.outlet] != '0'

    def setState(self, state: bool) -> None:
        try:
            response = requests.get(
                f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?$A3 {self.outlet} {'1' if state else '0'}",
                timeout=1.0
            ).content.decode('utf-8').strip()
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            return

        if response == "Success!":
            # This outlet is not responding to the correct documented protocol,
            # we must query the status and then flip the relay if needed.
            actual = self.getState()
            if actual is None:
                # Couldn't query, so don't want to mess with toggling the relay.
                return

            if actual != state:
                try:
                    # Need to toggle
                    requests.get(f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?rly={self.outlet - 1}", timeout=1.0)
                except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
                    pass
