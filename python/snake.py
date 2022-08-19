from __future__ import annotations


def snake(s: str) -> str | None:
    """

    >>> snake(None) is None
    True
    >>> snake("") is None
    True
    >>> snake("    ") is None
    True
    >>> snake("!@#$") is None
    True
    >>> snake("23skidoo")
    '23skidoo'
    >>> snake("hello")
    'hello'
    >>> snake("Hello")
    'hello'
    >>> snake("HELLO")
    'hello'
    >>> snake("hello-world")
    'hello_world'
    >>> snake("HelloWorld")
    'hello_world'
    >>> snake("Hell0World")
    'hell0_world'
    >>> snake("Hello World!")
    'hello_world'
    >>> snake("Hello, World!")
    'hello_world'
    """

    from re import sub
    from unicodedata import category, normalize

    if not s:
        return None

    s = normalize("NFC", s)
    chs = []
    pch = s[0]
    pchcat = category(pch)
    if pch.islower() or pch.isnumeric():
        chs.append(pch)
    elif pch.isupper():
        chs.append(pch.lower())
    for ch in s[1:]:
        chcat = category(ch)
        match list(pchcat + chcat):
            case ["L" | "N" | "P" | "Z", _, "L", "l"] | ["L" | "N" | "P", _, "N", "d"]:
                chs.append(ch)
            case ["P" | "S" | "Z", _, "P" | "S", _]:
                pass
            case ["L" | "N" | "P" | "S" | "Z", _, "P" | "S" | "Z", _]:
                chs.append(" ")
            case ["L", "l", "L", "u"] | ["N", "d", "L", "u"]:
                chs.append(" ")
                chs.append(ch.lower())
            case ["L", "u", "L", "u"] | ["P" | "S" | "Z", _, "L", "u"]:
                chs.append(ch.lower())
            case _:
                raise ValueError("Unhandled", pchcat, chcat)
        pch = ch
        pchcat = chcat
    if not chs:
        return None
    s = "".join(chs)
    s = s.strip()
    s = sub(r"\s+", "_", s)
    return s


def main() -> None:
    from sys import stdin

    while line := stdin.readline():
        s = snake(line.strip())
        print(s if s else "")


def _devmain():
    from doctest import FAIL_FAST, testmod

    testmod(optionflags=FAIL_FAST)


if __name__ == "__main__":
    _devmain()
    main()
