from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar, Dict, Optional, TypeVar


class OutletInterface(ABC):
    type: ClassVar[str]

    @abstractmethod
    def serialize(self) -> Dict[str, object]:
        ...

    @staticmethod
    @abstractmethod
    def deserialize(vals: Dict[str, object]) -> "OutletInterface":
        ...

    @abstractmethod
    def getState(self) -> Optional[bool]:
        ...

    @abstractmethod
    def setState(self, state: bool) -> None:
        ...


F = TypeVar('F', bound=Callable[..., Any])


def param(param: str, description: str) -> Callable[[F], F]:
    def decorator(clz: F) -> F:
        paramdict = getattr(clz, "__params__", {})
        paramdict[param] = description
        setattr(clz, "__params__", paramdict)
        return clz

    return decorator
