from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Tuple, cast

from .interface import OutletInterface, param
from .env import network_timeout


if TYPE_CHECKING:
    import pysnmp.hlapi as snmplib  # type: ignore


@param(
    "host",
    "the hostname or IP address of the SNMP-based outlet you are attempting to control",
)
@param(
    "query_oid",
    "the dotted OID that should be queried to determine the state of the outlet",
)
@param(
    "query_on_value",
    "the integer value that gets returned from the outlet to designate that it is on",
)
@param(
    "query_off_value",
    "the integer value that gets returned from the outlet to designate that it is off",
)
@param(
    "update_oid",
    "the dotted OID that should be set when updating the state of the outlet",
)
@param(
    "update_on_value",
    "the integer value that gets used when setting the state of the outlet to on",
)
@param(
    "update_off_value",
    "the integer value that gets used when setting the state of the outlet to off",
)
@param(
    "read_community", "the SNMP read community as configured on the SNMP-based outlet"
)
@param(
    "write_community", "the SNMP write community as configured on the SNMP-based outlet"
)
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

        # Import this here to pay less startup time cost.
        import pysnmp.hlapi as snmplib
        import pysnmp.proto.rfc1902 as rfc1902  # type: ignore

        self.snmplib = snmplib
        self.rfc1902 = rfc1902

        if type(query_on_value) != type(query_off_value):
            raise Exception("Unexpected differing types for query on and off values!")
        if type(update_on_value) != type(update_off_value):
            raise Exception("Unexpected differing types for update on and off values!")

        self.engine_cache_lock = Lock()

        # Since we will need at least one engine, create it. The rest will end up created
        # if we use this same object in multiple threads and query at the same time.
        self.engine_cache_lock.acquire()
        try:
            self.engine_cache: List[Tuple[bool, "snmplib.SnmpEngine"]] = [(False, self.snmplib.SnmpEngine())]
        finally:
            self.engine_cache_lock.release()

    @contextmanager
    def engine(self) -> "snmplib.SnmpEngine":
        # We have to do this set of shenanigans because we want these objects to be cacheable
        # and also multi-threaded aware. The SNMP library specifically says you want one engine
        # per thread in multi-threaded environments. But, we run in envs with short-lived
        # threads so we don't want to use threadlocal storage or we'd just create a new engine
        # every time. So, manage which engines are in use (you can only be in use already if another
        # thread is running simultaneously) and dish out unused ones.

        self.engine_cache_lock.acquire()

        # Grab an unused engine.
        try:
            engine: "snmplib.SnmpEngine"
            for i in range(len(self.engine_cache)):
                if not self.engine_cache[i][0]:
                    # This one isn't in use, let's mark it as in use and use it.
                    self.engine_cache[i] = (True, self.engine_cache[i][1])
                    engine = self.engine_cache[i][1]
                    break
            else:
                # All of them are in use, create a new one.
                engine = self.snmplib.SnmpEngine()
                self.engine_cache.append((True, engine))
        finally:
            self.engine_cache_lock.release()

        try:
            yield engine
        finally:
            # Now, mark it as not in use anymore.
            self.engine_cache_lock.acquire()

            try:
                for i in range(len(self.engine_cache)):
                    if self.engine_cache[i][1] is engine:
                        self.engine_cache[i] = (False, engine)
                        break
            finally:
                self.engine_cache_lock.release()

    def serialize(self) -> Dict[str, object]:
        return {
            "host": self.host,
            "query_oid": self.query_oid,
            "query_on_value": self.query_on_value,
            "query_off_value": self.query_off_value,
            "update_oid": self.update_oid,
            "update_on_value": self.update_on_value,
            "update_off_value": self.update_off_value,
            "read_community": self.read_community,
            "write_community": self.write_community,
        }

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> OutletInterface:
        return SNMPOutlet(
            host=cast(str, vals["host"]),
            query_oid=cast(str, vals["query_oid"]),
            query_on_value=vals["query_on_value"],
            query_off_value=vals["query_off_value"],
            update_oid=cast(str, vals["update_oid"]),
            update_on_value=vals["update_on_value"],
            update_off_value=vals["update_off_value"],
            read_community=cast(str, vals["read_community"]),
            write_community=cast(str, vals["write_community"]),
        )

    def query(self, value: object) -> Optional[object]:
        if isinstance(self.query_on_value, int):
            try:
                return int(str(value))
            except ValueError:
                return None
        raise NotImplementedError(
            f"Type of query value {type(self.query_on_value)} not supported!"
        )

    def update(self, value: bool) -> object:
        if isinstance(self.update_on_value, int):
            return self.rfc1902.Integer(
                self.update_on_value if value else self.update_off_value
            )
        raise NotImplementedError(
            f"Type of update value {type(self.update_on_value)} not supported!"
        )

    def getState(self) -> Optional[bool]:
        with self.engine() as engine:
            iterator = self.snmplib.getCmd(
                engine,
                self.snmplib.CommunityData(self.read_community, mpModel=0),
                self.snmplib.UdpTransportTarget((self.host, 161), timeout=network_timeout(), retries=0),
                self.snmplib.ContextData(),
                self.snmplib.ObjectType(self.snmplib.ObjectIdentity(self.query_oid)),
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
        with self.engine() as engine:
            iterator = self.snmplib.setCmd(
                engine,
                self.snmplib.CommunityData(self.write_community, mpModel=0),
                self.snmplib.UdpTransportTarget((self.host, 161)),
                self.snmplib.ContextData(),
                self.snmplib.ObjectType(
                    self.snmplib.ObjectIdentity(self.update_oid), self.update(state)
                ),
            )
            next(iterator)
