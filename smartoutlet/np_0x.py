from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .interface import OutletInterface
from .env import network_timeout


if TYPE_CHECKING:
    import pysnmp.hlapi as snmplib  # type: ignore


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
        import pysnmp.hlapi as snmplib
        import pysnmp.proto.rfc1902 as rfc1902  # type: ignore

        self.snmplib = snmplib
        self.rfc1902 = rfc1902

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
        with self.engine() as engine:
            iterator = self.snmplib.getCmd(
                engine,
                self.snmplib.CommunityData(self.community, mpModel=0),
                self.snmplib.UdpTransportTarget((self.host, 161), timeout=network_timeout(), retries=0),
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
        with self.engine() as engine:
            iterator = self.snmplib.setCmd(
                engine,
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
