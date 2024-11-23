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

┌────────────────────────┬──────┬─────┬───────┬─────────┐
│ typing.Hashable        │ bool │ int │ float │ complex │
│ typing.SupportsAbs     │ bool │ int │ float │ complex │
│ typing.SupportsFloat   │ bool │ int │ float │         │
│ typing.SupportsInt     │ bool │ int │ float │         │
│ typing.SupportsRound   │ bool │ int │ float │         │
│ typing.SupportsIndex   │ bool │ int │       │         │
│ typing.SupportsComplex │      │     │       │ complex │
└────────────────────────┴──────┴─────┴───────┴─────────┘

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

┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┳━━━┓
┃                        ┃ b ┃ d ┃ l ┃ m ┃ t ┃ f ┃ s ┃ b ┃ r ┃ s ┃ t ┃ e ┃ f ┃ m ┃ r ┃ z ┃ s ┃ c ┃ p ┃ s ┃ s ┃
┃                        ┃ y ┃ i ┃ i ┃ e ┃ u ┃ r ┃ e ┃ y ┃ a ┃ t ┃ y ┃ n ┃ i ┃ a ┃ e ┃ i ┃ t ┃ l ┃ r ┃ l ┃ u ┃
┃                        ┃ t ┃ c ┃ s ┃ m ┃ p ┃ o ┃ t ┃ t ┃ n ┃ r ┃ p ┃ u ┃ l ┃ p ┃ v ┃ p ┃ a ┃ a ┃ o ┃ i ┃ p ┃
┃                        ┃ e ┃ t ┃ t ┃ o ┃ l ┃ z ┃   ┃ e ┃ g ┃   ┃ e ┃ m ┃ t ┃   ┃ e ┃   ┃ t ┃ s ┃ p ┃ c ┃ e ┃
┃                        ┃ s ┃   ┃   ┃ r ┃ e ┃ e ┃   ┃ a ┃ e ┃   ┃   ┃ e ┃ e ┃   ┃ r ┃   ┃ i ┃ s ┃ e ┃ e ┃ r ┃
┃                        ┃   ┃   ┃   ┃ y ┃   ┃ n ┃   ┃ r ┃   ┃   ┃   ┃ r ┃ r ┃   ┃ s ┃   ┃ c ┃ m ┃ r ┃   ┃   ┃
┃                        ┃   ┃   ┃   ┃ v ┃   ┃ s ┃   ┃ r ┃   ┃   ┃   ┃ a ┃   ┃   ┃ e ┃   ┃ m ┃ e ┃ t ┃   ┃   ┃
┃                        ┃   ┃   ┃   ┃ i ┃   ┃ e ┃   ┃ a ┃   ┃   ┃   ┃ t ┃   ┃   ┃ d ┃   ┃ e ┃ t ┃ y ┃   ┃   ┃
┃                        ┃   ┃   ┃   ┃ e ┃   ┃ t ┃   ┃ y ┃   ┃   ┃   ┃ e ┃   ┃   ┃   ┃   ┃ t ┃ h ┃   ┃   ┃   ┃
┃                        ┃   ┃   ┃   ┃ w ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃ h ┃ o ┃   ┃   ┃   ┃
┃                        ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃ o ┃ d ┃   ┃   ┃   ┃
┃                        ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃   ┃ d ┃   ┃   ┃   ┃   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━╇━━━┩
│ typing.Hashable        │ X │   │   │ X │ X │ X │   │   │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │
│ typing.Iterable        │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │   │ X │ X │ X │ X │ X │   │   │   │   │   │
│ typing.Collection      │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Container       │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Sized           │ X │ X │ X │ X │ X │ X │ X │ X │ X │ X │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Reversible      │ X │ X │ X │ X │ X │   │   │ X │ X │ X │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Sequence        │ X │   │ X │ X │ X │   │   │ X │ X │ X │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Iterator        │   │   │   │   │   │   │   │   │   │   │   │ X │ X │ X │ X │ X │   │   │   │   │   │
│ typing.AbstractSet     │   │   │   │   │   │ X │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Callable        │   │   │   │   │   │   │   │   │   │   │ X │   │   │   │   │   │ X │   │   │   │   │
│ typing.MutableSequence │   │   │ X │   │   │   │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.ContextManager  │   │   │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Dict            │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.FrozenSet       │   │   │   │   │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.List            │   │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Mapping         │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.MutableMapping  │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.MutableSet      │   │   │   │   │   │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Set             │   │   │   │   │   │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.SupportsBytes   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Tuple           │   │   │   │   │ X │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │   │
│ typing.Type            │   │   │   │   │   │   │   │   │   │   │ X │   │   │   │   │   │   │   │   │   │   │
└────────────────────────┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
"""

import builtins
import numbers
import types
import typing

try:
    import rich
    import rich.console
    import rich.table
    import rich.text
except ImportError:
    rich = None


TypeName = str
TypesInModules = dict[TypeName, type]
SuperSubPair = tuple[TypeName, TypeName]


def find_types_in_modules(
    *mods: types.ModuleType,
    qualify_names=True,
) -> TypesInModules:
    d: TypesInModules = {}
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


def super_sub_pairs(
    supertypes: TypesInModules,
    subtypes: TypesInModules,
) -> list[SuperSubPair]:
    pairs: list[SuperSubPair] = []
    for supername, supertype in supertypes.items():
        for subname, subtype in subtypes.items():
            if supertype == subtype:
                continue
            try:
                if issubclass(subtype, supertype):
                    pairs.append((supername, subname))
            except TypeError:
                # ignore problems with issubclass(<a generic alias>, ...)
                pass
    return pairs


typing_types = find_types_in_modules(typing)
builtin_types = find_types_in_modules(builtins, qualify_names=False)
builtin_numeric_types: TypesInModules = {
    n: t for n, t in builtin_types.items() if issubclass(t, numbers.Number)
}
builtin_other_types: TypesInModules = {
    n: t for n, t in builtin_types.items() if not issubclass(t, numbers.Number)
}

labeled_supersubs = {
    "numerics": super_sub_pairs(typing_types, builtin_numeric_types),
    "other": super_sub_pairs(typing_types, builtin_other_types),
}

for label, supersubs in labeled_supersubs.items():
    supercounts = {
        sup1: sum([1 for sup2, sub2 in supersubs if sup2 == sup1])
        for sup1, sub1 in supersubs
    }
    subcounts = {
        sub1: sum([1 for sup2, sub2 in supersubs if sub2 == sub1])
        for sup1, sub1 in supersubs
    }
    supernames = sorted(supercounts, key=supercounts.__getitem__, reverse=True)
    subnames = sorted(subcounts, key=subcounts.__getitem__, reverse=True)
    superwidth = max(map(len, supernames))
    subwidth = max(map(len, subnames))

    print("##", label)
    fmt = f"{{supername:{superwidth}}}  {{subname}}"
    for supername, subname in supersubs:
        print(fmt.format(supername=supername, subname=subname))
    print()

    if rich:
        console = rich.console.Console()
        use_x = sum(map(len, subnames)) > 60
        if use_x:
            table = rich.table.Table()
            table.add_column()
            for subname in subnames:
                table.add_column(
                    rich.text.Text(
                        "\n".join(subname.ljust(subwidth)), justify="center"
                    ),
                    justify="center",
                )
        else:
            table = rich.table.Table(show_header=False)
        for supername in supernames:
            table.add_row(
                supername,
                *[
                    (
                        ("X" if use_x else subname)
                        if (supername, subname) in supersubs
                        else ""
                    )
                    for subname in subnames
                ],
            )
        console.print(table)
        print()
