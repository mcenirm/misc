from __future__ import annotations


class NoClobberDict[_KT, _VT](dict[_KT, _VT]):
    def __setitem__(self, key: _KT, value: _VT):
        if key not in self:
            super().__setitem__(key, value)
            return

        if self[key] == value:
            return

        raise KeyError("key already exists", key, self[key], value)
