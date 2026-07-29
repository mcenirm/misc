from __future__ import annotations

import collections
import collections.abc
import typing


class NoClobberDict[_KT, _VT](dict[_KT, _VT]):
    """Complains if the key already exists when trying to set a value"""

    def __setitem__(self, key: _KT, value: _VT):
        if key not in self:
            super().__setitem__(key, value)
            return

        if self[key] == value:
            return

        raise KeyError("key already exists", key, self[key], value)


class defaultdict_where_factory_takes_missing_key_as_arg[_KT, _VT](dict[_KT, _VT]):
    """Acts like defaultdict but use default_factory(key) as the value"""

    def __init__(self, default_factory: collections.abc.Callable[[_KT], _VT]) -> None:
        super().__init__()
        self.default_factory = default_factory

    def __missing__(self, key: _KT) -> _VT:
        value = self[key] = self.default_factory(key)
        return value


class defaultdict_where_default_value_is_missing_key(
    defaultdict_where_factory_takes_missing_key_as_arg
):
    """Acts like defaultdict but use key as the value"""

    def __init__(self, *args, **kwargs):
        super().__init__(lambda k: k, *args, **kwargs)


class MapAndGroupByResultException(BaseException):
    """Partial results captured in e.results"""

    def __init__(self, *args, results={}):
        super().__init__(*args)
        self.results = dict(results)


def map_and_group_by_result[_IT, _RT](
    fn: collections.abc.Callable[[_IT], _RT],
    iterable: collections.abc.Iterable[_IT],
) -> dict[_RT, list[_IT]]:
    """Group items by result of calling fn"""
    results: dict[_RT, list[_IT]] = {}
    for item in iterable:
        try:
            res = fn(item)
            if res not in results:
                results[res] = []
            results[res].append(item)
        except Exception as e:
            raise MapAndGroupByResultException(results=results) from e
    return results


class AdHocEquivalenceClasses[_KT]:
    """
    Track equivalence classes where the relation appears to be arbitrary.

    >>> ahec = AdHocEquivalenceClasses()
    >>> ahec.get_equivalence_classes()
    {}
    >>> ahec.equate(None)
    >>> ahec.get_equivalence_classes()
    {None: {None}}

    >>> ahec = AdHocEquivalenceClasses()
    >>> ahec.equate("a")
    'a'
    >>> ahec.get_equivalence_classes()
    {'a': {'a'}}
    >>> ahec.equate("a", "b", "c")
    'a'
    >>> ahec.equate("c", "d")
    'a'

    >>> ahec = AdHocEquivalenceClasses()
    >>> for a, b in [(1, 3), (2, 4), (5, 7), (6, 8), (9, 1), (10, 8), (5, 9), (2, 6)]:
    ...     _ = ahec.equate(a, b)
    ...     [sorted(eqcls) for _, eqcls in sorted(ahec.get_equivalence_classes().items())]
    [[1, 3]]
    [[1, 3], [2, 4]]
    [[1, 3], [2, 4], [5, 7]]
    [[1, 3], [2, 4], [5, 7], [6, 8]]
    [[1, 3, 9], [2, 4], [5, 7], [6, 8]]
    [[1, 3, 9], [2, 4], [5, 7], [6, 8, 10]]
    [[1, 3, 5, 7, 9], [2, 4], [6, 8, 10]]
    [[1, 3, 5, 7, 9], [2, 4, 6, 8, 10]]
    """

    def __init__(self):
        self._nextorder: int = 0
        self._keyorder: dict[_KT, int] = {}
        self._keyrep: dict[_KT, _KT] = {}
        self._repkeys: dict[_KT, set[_KT]] = collections.defaultdict(set)

    def get_equivalence_classes(self) -> dict[_KT, set[_KT]]:
        """Return a copy of the equivalence classes, by earliest key in the class."""
        return {rep: keyset.copy() for rep, keyset in self._repkeys.items() if keyset}

    def get_equivalence_class(self, key: _KT) -> set[_KT] | None:
        if key not in self._keyrep:
            return None
        return self._repkeys[self._keyrep[key]].copy()

    def equate(self, key: _KT, *more_keys: _KT) -> _KT:
        keys = [key, *more_keys]
        temprep = keys[0]
        for k in keys:
            if k not in self._keyorder:
                self._keyorder[k] = self._nextorder
                self._nextorder += 1
                self._keyrep[k] = temprep
        self._repkeys[temprep].update(keys)
        eqcls = set(keys)
        while True:
            eqcls_copy = eqcls.copy()
            for k in eqcls_copy:
                eqcls.add(self._keyrep[k])
                eqcls.update(self._repkeys[k])
            if eqcls == eqcls_copy:
                break
        newrep = sorted(eqcls, key=lambda k: self._keyorder[k])[0]
        for k in eqcls:
            self._keyrep[k] = newrep
            self._repkeys[k].clear()
        self._repkeys[newrep].clear()
        self._repkeys[newrep].update(eqcls)
        return newrep


def iter_over_nested(
    data: typing.Any,
    keys: collections.abc.Sequence[
        collections.abc.Hashable | typing.SupportsIndex | type[list]
    ] = [],
    skip_missing=True,
) -> collections.abc.Generator[typing.Any, None, None]:
    """
    Use the keys to navigate the data structure and yield the values that are found.

    >>> data = {"a": [{"c": [1, 2, 3, 4]}]}
    >>> list(iter_over_nested(data, ["a", 0, "c", 0]))
    [1]
    >>> list(iter_over_nested(data, ["a", 0, "c", slice(1, -1)]))
    [2, 3]
    >>> list(iter_over_nested(data, ["a", 0, "c", list]))
    [1, 2, 3, 4]
    >>> list(iter_over_nested(data, ["a", 0, "c"]))
    [[1, 2, 3, 4]]

    >>> data = [
    ...     {"name": "Alice", "color": "blue"},
    ...     {"name": "Bob", "color": "orange"},
    ...     {"name": "Eve"},
    ... ]
    >>> list(iter_over_nested(data, [list, "name"]))
    ['Alice', 'Bob', 'Eve']
    >>> list(iter_over_nested(data, [list, "color"]))
    ['blue', 'orange']
    >>> list(iter_over_nested(data, [list, "color"], skip_missing=False))
    Traceback (most recent call last):
    ...
    KeyError: 'color'

    """

    if keys:
        key, rest = keys[0], keys[1:]
        value_iter = None

        if key is list:
            value_iter = iter(data)
        elif isinstance(key, slice):
            value_iter = iter(data[key])
        elif skip_missing:
            try:
                value_iter = iter([data[key]])
            except LookupError:
                value_iter = iter([])
        else:
            value_iter = iter([data[key]])

        if value_iter is None:
            raise NotImplementedError(
                "unexpected key type",
                type(key),
                key,
            )
        for value in value_iter:
            yield from iter_over_nested(
                value,
                rest,
                skip_missing=skip_missing,
            )
    else:
        yield data


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
