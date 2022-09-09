from typing import ClassVar

from .interface import param
from .ap790x import AP790XOutlet


@param("host", "the hostname or IP address of the AP7901 you are attempting to control")
@param("outlet", "the outlet number (between 1-8 inclusive) that you are attempting to control")
@param("read_community", "the SNMP read community as specified in the AP7901 config menu")
@param("write_community", "the SNMP write community as specified in the AP7901 config menu")
class AP7901Outlet(AP790XOutlet):
    type: ClassVar[str] = "ap7901"
