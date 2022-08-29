import logging
import os
import Pyro5.errors  # type: ignore
import sys
import time
from Pyro5.api import Proxy, expose, behavior  # type: ignore
from typing import ClassVar, Dict, Final, Optional, cast

from . import ALL_OUTLET_CLASSES
from .interface import OutletInterface


PROXY_VERSION: Final[int] = 4
PROXY_PORT: Final[int] = 54545
PROXY_CACHE_TIME: Final[float] = 0.5


exit_daemon: bool = False


class OutletProxy(OutletInterface):
    type: ClassVar[str] = "proxy"

    def __init__(self, proxy: Proxy, vals: Dict[str, object]) -> None:
        self.vals = vals
        self.proxy = proxy

    def serialize(self) -> Dict[str, object]:
        # We don't implement this, because this is a local proxy object only.
        raise NotImplementedError("Do not serialize proxy outlets!")

    @staticmethod
    def __connect(port: int) -> Optional[Proxy]:
        proxy = Proxy(f"PYRO:smartoutlet@localhost:{port}")
        try:
            running = proxy.checkVersion(PROXY_VERSION)
        except Pyro5.errors.CommunicationError:
            running = False
        except Pyro5.errors.NamingError:
            running = False

        if running:
            return proxy
        else:
            return None

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> "OutletInterface":
        # We use this to connect to a remote interface
        if "type" not in vals:
            raise Exception("Could not instantiate a deserialization of an abstract outlet!")

        if "port" in vals:
            port = cast(int, vals['port'])
            del vals['port']
        else:
            port = PROXY_PORT

        logloc = None
        if "log" in vals:
            logloc = cast(str, vals["log"])
            del vals["log"]

        # Attempt to connect to an existing remote daemon that's already started.
        proxy = OutletProxy.__connect(port)

        # If it is not already running, attempt to start a new one.
        if proxy is None:
            pid = os.fork()
            if pid == 0:
                # Decouple from parent.
                os.chdir("/")
                os.setsid()
                os.umask(0)

                # Secondary fork.
                pid = os.fork()
                if pid > 0:
                    # We're the parent, we should exit.
                    sys.exit(0)

                # Set up logging to go to file.
                if logloc is not None:
                    try:
                        os.remove(logloc)
                    except FileNotFoundError:
                        pass
                    logging.basicConfig(filename=logloc, level=logging.INFO)

                # Now, start the server daemon.
                for _ in range(500):
                    try:
                        daemon = Pyro5.server.Daemon(host="localhost", port=port)
                        logging.info(f"Started daemon server listening on {port}")
                        break
                    except OSError:
                        # Can happen when restarting server.
                        time.sleep(0.01)
                else:
                    raise Exception("Failed to spawn proxy daemon instance!")

                # Now, run the loop until we're requested to exit.
                daemon.register(OutletDaemon, objectId="smartoutlet")
                daemon.requestLoop(lambda: not exit_daemon)
                sys.exit(0)

            else:
                for _ in range(500):
                    try:
                        proxy = OutletProxy.__connect(port)
                    except OSError:
                        # Can happen when restarting server.
                        proxy = None

                    if proxy is not None:
                        break
                    time.sleep(0.01)
                else:
                    raise Exception("Failed to spawn proxy daemon instance!")

        return OutletProxy(proxy, vals)

    def getState(self) -> Optional[bool]:
        # This is where we talk to the remote daemon.
        return cast(Optional[bool], self.proxy.getState(self.vals))

    def setState(self, state: bool) -> None:
        # This is where we talk to the remote daemon.
        self.proxy.setState(self.vals, state)


@expose
@behavior(instance_mode="single")
class OutletDaemon:
    def __init__(self) -> None:
        self.registered_outlets: Dict[str, OutletInterface] = {}
        self.cached_states: Dict[str, Optional[bool]] = {}
        self.cached_times: Dict[str, float] = {}

    def checkVersion(self, proxy_version: int) -> bool:
        if proxy_version == PROXY_VERSION:
            return True

        # We need to kill ourselves, we're running the wrong version!
        logging.info("We are running the wrong version, so time to die!")

        global exit_daemon
        exit_daemon = True

        return False

    def __getKey(self, vals: Dict[str, object]) -> str:
        return "-".join(f"{k}:{vals[k]}" for k in sorted(vals.keys()))

    def __getClass(self, vals: Dict[str, object]) -> OutletInterface:
        key = self.__getKey(vals)
        knowntype: str = cast(str, vals['type'])
        del vals['type']

        if key not in self.registered_outlets:
            for clz in ALL_OUTLET_CLASSES:
                if clz.type.lower() == knowntype.lower():
                    logging.info(f"Registering new outlet with key {key}")
                    self.registered_outlets[key] = clz.deserialize(vals)
                    break
            else:
                raise Exception(f"Cannot deserialize outlet of type {knowntype}!")

        return self.registered_outlets[key]

    def getState(self, vals: Dict[str, object]) -> Optional[bool]:
        key = self.__getKey(vals)
        if key not in self.cached_states or self.cached_times[key] < (time.time() - PROXY_CACHE_TIME):
            outlet = self.__getClass(vals)
            logging.info(f"Fetching state for {key}")
            self.cached_states[key] = outlet.getState()
            self.cached_times[key] = time.time()

        logging.info(f"State for {key} is {self.cached_states[key]}")
        return self.cached_states[key]

    def setState(self, vals: Dict[str, object], state: bool) -> None:
        key = self.__getKey(vals)
        outlet = self.__getClass(vals)
        logging.info(f"Setting state for {key} to {state}")
        outlet.setState(state)
        self.cached_states[key] = outlet.getState()
        self.cached_times[key] = time.time()
        logging.info(f"State for {key} is {self.cached_states[key]}")
