import pysnmp.hlapi as snmplib  # type: ignore
import pysnmp.proto.rfc1902 as rfc1902  # type: ignore
from typing import ClassVar, Dict, Optional, cast

from .interface import OutletInterface


class NP02Outlet(OutletInterface):
    type: ClassVar[str] = "np-02"

    def __init__(
        self,
        *,
        host: str,
        outlet: int,
        # Yes, they only support one community for read and write.
        community: str = "public",
    ) -> None:
        self.host = host
        self.outlet = outlet
        self.community = community

    def serialize(self) -> Dict[str, object]:
        return {
            'host': self.host,
            'outlet': self.outlet,
            'community': self.community,
        }

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> OutletInterface:
        return NP02Outlet(
            host=cast(str, vals['host']),
            outlet=cast(int, vals['outlet']),
            community=cast(str, vals['community']),
        )

    def query(self, value: object) -> Optional[int]:
        try:
            return int(str(value))
        except ValueError:
            return None

    def update(self, value: bool) -> object:
        return rfc1902.Integer(1 if value else 2)

    def getState(self) -> Optional[bool]:
        iterator = snmplib.getCmd(
            snmplib.SnmpEngine(),
            snmplib.CommunityData(self.community, mpModel=0),
            snmplib.UdpTransportTarget((self.host, 161), timeout=1.0, retries=0),
            snmplib.ContextData(),
            snmplib.ObjectType(snmplib.ObjectIdentity(f"1.3.6.1.4.1.21728.2.4.1.2.1.1.3.{self.outlet}")),
        )

        for response in iterator:
            errorIndication, errorStatus, errorIndex, varBinds = response
            if errorIndication:
                return None
            elif errorStatus:
                return None
            else:
                for varBind in varBinds:
                    actual = self.query(varBind[1])

                    # Yes, this is the documented response, they clearly had a bug
                    # where they couldn't clear the top bit so the outlets modify
                    # each other and they just documented it as such.
                    if actual in {0, 256, 2}:
                        return False
                    elif actual in {1, 257}:
                        return True
                    return None
        return None

    def setState(self, state: bool) -> None:
        iterator = snmplib.setCmd(
            snmplib.SnmpEngine(),
            snmplib.CommunityData(self.community, mpModel=0),
            snmplib.UdpTransportTarget((self.host, 161)),
            snmplib.ContextData(),
            snmplib.ObjectType(snmplib.ObjectIdentity(f"1.3.6.1.4.1.21728.2.4.1.2.1.1.4.{self.outlet}"), self.update(state)),
        )
        next(iterator)
