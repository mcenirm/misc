import builtins
import keyword
import unicodedata


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

    words = guess_words(s)
    words = [w.lower() for w in words if w.isalnum()]
    if not words:
        return None
    return "_".join(words)


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


def _devmain():
    from doctest import FAIL_FAST, testmod

    testmod(optionflags=FAIL_FAST)


if __name__ == "__main__":
    _devmain()
