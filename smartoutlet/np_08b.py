from typing import ClassVar, Dict, cast

from .interface import OutletInterface, param
from .np_0xb import NP0XBOutlet


@param("host", "the hostname or IP address of the NP-08B you are attempting to control")
@param(
    "outlet",
    "the outlet number (between 1-8 inclusive) that you are attempting to control",
)
@param(
    "username", "the administrator username as specified in the NP-08B web interface"
)
@param(
    "password", "the administrator password as specified in the NP-08B web interface"
)
class NP08BOutlet(NP0XBOutlet):
    type: ClassVar[str] = "np-08b"

    def __init__(
        self,
        *,
        host: str,
        outlet: int,
        username: str = "admin",
        password: str = "admin",
    ) -> None:
        super().__init__(host, 8, outlet, username, password)

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> OutletInterface:
        return NP08BOutlet(
            host=cast(str, vals["host"]),
            outlet=cast(int, vals["outlet"]),
            username=cast(str, vals["username"]),
            password=cast(str, vals["password"]),
        )
