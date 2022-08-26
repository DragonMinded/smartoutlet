import requests
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
            response = requests.get(f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?$A5", timeout=1.0).content.decode('utf-8')
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            return None

        if '$' in response:
            return None
        if self.outlet == 1:
            return response[1] != '0'
        if self.outlet == 2:
            return response[0] != '0'
        return None

    def setState(self, state: bool) -> None:
        try:
            requests.get(f"http://{self.username}:{self.password}@{self.host}/cmd.cgi?$A3 {self.outlet} {'1' if state else '0'}", timeout=1.0)
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError):
            pass
