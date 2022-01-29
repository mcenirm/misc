from dataclasses import dataclass, field
from random import choice
from time import sleep

from tqdm import tqdm


@dataclass
class MultipleRandomTQDMBars:
    total: int = 100
    maxbars: int = 5
    bars: list[tqdm] = field(default_factory=list)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for bar in self.bars:
            bar.close()

    def _appendbar(self) -> tqdm:
        nbars = len(self.bars)
        bar = tqdm(total=self.total, position=nbars, desc=str(nbars))
        self.bars.append(bar)
        return bar

    def update(self) -> None:
        if not self.bars:
            self._appendbar()
            self._appendbar()
        bar = choice(self.bars)
        if bar == self.bars[0]:
            bar = self._appendbar()
        self.bars[0].update()
        bar.update()


if __name__ == "__main__":
    x = MultipleRandomTQDMBars()
    with x:
        for i in range(x.total):
            x.update()
            sleep(0.1)
