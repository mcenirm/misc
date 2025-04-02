import builtins
import keyword


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
