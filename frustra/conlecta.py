from __future__ import annotations

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
