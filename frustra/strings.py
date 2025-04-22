import builtins
import functools
import keyword
import typing
import unicodedata


@functools.cache
def str_to_identifier(s: str, lowercase=True) -> str:
    if s is None:
        return None
    s = str(s)
    if s == "":
        return "_"
    if lowercase:
        s = s.lower()
    s = s.replace(" ", "_")
    s = s.replace("-", "_")
    while keyword.iskeyword(s) or s in dir(builtins):
        s = s + "_"
    return s


# Cc  Control
# Cf  Format
# Ll  Lowercase   Letter
# Lm  Modifier    Letter
# Lo  Other       Letter
# Lt  Titlecase   Letter
# Lu  Uppercase   Letter
# Mc  Spacing     Mark
# Me  Enclosing   Mark
# Mn  Nonspacing  Mark
# Nd  Decimal     Number
# Nl  Letter      Number
# No  Other       Number
# Pc  Connector   Punctuation
# Pd  Dash        Punctuation
# Pe  Close       Punctuation
# Pf  Final       Punctuation
# Pi  Initial     Punctuation
# Po  Other       Punctuation
# Ps  Open        Punctuation
# Sc  Currency    Symbol
# Sk  Modifier    Symbol
# Sm  Math        Symbol
# So  Other       Symbol
# Zl  Line        Separator
# Zp  Paragraph   Separator
# Zs  Space       Separator
_EQUIVALENCE_CLASSES = {
    "Cc": "Separator",
    "Cf": "Separator",
    "Ll": "Lower",
    "Lm": "Lower",
    "Lo": "Lower",
    "Lt": "Upper",
    "Lu": "Upper",
    "Mc": "Mark",
    "Me": "Mark",
    "Mn": "Mark",
    "Nd": "Lower",
    "Nl": "Lower",
    "No": "Lower",
    "Pc": "Punctuation",
    "Pd": "Punctuation",
    "Pe": "Punctuation",
    "Pf": "Punctuation",
    "Pi": "Punctuation",
    "Po": "Punctuation",
    "Ps": "Punctuation",
    "Sc": "Punctuation",
    "Sk": "Punctuation",
    "Sm": "Punctuation",
    "So": "Punctuation",
    "Zl": "Separator",
    "Zp": "Separator",
    "Zs": "Separator",
}


@functools.cache
def guess_words(s: str) -> list[str]:
    """

    >>> guess_words(None)
    []
    >>> guess_words("")
    []
    >>> guess_words("    ")
    []
    >>> guess_words("!@#$ %^&*")
    ['!@#$', '%^&*']
    >>> guess_words("23skidoo")
    ['23skidoo']
    >>> guess_words("23Skidoo")
    ['23', 'Skidoo']
    >>> guess_words("hello")
    ['hello']
    >>> guess_words("Hello")
    ['Hello']
    >>> guess_words("HELLO")
    ['HELLO']
    >>> guess_words("hello-world")
    ['hello', '-', 'world']
    >>> guess_words("hello_world")
    ['hello', '_', 'world']
    >>> guess_words("HELLOWorld")
    ['HELLO', 'World']
    >>> guess_words("HelloWorld")
    ['Hello', 'World']
    >>> guess_words("Hell0World")
    ['Hell0', 'World']
    >>> guess_words("Hello World!")
    ['Hello', 'World', '!']
    >>> guess_words("Hello, World!")
    ['Hello', ',', 'World', '!']
    """

    if s is None:
        return []
    s = str(s)
    if s == "":
        return []
    s = unicodedata.normalize("NFC", s)

    eqvlist = list(map(_EQUIVALENCE_CLASSES.get, map(unicodedata.category, s)))
    wordstartlist = [True] + [False] * (len(s) - 1) + [True]
    for i in range(1, len(s)):
        eqv = eqvlist[i]
        preveqv = eqvlist[i - 1]
        if eqv == "Upper" and preveqv == "Lower":
            # aB -> a B
            wordstartlist[i] = True
        elif (
            eqv == "Upper"
            and preveqv == "Upper"
            and i + 1 < len(s)
            and eqvlist[i + 1] == "Lower"
        ):
            # ABc -> A Bc
            wordstartlist[i] = True
        elif eqv in {"Upper", "Lower"} and preveqv in {"Upper", "Lower"}:
            # ab -> ab
            pass
        elif eqv in {"Upper", "Lower"} and preveqv not in {"Upper", "Lower"}:
            # @b -> @ b
            wordstartlist[i] = True
        elif eqv != preveqv:
            # simple cases of changes
            wordstartlist[i] = True

    wordstartindexlist = [i for i, ws in enumerate(wordstartlist) if ws]
    wordlist = []
    # raise Exception("++", s, wordstartindexlist)
    start = wordstartindexlist[0]
    for end in wordstartindexlist[1:]:
        if eqvlist[start] != "Separator":
            word = s[start:end]
            wordlist.append(word)
        start = end
    return wordlist


def _snake_or_CONSTANT_case(
    s: str,
    strmethod: typing.Callable[[str], str],
) -> str | None:
    words = guess_words(s)
    words = [strmethod(w) for w in words if w.isalnum()]
    if not words:
        return None
    return "_".join(words)


@functools.cache
def snake_case(s: str) -> str | None:
    """

    >>> snake_case(None)
    >>> snake_case("")
    >>> snake_case("    ")
    >>> snake_case("!@#$")
    >>> snake_case("23skidoo")
    '23skidoo'
    >>> snake_case("hello")
    'hello'
    >>> snake_case("Hello")
    'hello'
    >>> snake_case("HELLO")
    'hello'
    >>> snake_case("hello-world")
    'hello_world'
    >>> snake_case("HelloWorld")
    'hello_world'
    >>> snake_case("Hell0World")
    'hell0_world'
    >>> snake_case("Hello World!")
    'hello_world'
    >>> snake_case("Hello, World!")
    'hello_world'
    """

    return _snake_or_CONSTANT_case(s, str.lower)


@functools.cache
def CONSTANT_CASE(s: str) -> str | None:
    """

    >>> CONSTANT_CASE(None)
    >>> CONSTANT_CASE("")
    >>> CONSTANT_CASE("    ")
    >>> CONSTANT_CASE("!@#$")
    >>> CONSTANT_CASE("23skidoo")
    '23SKIDOO'
    >>> CONSTANT_CASE("hello")
    'HELLO'
    >>> CONSTANT_CASE("Hello")
    'HELLO'
    >>> CONSTANT_CASE("HELLO")
    'HELLO'
    >>> CONSTANT_CASE("hello-world")
    'HELLO_WORLD'
    >>> CONSTANT_CASE("HelloWorld")
    'HELLO_WORLD'
    >>> CONSTANT_CASE("Hell0World")
    'HELL0_WORLD'
    >>> CONSTANT_CASE("Hello World!")
    'HELLO_WORLD'
    >>> CONSTANT_CASE("Hello, World!")
    'HELLO_WORLD'
    """

    return _snake_or_CONSTANT_case(s, str.upper)


@functools.cache
def camelCase(s: str) -> str | None:
    """

    >>> camelCase(None)
    >>> camelCase("")
    >>> camelCase("    ")
    >>> camelCase("!@#$ %^&*")
    >>> camelCase("23skidoo")
    '23skidoo'
    >>> camelCase("23Skidoo")
    '23Skidoo'
    >>> camelCase("hello")
    'hello'
    >>> camelCase("Hello")
    'hello'
    >>> camelCase("HELLO")
    'hello'
    >>> camelCase("hello-world")
    'helloWorld'
    >>> camelCase("hello_world")
    'helloWorld'
    >>> camelCase("HELLOWorld")
    'helloWorld'
    >>> camelCase("HelloWorld")
    'helloWorld'
    >>> camelCase("Hell0World")
    'hell0World'
    >>> camelCase("Hello World!")
    'helloWorld'
    >>> camelCase("Hello, World!")
    'helloWorld'
    """

    word = PascalCase(s)
    if not word:
        return None
    word = word[0].lower() + word[1:]
    return word


@functools.cache
def PascalCase(s: str) -> str | None:
    """

    >>> PascalCase(None)
    >>> PascalCase("")
    >>> PascalCase("    ")
    >>> PascalCase("!@#$ %^&*")
    >>> PascalCase("23skidoo")
    '23skidoo'
    >>> PascalCase("23Skidoo")
    '23Skidoo'
    >>> PascalCase("hello")
    'Hello'
    >>> PascalCase("Hello")
    'Hello'
    >>> PascalCase("HELLO")
    'Hello'
    >>> PascalCase("hello-world")
    'HelloWorld'
    >>> PascalCase("hello_world")
    'HelloWorld'
    >>> PascalCase("HELLOWorld")
    'HelloWorld'
    >>> PascalCase("HelloWorld")
    'HelloWorld'
    >>> PascalCase("Hell0World")
    'Hell0World'
    >>> PascalCase("Hello World!")
    'HelloWorld'
    >>> PascalCase("Hello, World!")
    'HelloWorld'
    """

    words = guess_words(s)
    words = [w.capitalize() for w in words if w.isalnum()]
    if not words:
        return None
    return "".join(words)


@functools.cache
def repr_str_with_double_quotes(s: str) -> str:
    r"""

    >>> s = None ; repr(s) ; repr_str_with_double_quotes(s)
    'None'
    'None'
    >>> s = "None" ; repr(s) ; repr_str_with_double_quotes(s)
    "'None'"
    '"None"'
    >>> s = "" ; repr(s) ; repr_str_with_double_quotes(s)
    "''"
    '""'
    >>> s = "'" ; repr(s) ; repr_str_with_double_quotes(s)
    '"\'"'
    '"\'"'
    >>> s = '"' ; repr(s) ; repr_str_with_double_quotes(s)
    '\'"\''
    '"\\""'
    >>> s = "\"'" ; repr(s) ; repr_str_with_double_quotes(s)
    '\'"\\\'\''
    '"\\"\'"'
    >>> s = "\n" ; repr(s) ; repr_str_with_double_quotes(s)
    "'\\n'"
    '"\\n"'

    """
    if s is None:
        return repr(None)
    s = str(s)
    r = repr(s)
    if r.startswith('"'):
        return r
    return '"' + r[1:-1].replace("\\'", "'").replace('"', '\\"') + '"'


def _devmain():
    from doctest import FAIL_FAST, testmod

    testmod(optionflags=FAIL_FAST)


if __name__ == "__main__":
    _devmain()
