from rich.console import Console
from rich.table import Table

table = Table()
table.add_column("test")
table.add_column("sep")
table.add_column("len")
table.add_column("result")
for sep in (None, "a", "b"):
    for s in ("", "a", "abc", "abcbd", "abc def"):
        v = s.split(sep)
        l = len(v)
        table.add_row(*[repr(_) for _ in (s, sep, l, v)])
console = Console()
console.print(table)
