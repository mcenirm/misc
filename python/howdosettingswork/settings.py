import logging
from typing import Type


class Setting:
    def __init__(self, *args, **kwargs) -> None:
        self._args = args
        self._kwargs = kwargs

    def _oof(self, method, **kwargs):
        prefix = "Setting: " + method + ": "
        logging.info(prefix + "----")
        logging.info(prefix + "self: " + repr(self))
        logging.info(prefix + "      " + repr(dir(self)))
        for k, v in kwargs.items():
            logging.info(prefix + str(k) + ": " + repr(v))
        logging.info(prefix + "----")

    def __get__(self, instance, owner=None):
        self._oof("__get__", inst=instance, ownr=owner)

    def __set__(self, instance, value):
        self._oof("__set__", inst=instance, valu=value)

    def __delete__(self, instance):
        self._oof("__delete__", inst=instance)

    def __repr__(self) -> str:
        return "Setting(" + repr(self.__dict__) + ")"



class SettingsMeta:
    pass

class Settings(metaclass=SettingsMeta):
    pass

def setting(attrname, *, default=None,*args, **kwargs):
    def incite(c: Type[Settings]):
        c._add_setting(attrname, default=default, *args, **kwargs)
        return c
    return incite


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if True:

        @setting("example", 42, a=1, b=2)
        class FooSettings:
            pass

        debug(FooSettings)
        debug([_ for _ in dir(FooSettings) if not _.startswith("_")])
    else:

        class FooSettings:
            a = Setting()

        s = FooSettings()
        x = s.a
        s.a = 11
        del s.a
        print(x, s.a, s)
