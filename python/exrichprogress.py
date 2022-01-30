from time import sleep

import rich
from rich.progress import BarColumn, Progress, TextColumn, track
from rich.table import Column

rich.print("Basic")
for n in track(range(10), description="Processing..."):
    sleep(0.1)

rich.print("Advanced")
with Progress() as progress:

    task1 = progress.add_task("[red]Downloading...", total=1000)
    task2 = progress.add_task("[green]Processing...", total=1000)
    task3 = progress.add_task("[cyan]Cooking...", total=1000)

    while not progress.finished:
        progress.update(task1, advance=0.5)
        progress.update(task2, advance=0.3)
        progress.update(task3, advance=0.9)
        sleep(0.02)

rich.print("Table")
text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
bar_column = BarColumn(bar_width=None, table_column=Column(ratio=2))
progress = Progress(text_column, bar_column, expand=True)

with progress:
    for n in progress.track(range(100)):
        progress.print(n)
        sleep(0.1)
