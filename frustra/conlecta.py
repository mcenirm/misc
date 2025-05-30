from __future__ import annotations

import collections
import typing


class NoClobberDict[_KT, _VT](dict[_KT, _VT]):
    def __setitem__(self, key: _KT, value: _VT):
        if key not in self:
            super().__setitem__(key, value)
            return

        if self[key] == value:
            return

        raise KeyError("key already exists", key, self[key], value)


class defaultdict_where_factory_takes_missing_key_as_arg[_KT, _VT](dict[_KT, _VT]):
    def __init__(self, default_factory: typing.Callable[[_KT], _VT]) -> None:
        super().__init__()
        self.default_factory = default_factory

    def __missing__(self, key: _KT) -> _VT:
        value = self[key] = self.default_factory(key)
        return value


class defaultdict_where_default_value_is_missing_key(
    defaultdict_where_factory_takes_missing_key_as_arg
):
    def __init__(self, *args, **kwargs):
        super().__init__(lambda k: k, *args, **kwargs)


class MapAndGroupByResultException(BaseException):
    """Partial results captured in e.results"""

    def __init__(self, *args, results={}):
        super().__init__(*args)
        self.results = dict(results)


def map_and_group_by_result[_IT, _RT](
    fn: typing.Callable[[_IT], _RT],
    iterable: typing.Iterable[_IT],
) -> dict[_RT, list[_IT]]:
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


if __name__ == "__main__":
    import doctest

    doctest.testmod()
