from typing import ClassVar, Dict, cast

from .interface import OutletInterface, param
from .np_0xb import NP0XBOutlet


@param("host", "the hostname or IP address of the NP-05B you are attempting to control")
@param(
    "outlet",
    "the outlet number (between 1-5 inclusive) that you are attempting to control",
)
@param(
    "username", "the administrator username as specified in the NP-05B web interface"
)
@param(
    "password", "the administrator password as specified in the NP-05B web interface"
)
class NP05BOutlet(NP0XBOutlet):
    type: ClassVar[str] = "np-05b"

    def __init__(
        self,
        *,
        host: str,
        outlet: int,
        username: str = "admin",
        password: str = "admin",
    ) -> None:
        super().__init__(host, 5, outlet, username, password)

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> OutletInterface:
        return NP05BOutlet(
            host=cast(str, vals["host"]),
            outlet=cast(int, vals["outlet"]),
            username=cast(str, vals["username"]),
            password=cast(str, vals["password"]),
        )
