import pysnmp.hlapi as snmplib  # type: ignore
import pysnmp.proto.rfc1902 as rfc1902  # type: ignore
from typing import ClassVar, Dict, Optional, cast

from .interface import OutletInterface


class SNMPOutlet(OutletInterface):
    type: ClassVar[str] = "snmp"

    def __init__(
        self,
        *,
        host: str,
        query_oid: str,
        query_on_value: object,
        query_off_value: object,
        update_oid: str,
        update_on_value: object,
        update_off_value: object,
        read_community: str = "public",
        write_community: str = "private",
    ) -> None:
        self.host = host
        self.query_oid = query_oid
        self.query_on_value = query_on_value
        self.query_off_value = query_off_value
        self.update_oid = update_oid
        self.update_on_value = update_on_value
        self.update_off_value = update_off_value
        self.read_community = read_community
        self.write_community = write_community

        if type(query_on_value) != type(query_off_value):
            raise Exception("Unexpected differing types for query on and off values!")
        if type(update_on_value) != type(update_off_value):
            raise Exception("Unexpected differing types for update on and off values!")

    def serialize(self) -> Dict[str, object]:
        return {
            'host': self.host,
            'query_oid': self.query_oid,
            'query_on_value': self.query_on_value,
            'query_off_value': self.query_off_value,
            'update_oid': self.update_oid,
            'update_on_value': self.update_on_value,
            'update_off_value': self.update_off_value,
            'read_community': self.read_community,
            'write_community': self.write_community,
        }

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> OutletInterface:
        return SNMPOutlet(
            host=cast(str, vals['host']),
            query_oid=cast(str, vals['query_oid']),
            query_on_value=vals['query_on_value'],
            query_off_value=vals['query_off_value'],
            update_oid=cast(str, vals['update_oid']),
            update_on_value=vals['update_on_value'],
            update_off_value=vals['update_off_value'],
            read_community=cast(str, vals['read_community']),
            write_community=cast(str, vals['write_community']),
        )

    def query(self, value: object) -> Optional[object]:
        if isinstance(self.query_on_value, int):
            try:
                return int(str(value))
            except ValueError:
                return None
        raise NotImplementedError(f"Type of query value {type(self.query_on_value)} not supported!")

    def update(self, value: bool) -> object:
        if isinstance(self.update_on_value, int):
            return rfc1902.Integer(self.update_on_value if value else self.update_off_value)
        raise NotImplementedError(f"Type of update value {type(self.update_on_value)} not supported!")

    def getState(self) -> Optional[bool]:
        iterator = snmplib.getCmd(
            snmplib.SnmpEngine(),
            snmplib.CommunityData(self.read_community),
            snmplib.UdpTransportTarget((self.host, 161), timeout=1.0, retries=0),
            snmplib.ContextData(),
            snmplib.ObjectType(snmplib.ObjectIdentity(self.query_oid)),
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
                    if actual == self.query_on_value:
                        return True
                    if actual == self.query_off_value:
                        return False
                    return None
        return None

    def setState(self, state: bool) -> None:
        iterator = snmplib.setCmd(
            snmplib.SnmpEngine(),
            snmplib.CommunityData(self.write_community),
            snmplib.UdpTransportTarget((self.host, 161)),
            snmplib.ContextData(),
            snmplib.ObjectType(snmplib.ObjectIdentity(self.update_oid), self.update(state)),
        )
        next(iterator)
