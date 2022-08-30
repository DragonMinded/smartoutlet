import logging
import os
import pickle
import socket
import struct
import sys
import threading
import time
from typing import ClassVar, Dict, Final, List, Optional, cast

from . import ALL_OUTLET_CLASSES
from .interface import OutletInterface


PROXY_VERSION: Final[int] = 5
PROXY_PORT: Final[int] = 54545
PROXY_CACHE_TIME: Final[float] = 5.0
PROXY_CACHE_REFILL_TIME: Final[float] = 3.0
PROXY_POOL_SIZE: Final[int] = 10


exit_daemon: bool = False


class OutletConnection:
    def __init__(self, port: int) -> None:
        self.port: int = port
        self.sock: Optional[socket.socket] = None

    def send(self, data: object) -> None:
        if self.sock is None:
            return
        pickled = pickle.dumps(data)
        self.sock.send(struct.pack("<I", len(pickled)) + pickled)

    def recv(self) -> object:
        if self.sock is None:
            return None

        data = self.sock.recv(4)
        length = struct.unpack("<I", data)[0]

        data = b""
        while len(data) < length:
            data += self.sock.recv(length)

        return pickle.loads(data)

    def connect(self) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("localhost", self.port))
        except ConnectionRefusedError:
            return False

        self.sock = sock
        self.send(("checkVersion", PROXY_VERSION))
        retval = self.recv()
        if isinstance(retval, bool):
            return retval
        return False

    def disconnect(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None


class OutletProxy(OutletInterface):
    type: ClassVar[str] = "proxy"

    def __init__(self, conn: OutletConnection, vals: Dict[str, object]) -> None:
        self.vals = vals
        self.conn = conn

    def serialize(self) -> Dict[str, object]:
        # We don't implement this, because this is a local proxy object only.
        raise NotImplementedError("Do not serialize proxy outlets!")

    @staticmethod
    def __connect(port: int) -> Optional[OutletConnection]:
        conn = OutletConnection(port)
        if conn.connect():
            return conn
        else:
            return None

    @staticmethod
    def deserialize(vals: Dict[str, object]) -> "OutletInterface":
        # We use this to connect to a remote interface
        if "type" not in vals:
            raise Exception("Could not instantiate a deserialization of an abstract outlet!")

        if "port" in vals:
            port = cast(int, vals['port'] or PROXY_PORT)
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
                        daemon = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        daemon.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        daemon.settimeout(0.05)
                        daemon.bind(("localhost", port))
                        daemon.listen(1)

                        logging.info(f"Started daemon server listening on {port}")
                        break
                    except OSError:
                        # Can happen when restarting server.
                        time.sleep(0.01)
                else:
                    raise Exception("Failed to spawn proxy daemon instance!")

                # Now, run the loop until we're requested to exit.
                outletdaemon = OutletDaemon()
                while not exit_daemon:
                    try:
                        conn, _ = daemon.accept()
                    except socket.timeout:
                        time.sleep(0.01)
                        continue

                    def reply(data: object) -> None:
                        pickled = pickle.dumps(data)
                        conn.send(struct.pack("<I", len(pickled)) + pickled)

                    try:
                        while True:
                            # Handle the message
                            data = conn.recv(4)
                            length = struct.unpack("<I", data)[0]

                            data = b""
                            while len(data) < length:
                                data += conn.recv(length)

                            actual = pickle.loads(data)
                            if isinstance(actual, tuple) and len(actual) == 2:
                                cmd, param = actual
                                if cmd == "checkVersion":
                                    reply(outletdaemon.checkVersion(param))
                                elif cmd == "getState":
                                    reply(outletdaemon.getState(param))
                                elif cmd == "setState":
                                    outletdaemon.setState(*param)
                                else:
                                    logging.warning(f"Unrecognized command {cmd}!")
                            else:
                                logging.warning("Unrecognized packet!")

                    except Exception:
                        pass
                    finally:
                        conn.close()

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
        self.conn.send(("getState", self.vals))
        return cast(Optional[bool], self.conn.recv())

    def setState(self, state: bool) -> None:
        # This is where we talk to the remote daemon.
        self.conn.send(("setState", (self.vals, state)))


def pollThread(daemon: "OutletDaemon", num: int) -> None:
    daemon.poll(num)


class OutletDaemon:
    def __init__(self) -> None:
        # Cache contrl and registered outlets.
        self.registered_outlets: Dict[str, OutletInterface] = {}
        self.cached_states: Dict[str, Optional[bool]] = {}
        self.cached_times: Dict[str, float] = {}

        # Threadpool control structures
        self.pending_keys_lock: threading.Lock = threading.Lock()
        self.pending_keys: List[str] = []
        self.thread_count: int = 0

    def start_thread(self) -> None:
        thread = None
        with self.pending_keys_lock:
            if self.thread_count < PROXY_POOL_SIZE:
                self.thread_count += 1
                thread = threading.Thread(target=pollThread, args=(self, self.thread_count), daemon=True)

        if thread is not None:
            thread.start()

    def poll(self, num: int) -> None:
        logging.debug(f"Starting polling thread {num}")

        while True:
            try:
                # First, let's do some bookkeeping.
                with self.pending_keys_lock:
                    if not self.pending_keys:
                        # We're clever to use cached times here, so the initial poll doesn't
                        # cause us to make the CLI wait longer.
                        logging.debug("Full sweep completed, starting over!")
                        self.pending_keys = [x for x in self.cached_times]

                    key = None
                    if self.pending_keys:
                        key = self.pending_keys.pop()

                if key is not None and self.cached_times[key] < (time.time() - PROXY_CACHE_REFILL_TIME):
                    # Now, let's fetch the outlet in order to refresh.
                    outlet = self.registered_outlets[key]
                    logging.debug(f"Caching state for {key}")
                    self.cached_states[key] = outlet.getState()
                    self.cached_times[key] = time.time()
                    logging.debug(f"Cached state for {key} is {self.cached_states[key]}")
                else:
                    # Sleep a little longer, given we had nothing to do.
                    time.sleep(0.5)

            except Exception:
                logging.exception(f"Failed to poll in thread {num}")

            # Sleep a little, give the rest of the code some breathing room.
            time.sleep(0.05)

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
                    self.start_thread()

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
