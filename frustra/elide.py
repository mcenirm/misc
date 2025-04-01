__all__ = ["elide_repr", "elide_str"]

import sys


def elide_repr(obj, maxlen=60, endlen=6, ellipsis_="...") -> str:
    """

    >>> elide_repr(None) == repr(None)
    True
    >>> elide_repr(1) == repr(1)
    True
    >>> elide_repr("test") == repr("test")
    True
    >>> elide_repr("testtesttest",maxlen=8,endlen=2)
    "'te...t'"
    >>> elide_repr(Ellipsis)
    'Ellipsis'
    >>> elide_repr(list(range(10)),maxlen=12,endlen=3)
    '[0, 1,... 9]'

    """

    return elide_str(repr(obj), maxlen=maxlen, endlen=endlen, ellipsis_=ellipsis_)


def elide_str(s: str, maxlen=60, endlen=6, ellipsis_="...") -> str:
    """

    >>> elide_str(None)
    >>> elide_str("test")
    'test'
    >>> elide_str("abcdefghij", maxlen=10)
    'abcdefghij'
    >>> elide_str("abcdefghijk", maxlen=10,endlen=0)
    'abcdefg...'
    >>> elide_str("abcdefghijk", maxlen=10,endlen=1)
    'abcdef...k'
    >>> elide_str("abcdefghijk", maxlen=10,endlen=2)
    'abcde...jk'

    """

    if s is None:
        return None
    s = str(s)
    elide_len = maxlen - len(ellipsis_)
    if len(s) > maxlen:
        s = s[: elide_len - endlen] + ellipsis_ + (s[-endlen:] if endlen > 0 else "")
    return s


def main():
    for arg in sys.argv[1:]:
        print(elide_str(arg))


if __name__ == "__main__":
    if sys.argv[1:] == ["--doctest"]:
        import doctest

        doctest.testmod(optionflags=doctest.FAIL_FAST)
    else:
        main()
