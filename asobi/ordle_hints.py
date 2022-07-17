from __future__ import annotations

import dataclasses
import enum
import pathlib
import random
import sys
import typing

DEFAULT_WORDLISTS = list(
    filter(
        pathlib.Path.exists,
        map(
            pathlib.Path,
            [
                "/usr/share/dict/words",
            ],
        ),
    )
)


def load_words(
    paths: list[pathlib.Path],
    word_length: int | None = None,
) -> typing.Generator[str, None, None]:
    """load words

    >>> next(load_words([pathlib.Path(__file__)], word_length=27))
    'fromfutureimportannotations'
    >>> next(load_words([pathlib.Path(__file__)], word_length=8))
    'importre'
    """
    for path in paths:
        with path.open() as f:
            for line in f:
                word = "".join(map(str.lower, filter(str.isalpha, line)))
                if word_length is not None and len(word) == word_length:
                    yield word


class WordSet(set[str]):
    def discard_words_if(self, func: typing.Callable[[str], bool]) -> None:
        words_to_discard = WordSet(filter(func, self))
        self.difference_update(words_to_discard)

    def discard_words_unless(self, func: typing.Callable[[str], bool]) -> None:
        self.discard_words_if(lambda w: not func(w))

    def discard_words_that_contain_any_of_these_characters(
        self,
        characters: set[str],
    ) -> None:
        """

        >>> ws = WordSet({"abc","bcd","cde","def"})
        >>> ws.discard_words_that_contain_any_of_these_characters({"a","b"})
        >>> sorted(ws)
        ['cde', 'def']

        """

        self.discard_words_if(lambda w: bool(set(w).intersection(characters)))

    def discard_words_with_character_at_index(
        self,
        character: str,
        index: int,
    ) -> None:
        """

        >>> ws = WordSet({"aaa","abb","cac","dda","eae"})
        >>> ws.discard_words_with_character_at_index("a",1)
        >>> sorted(ws)
        ['abb', 'dda']

        """

        self.discard_words_if(lambda w: w[index] == character)

    def discard_words_without_character_at_index(
        self,
        character: str,
        index: int,
    ) -> None:
        """

        >>> ws = WordSet({"aaa","abb","cac","dda","eae"})
        >>> ws.discard_words_without_character_at_index("a",1)
        >>> sorted(ws)
        ['aaa', 'cac', 'eae']

        """

        self.discard_words_unless(lambda w: w[index] == character)

    def discard_words_that_do_not_contain_character(self, character: str) -> None:
        """

        >>> ws = WordSet({"aaa","abb","cac","dda","eae"})
        >>> ws.discard_words_that_do_not_contain_character("a")
        >>> sorted(ws)
        ['aaa', 'abb', 'cac', 'dda', 'eae']

        """

        self.discard_words_unless(lambda w: character in w)


DEFAULT_ALLOWED_WORDS = WordSet(load_words(DEFAULT_WORDLISTS, word_length=5))


class LetterScore(enum.Enum):
    CORRECT = enum.auto()
    WRONG_SPOT = enum.auto()
    NOT_IN_WORD = enum.auto()
    IGNORE = enum.auto()

    def __repr__(self) -> str:
        return self.name


CORRECT = LetterScore.CORRECT
WRONG_SPOT = LetterScore.WRONG_SPOT
NOT_IN_WORD = LetterScore.NOT_IN_WORD
IGNORE = LetterScore.IGNORE

DECODED_LETTER_SCORES = {
    "n": LetterScore.NOT_IN_WORD,
    "x": LetterScore.WRONG_SPOT,
    "y": LetterScore.CORRECT,
    "-": LetterScore.IGNORE,
}


@dataclasses.dataclass(kw_only=True)
class Game:
    """

    >>> g = Game(words=WordSet({"abc","bcd","cde","def"}))
    >>> g.alphabet
    'abcdef'
    >>> sorted(g.play(ScoredWord(word="abc",scores=[
    ...         [LetterScore.NOT_IN_WORD, LetterScore.NOT_IN_WORD, LetterScore.NOT_IN_WORD],
    ...     ])))
    ['def']

    """

    words: WordSet = dataclasses.field(default_factory=WordSet)
    alphabet: str = dataclasses.field(init=False)
    boards: list[Board] = dataclasses.field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        # ensure ownership of word set
        self.words = WordSet(self.words)
        alphaset = set()
        for word in self.words:
            alphaset.update(set(word))
        self.alphabet = "".join(sorted(alphaset))

    def play(self, scored_word: ScoredWord) -> WordSet:
        """

        >>> # de
        >>> g1x2 = Game(words=WordSet({"ab","bc","cd","de"}))
        >>> sorted(g1x2.play(ScoredWord(word="ab",scores=[
        ...         [NOT_IN_WORD, NOT_IN_WORD],
        ...     ])))
        ['cd', 'de']
        >>> sorted(g1x2.play(ScoredWord(word="bc",scores=[
        ...         [NOT_IN_WORD, NOT_IN_WORD],
        ...     ])))
        ['de']

        >>> # bcb, caa
        >>> from itertools import permutations
        >>> g2x3 = Game(words=WordSet(map(lambda t:"".join(t),permutations("aaabbbccc",3))))
        >>> sorted(g2x3.play(ScoredWord(word="abc",scores=[
        ...         [NOT_IN_WORD, WRONG_SPOT,  WRONG_SPOT],
        ...         [WRONG_SPOT,  NOT_IN_WORD, WRONG_SPOT],
        ...     ])))
        ['bcb', 'caa', 'cca', 'ccb']
        >>> sorted(g2x3.play(ScoredWord(word="ccb",scores=[
        ...         [NOT_IN_WORD, CORRECT, CORRECT],
        ...         [CORRECT, NOT_IN_WORD, NOT_IN_WORD],
        ...     ])))
        ['bcb', 'caa']

        """

        if not self.boards:
            self.boards = [Board(words=self.words) for _ in scored_word.scores]

        for si, score in enumerate(scored_word.scores):
            self.boards[si].play(scored_word.word, score)

        new_words = WordSet()
        for bd in self.boards:
            new_words.update(bd.words)
        self.words = new_words

        return self.words


@dataclasses.dataclass(kw_only=True)
class Board:
    words: WordSet = dataclasses.field(default_factory=WordSet)
    needed_characters: set[str] = dataclasses.field(default_factory=set)
    solved: bool = False
    solution: str | None = None

    def __post_init__(self) -> None:
        # ensure ownership of word set
        self.words = WordSet(self.words)

    def need(self, character: str) -> None:
        self.needed_characters.add(character)
        self.words.discard_words_that_do_not_contain_character(character)

    def needs(self, character: str) -> bool:
        return character in self.needed_characters

    def play(self, word: str, score: list[LetterScore]) -> WordSet:
        """

        >>> # de
        >>> bd = Board(words=WordSet({"ab","bc","cd","de","ef"}))
        >>> sorted(bd.play(word="ab",score=[NOT_IN_WORD,NOT_IN_WORD]))
        ['cd', 'de', 'ef']
        >>> sorted(bd.play(word="cd",score=[NOT_IN_WORD,WRONG_SPOT]))
        ['de']

        """

        if not self.solved:
            if score == [LetterScore.CORRECT] * len(word):
                self.solution = word
                self.solved = True
                self.words = WordSet()
            else:
                for i, ls in enumerate(score):
                    if ls == LetterScore.CORRECT or ls == LetterScore.WRONG_SPOT:
                        self.need(word[i])
                for i, ls in enumerate(score):
                    ch = word[i]
                    if ls == LetterScore.CORRECT:
                        self.words.discard_words_without_character_at_index(ch, i)
                    else:
                        if (
                            ls == LetterScore.NOT_IN_WORD
                            or ls == LetterScore.WRONG_SPOT
                        ):
                            self.words.discard_words_with_character_at_index(ch, i)
                        if ls == LetterScore.NOT_IN_WORD and not self.needs(ch):
                            self.words.discard_words_that_contain_any_of_these_characters(
                                set(ch)
                            )
        return self.words


@dataclasses.dataclass(kw_only=True)
class ScoredWord:
    word: str
    scores: list[list[LetterScore]]

    def characters_not_on_any_board(self):
        """

        >>> sorted(ScoredWord(word="abcd",scores=[
        ...         [LetterScore.NOT_IN_WORD] * 4,
        ...         [LetterScore.NOT_IN_WORD,LetterScore.NOT_IN_WORD,LetterScore.WRONG_SPOT,LetterScore.CORRECT],
        ...     ]).characters_not_on_any_board())
        ['a', 'b']
        >>> sorted(ScoredWord(word="abcd",scores=[
        ...         [LetterScore.CORRECT] * 4,
        ...         [LetterScore.NOT_IN_WORD,LetterScore.NOT_IN_WORD,LetterScore.WRONG_SPOT,LetterScore.CORRECT],
        ...     ]).characters_not_on_any_board())
        []

        """
        unloved = [set() for _ in self.scores]
        for si, score in enumerate(self.scores):
            for wi, ch in enumerate(self.word):
                ls = score[wi]
                if ls == LetterScore.NOT_IN_WORD:
                    unloved[si].add(ch)
        return set.intersection(*unloved)


def decode_shorthand(shorthand: str) -> ScoredWord:
    """

    >>> decode_shorthand("a:n,x,y")
    ScoredWord(word='a', scores=[[NOT_IN_WORD], [WRONG_SPOT], [CORRECT]])
    >>> decode_shorthand("abc:nn,xn,yn")
    ScoredWord(word='abc', scores=[[NOT_IN_WORD, NOT_IN_WORD], [WRONG_SPOT, NOT_IN_WORD], [CORRECT, NOT_IN_WORD]])

    """

    word, scores = shorthand.strip().lower().split(":", maxsplit=1)
    scores = list(map(str.strip, scores.split(",")))
    scores = [[DECODED_LETTER_SCORES[ls] for ls in s] for s in scores]
    return ScoredWord(word=word, scores=scores)


def main() -> None:
    args = sys.argv[1:]
    if not args:
        return

    n = 8
    g = Game(words=DEFAULT_ALLOWED_WORDS)
    for shorthand in args:
        scored_word = decode_shorthand(shorthand=shorthand)
        remaining_words = g.play(scored_word=scored_word)
        rwn = len(remaining_words)
        if rwn > n:
            remaining_words = random.sample(sorted(remaining_words), n)
        print(" ".join([str(rwn)] + sorted(remaining_words)))


if __name__ == "__main__":
    if sys.argv[1:] == ["--doctest"]:
        import doctest

        doctest.testmod(optionflags=doctest.FAIL_FAST)
    else:
        main()
