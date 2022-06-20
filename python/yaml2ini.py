import numbers
import sys
import typing

import yaml
from icecream import ic
from rich import inspect as ri
from rich import print as rp


def yaml2ini(yaml_in: typing.TextIO, ini_out: typing.TextIO, sep=" = ", section="DEFAULT"):
    data = yaml.safe_load(yaml_in)
    ini = {str(key):repr(str(value)) for key,value in convert(data)}
    key_width = max(map(len,ini.keys()))
    key_format = f"{{key:{key_width}}}"
    print(f"[{section}]",file=ini_out)
    for key in sorted( ini.keys()):
        value = ini[key]
        print(key_format.format(key=key),value,sep=sep,file=ini_out)

ValueType = dict|str
def simplify_type(obj:ValueType)->str:
    if isinstance(obj, dict):
        return 'dict'
    if isinstance(obj,str):
        return 'str'
    raise TypeError("unhandled type",obj,type(obj))

def convert(data:ValueType, prefix="",joiner=".") -> typing.Generator[tuple[typing.Any, typing.Any], None, None]:
    st = simplify_type(data)
    match st:
        case 'dict':
            if prefix:
                prefix += joiner
            for k,v in data.items():
                for item in convert(data=v, prefix=f"{prefix}{k}",joiner=joiner):
                    yield item
        case 'str':
            yield (prefix, data)
        case _:
            raise StopIteration()


if __name__ == "__main__":
    yaml2ini(yaml_in=sys.stdin, ini_out=sys.stdout)
