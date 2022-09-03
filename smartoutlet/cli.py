import argparse
import inspect
import os
import sys

from smartoutlet import ALL_OUTLET_CLASSES


def addargs(parser: argparse.ArgumentParser) -> None:
    logloc = os.path.abspath(os.path.join(os.getcwd(), "daemon.log"))
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Use a local daemon to speed up fetch and set requests.",
    )
    parser.add_argument(
        "--port",
        metavar="PORT",
        type=int,
        help="the port which the daemon will listen on, defaults to 54545",
    )
    parser.add_argument(
        "--log",
        metavar="LOG",
        type=str,
        default=logloc,
        help=f"the logfile we will write daemon logs to, defaults to {logloc}",
    )


def cli(mode: str) -> int:
    outlettypes = ', '.join(c.type for c in ALL_OUTLET_CLASSES)

    if mode == "fetch":
        parser = argparse.ArgumentParser(description="Fetch the state of a smart outlet or PDU.", add_help=False)
    else:
        parser = argparse.ArgumentParser(description="Set the state of a smart outlet or PDU.", add_help=False)
    parser.add_argument(
        "type",
        metavar="TYPE",
        type=str,
        nargs="?",
        default="",
        help=f"the type of outlet you are controlling, valid values are {outlettypes}",
    )
    addargs(parser)

    knownargs, _ = parser.parse_known_args()

    # Rebuild parser with help enabled so we can get actual help strings.
    if mode == "fetch":
        parser = argparse.ArgumentParser(description="Fetch the state of a smart outlet or PDU.")
    else:
        parser = argparse.ArgumentParser(description="Set the state of a smart outlet or PDU.")
    parser.add_argument(
        "type",
        metavar="TYPE",
        type=str,
        help=f"the type of outlet you are controlling, valid values are {outlettypes}",
    )
    addargs(parser)

    # Add outlet-specific arguments.
    for clz in ALL_OUTLET_CLASSES:
        if clz.type.lower() == knownargs.type.lower():
            # Figure out arguments to add for this outlet.
            signature = inspect.signature(clz.__init__)
            params = getattr(clz, "__params__", {})
            for param in signature.parameters.values():
                if param.name == "self":
                    continue
                if param.default is inspect.Parameter.empty:
                    parser.add_argument(
                        param.name,
                        metavar=param.name.upper(),
                        type=param.annotation,
                        help=params.get(param.name, f"{param.annotation.__name__} parameter"),
                    )
                else:
                    parser.add_argument(
                        f"--{param.name}",
                        type=param.annotation,
                        default=param.default,
                        help=params.get(param.name, f"{param.annotation.__name__} parameter") + f", defaults to {param.default}",
                    )
            break
    else:
        if knownargs.type:
            print(f"Unrecognized outlet type {knownargs.type}!", os.linesep, file=sys.stderr)
            parser.print_help()
            return 1

    if mode == "set":
        parser.add_argument(
            "state",
            metavar="STATE",
            type=str,
            help="the state you want to set the outlet to, valid values are on and off",
        )
    args = vars(parser.parse_args())
    if mode == "set":
        state = args['state'].lower() == "on"
        del args['state']

    # Figure out arguments to add for this outlet.
    signature = inspect.signature(clz.__init__)
    constructor_args = {}
    for param in signature.parameters.values():
        if param.name == "self":
            continue
        constructor_args[param.name] = args[param.name]

    if args['daemon']:
        # Import this here so we don't pay the cost otherwise.
        from smartoutlet.daemon import OutletProxy
        inst = OutletProxy.deserialize({'type': clz.type, 'port': args['port'], 'log': args['log'], **constructor_args})
    else:
        inst = clz.deserialize(constructor_args)

    if mode == "fetch":
        state = inst.getState()
        if state is None:
            print("unknown")
        else:
            print("on" if state else "off")
    else:
        inst.setState(state)

    return 0
