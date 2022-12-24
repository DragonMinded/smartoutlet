from typing import Dict, Optional

from .interface import OutletInterface


class NP0XOutlet(OutletInterface):
    def __init__(
        self,
        host: str,
        outlet_count: int,
        outlet: int,
        # These devices only support one community for both read and write.
        community: str,
    ) -> None:
        if outlet < 1 or outlet > outlet_count:
            raise Exception("Out of bounds outlet number!")

        self.host = host
        self.outlet = outlet
        self.community = community

        # Import these here to pay less cost to startup time.
        import pysnmp.hlapi as snmplib  # type: ignore
        import pysnmp.proto.rfc1902 as rfc1902  # type: ignore

        self.snmplib = snmplib
        self.rfc1902 = rfc1902

    def serialize(self) -> Dict[str, object]:
        return {
            "host": self.host,
            "outlet": self.outlet,
            "community": self.community,
        }

    def query(self, value: object) -> Optional[int]:
        try:
            return int(str(value))
        except ValueError:
            return None

    def update(self, value: bool) -> object:
        return self.rfc1902.Integer(1 if value else 2)

    def getState(self) -> Optional[bool]:
        iterator = self.snmplib.getCmd(
            self.snmplib.SnmpEngine(),
            self.snmplib.CommunityData(self.community, mpModel=0),
            self.snmplib.UdpTransportTarget((self.host, 161), timeout=1.0, retries=0),
            self.snmplib.ContextData(),
            self.snmplib.ObjectType(
                self.snmplib.ObjectIdentity(
                    f"1.3.6.1.4.1.21728.2.4.1.2.1.1.3.{self.outlet}"
                )
            ),
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
        iterator = self.snmplib.setCmd(
            self.snmplib.SnmpEngine(),
            self.snmplib.CommunityData(self.community, mpModel=0),
            self.snmplib.UdpTransportTarget((self.host, 161)),
            self.snmplib.ContextData(),
            self.snmplib.ObjectType(
                self.snmplib.ObjectIdentity(
                    f"1.3.6.1.4.1.21728.2.4.1.2.1.1.4.{self.outlet}"
                ),
                self.update(state),
            ),
        )
        next(iterator)
