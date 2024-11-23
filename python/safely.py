from __future__ import annotations
import typing

__all__ = [
    "flatten",
    "str_or_none",
]


def str_or_none(obj) -> str | None:
    """
    Return str form of obj unless it is None

    >>> str_or_none(None)
    >>> str_or_none("")
    ''
    >>> str_or_none(1)
    '1'
    >>> str_or_none([1])
    '[1]'
    """

    if obj is None:
        return None
    else:
        return str(obj)


NotBytesOrStrT = typing.TypeVar("NotBytesOrStrT")


@typing.overload
def protect_in_tuple_if_bytes_or_str(obj: bytes) -> tuple[bytes]: ...
@typing.overload
def protect_in_tuple_if_bytes_or_str(obj: str) -> tuple[str]: ...
@typing.overload
def protect_in_tuple_if_bytes_or_str(obj: NotBytesOrStrT) -> NotBytesOrStrT: ...


def protect_in_tuple_if_bytes_or_str(obj):
    """
    Protect bytes or str by wrapping in a tuple

    >>> protect_in_tuple_if_bytes_or_str(None)
    >>> protect_in_tuple_if_bytes_or_str(123)
    123
    >>> protect_in_tuple_if_bytes_or_str("abc")
    ('abc',)
    >>> protect_in_tuple_if_bytes_or_str(b"abc")
    (b'abc',)
    >>> protect_in_tuple_if_bytes_or_str(list("abc"))
    ['a', 'b', 'c']
    """

    if isinstance(obj, bytes) or isinstance(obj, str):
        return (obj,)
    else:
        return obj


def flatten(iterable: typing.Iterable) -> typing.Generator[typing.Any, None, None]:
    """
    Flatten once without iterating strings

    >>> sample = ["xyz", None, 1, [2, [3, [4]]], [b"567"]]
    >>> list(flatten(sample))
    ['xyz', None, 1, 2, [3, [4]], b'567']
    >>> list(flatten(flatten(sample)))
    ['xyz', None, 1, 2, 3, [4], b'567']
    >>> list(flatten(flatten(flatten(sample))))
    ['xyz', None, 1, 2, 3, 4, b'567']
    """

    for item in map(protect_in_tuple_if_bytes_or_str, iterable):
        item_is_iterable = isinstance(item, typing.Iterable)
        if item_is_iterable:
            yield from item
        else:
            yield item


if __name__ == "__main__":
    import doctest

    doctest.testmod()
