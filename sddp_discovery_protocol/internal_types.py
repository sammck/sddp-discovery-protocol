#
# Copyright (c) 2023 Samuel J. McKelvie
#
# MIT License - See LICENSE file accompanying this package.
#

"""Type hints used internally by this package"""

from typing import (
    Dict,
    Union,
    Any,
    List,
    Optional,
    Callable,
    Awaitable,
    NewType,
    AsyncIterable,
    AsyncGenerator,
    AsyncContextManager,
    AsyncIterable,
    Tuple,
    Type,
    Set,
    TypeVar,
    TYPE_CHECKING,
    FrozenSet,
    Coroutine,
    Generator,
    Iterable,
    Iterable,
    Mapping,
    MutableMapping,
    Sequence,
    AsyncIterator,
  )

from types import TracebackType


from typing_extensions import Self

JsonableTypes = ( str, int, float, bool, dict, list )
# A tuple of types to use for isinstance checking of JSON-serializable types. Excludes None. Useful for isinstance.

if TYPE_CHECKING:
  Jsonable = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
  """A Type hint for a simple JSON-serializable value; i.e., str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]"""
else:
  Jsonable = Union[str, int, float, bool, None, Dict[str, 'Jsonable'], List['Jsonable']]
  """A Type hint for a simple JSON-serializable value; i.e., str, int, float, bool, None, Dict[str, Jsonable], List[Jsonable]"""

JsonableDict = Dict[str, Jsonable]
"""A type hint for a simple JSON-serializable dict; i.e., Dict[str, Jsonable]"""

HostAndPort = Tuple[str, int]
"""A type hint for a host and port number; i.e., Tuple[str, int]"""
