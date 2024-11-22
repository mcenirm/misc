"""
As of Python 3.12.7

## numerics
typing.Hashable         bool
typing.Hashable         complex
typing.Hashable         float
typing.Hashable         int
typing.SupportsAbs      bool
typing.SupportsAbs      complex
typing.SupportsAbs      float
typing.SupportsAbs      int
typing.SupportsComplex  complex
typing.SupportsFloat    bool
typing.SupportsFloat    float
typing.SupportsFloat    int
typing.SupportsIndex    bool
typing.SupportsIndex    int
typing.SupportsInt      bool
typing.SupportsInt      float
typing.SupportsInt      int
typing.SupportsRound    bool
typing.SupportsRound    float
typing.SupportsRound    int

## other
typing.AbstractSet      frozenset
typing.AbstractSet      set
typing.Callable         staticmethod
typing.Callable         type
typing.Collection       bytearray
typing.Collection       bytes
typing.Collection       dict
typing.Collection       frozenset
typing.Collection       list
typing.Collection       memoryview
typing.Collection       range
typing.Collection       set
typing.Collection       str
typing.Collection       tuple
typing.Container        bytearray
typing.Container        bytes
typing.Container        dict
typing.Container        frozenset
typing.Container        list
typing.Container        memoryview
typing.Container        range
typing.Container        set
typing.Container        str
typing.Container        tuple
typing.ContextManager   memoryview
typing.Dict             dict
typing.FrozenSet        frozenset
typing.Hashable         bytes
typing.Hashable         classmethod
typing.Hashable         enumerate
typing.Hashable         filter
typing.Hashable         frozenset
typing.Hashable         map
typing.Hashable         memoryview
typing.Hashable         property
typing.Hashable         range
typing.Hashable         reversed
typing.Hashable         slice
typing.Hashable         staticmethod
typing.Hashable         str
typing.Hashable         super
typing.Hashable         tuple
typing.Hashable         type
typing.Hashable         zip
typing.Iterable         bytearray
typing.Iterable         bytes
typing.Iterable         dict
typing.Iterable         enumerate
typing.Iterable         filter
typing.Iterable         frozenset
typing.Iterable         list
typing.Iterable         map
typing.Iterable         memoryview
typing.Iterable         range
typing.Iterable         reversed
typing.Iterable         set
typing.Iterable         str
typing.Iterable         tuple
typing.Iterable         zip
typing.Iterator         enumerate
typing.Iterator         filter
typing.Iterator         map
typing.Iterator         reversed
typing.Iterator         zip
typing.List             list
typing.Mapping          dict
typing.MutableMapping   dict
typing.MutableSequence  bytearray
typing.MutableSequence  list
typing.MutableSet       set
typing.Reversible       bytearray
typing.Reversible       bytes
typing.Reversible       dict
typing.Reversible       list
typing.Reversible       memoryview
typing.Reversible       range
typing.Reversible       str
typing.Reversible       tuple
typing.Sequence         bytearray
typing.Sequence         bytes
typing.Sequence         list
typing.Sequence         memoryview
typing.Sequence         range
typing.Sequence         str
typing.Sequence         tuple
typing.Set              set
typing.Sized            bytearray
typing.Sized            bytes
typing.Sized            dict
typing.Sized            frozenset
typing.Sized            list
typing.Sized            memoryview
typing.Sized            range
typing.Sized            set
typing.Sized            str
typing.Sized            tuple
typing.SupportsBytes    bytes
typing.Tuple            tuple
typing.Type             type
"""

import builtins
import itertools
import numbers
import types
import typing


def find_types_in_modules(
    *mods: types.ModuleType,
    qualify_names=True,
) -> dict[str, type]:
    d = {}
    for mod in mods:
        for name in dir(mod):
            if name.startswith("_"):
                # not public
                continue
            if mod == typing and name == "ByteString":
                # deprecated
                continue
            item = getattr(mod, name)
            if qualify_names:
                name = mod.__name__ + "." + name
            if item == object:
                # ignore base class of all classes
                continue
            try:
                isinstance(d, item)
            except TypeError:
                # skip troublemakers like typing.Any
                continue
            try:
                if issubclass(item, BaseException):
                    # ignore exception types
                    continue
            except TypeError:
                # TODO Is "arg 1 must be a class" an important error?
                pass
            d[name] = item
    return d


supertypes = find_types_in_modules(typing)
subtypes = find_types_in_modules(builtins, qualify_names=False)

numerics_supersubs = []
numerics_supernames_with_subtypes = set()
numerics_subnames_with_supertypes = set()

other_supersubs = []
other_supernames_with_subtypes = set()
other_subnames_with_supertypes = set()

for supername, subname in itertools.product(supertypes.keys(), subtypes.keys()):
    supertype = supertypes[supername]
    subtype = subtypes[subname]
    if supertype == subtype:
        continue
    try:
        if issubclass(subtype, supertype):
            if issubclass(subtype, numbers.Number):
                numerics_supersubs.append((supername, subname))
                numerics_supernames_with_subtypes.add(supername)
                numerics_subnames_with_supertypes.add(subname)
            else:
                other_supersubs.append((supername, subname))
                other_supernames_with_subtypes.add(supername)
                other_subnames_with_supertypes.add(subname)
    except TypeError:
        # ignore problems with issubclass(<a generic alias>, ...)
        pass

for label, supersubs, supernames_with_subtypes, subnames_with_supertypes in [
    (
        "numerics",
        numerics_supersubs,
        numerics_supernames_with_subtypes,
        numerics_subnames_with_supertypes,
    ),
    (
        "other",
        other_supersubs,
        other_supernames_with_subtypes,
        other_subnames_with_supertypes,
    ),
]:
    print("##", label)
    superwidth = max(map(len, supernames_with_subtypes))
    subwidth = max(map(len, subnames_with_supertypes))
    fmt = f"{{supername:{superwidth}}}  {{subname}}"
    for supername, subname in supersubs:
        print(fmt.format(supername=supername, subname=subname))
    print()
