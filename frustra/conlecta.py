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
