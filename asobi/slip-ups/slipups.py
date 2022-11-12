from __future__ import annotations

from abc import ABCMeta, abstractmethod
from codecs import getwriter
from dataclasses import dataclass, field
from enum import IntFlag
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from random import randint
from sys import argv
from typing import Generator
from webbrowser import open as wbopen

from icecream import ic


class SlipUpsRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        print(self.path)

        shorthand = self.path.removeprefix("/")
        state = state_from_shorthand(shorthand)
        game = Game(state=state)
        adjacents = list(game.adjacent_states())

        encoding = "utf-8"
        outlines = [
            "HTTP/1.1 200 OK",
            f"content-type: text/html; charset={encoding}",
            "",
            "<!doctype html>",
            "<html><body>",
        ]
        try:
            if state.columns:
                max_column_height = max(map(len, state.columns))
                if max_column_height:
                    outlines += [
                        "<table>",
                    ]
                    try:
                        row_lines = []
                        for row_index in range(max_column_height):
                            row_parts = [
                                escape(repr(column[row_index]))
                                if len(column) > row_index
                                else "&nbsp;"
                                for column in state.columns
                            ]
                            row_lines.append(
                                "<tr>"
                                + "".join(
                                    ["<td>" + part + "</td>" for part in row_parts]
                                )
                                + "</tr>"
                            )
                    finally:
                        outlines += [
                            "</table>",
                        ]
            else:
                outlines += [
                    "<table><tr><td>&nbsp;</td></tr></table>",
                ]
            if adjacents:
                outlines += [
                    "<ul>",
                ]
                try:
                    outlines += [
                        f"<li><a href='{state_as_shorthand(adj)}'>{escape(state_as_shorthand(adj))}</a></li>"
                        for adj in adjacents
                    ]
                finally:
                    outlines += [
                        "</ul>",
                    ]
            else:
                outlines += [
                    "<p>No adjacent states</p>",
                ]
        finally:
            outlines += [
                "</body></html>",
            ]

        out = getwriter(encoding)(self.wfile)
        out.writelines([_ + "\n" for _ in outlines])


class Connection(IntFlag):
    """Indicate that a connection is active in that direction.

    >>> for c in Connection:
    ...     c
    ...
    AFTER
    BEFORE
    CONTRACT
    EXPAND
    """

    AFTER = 1
    BEFORE = 2
    CONTRACT = 4
    EXPAND = 8

    def __repr__(self) -> str:
        return self.name

    def as_tile_glyph(self) -> str:
        return "".join(
            [
                "E" if self & Connection.EXPAND else "-",
                "C" if self & Connection.CONTRACT else "-",
                "B" if self & Connection.BEFORE else "-",
                "A" if self & Connection.AFTER else "-",
            ]
        )


_TILE_GLYPHS = {i: Connection(i).as_tile_glyph() for i in range(16)}


@dataclass(kw_only=True, frozen=True)
class Tile:
    connections: Connection

    @classmethod
    def random(cls) -> Tile:
        connections = Connection(randint(0, 15))
        return Tile(connections=connections)

    def __repr__(self) -> str:
        return f"<Tile:{_TILE_GLYPHS[self.connections]}>"
        # "═║╔╗╚╝╠╣╦╩╬"


@dataclass(frozen=True, kw_only=True)
class State:
    columns: list[list[Tile]] = field(default_factory=list)
    queue: list[Tile] = field(default_factory=list)


class StateChanger(metaclass=ABCMeta):
    @abstractmethod
    def adjacent_states(self, state: State) -> Generator[State, None, None]:
        ...


class DefaultStateChanger(StateChanger):
    def adjacent_states(self, state: State) -> Generator[State, None, None]:
        """
        >>> t0 = Tile(connections=Connection(0x0))
        >>> t1 = Tile(connections=Connection(0x1))
        >>> dsc = DefaultStateChanger()

        >>> list(dsc.adjacent_states(State()))
        [State(columns=[], queue=[])]

        >>> for adj in dsc.adjacent_states(State(queue=[t0,t1])):
        ...     adj
        State(columns=[[<Tile:---->]], queue=[<Tile:---A>])
        State(columns=[[], [<Tile:---->]], queue=[<Tile:---A>])
        """

        if not state.queue:
            yield state
        else:
            next_tile, *remainder = state.queue
            for i, c in enumerate(state.columns):
                new_columns = [list(_) for _ in state.columns]
                new_columns[i].insert(0, next_tile)
                yield State(
                    columns=new_columns,
                    queue=list(remainder),
                )
            yield State(
                columns=state.columns + [[next_tile]],
                queue=list(remainder),
            )


@dataclass(kw_only=True, frozen=False)
class Game:
    state: State = field(default_factory=State)
    state_changer: StateChanger = field(default_factory=DefaultStateChanger)

    def adjacent_states(self) -> Generator[State, None, None]:
        for adj in self.state_changer.adjacent_states(self.state):
            yield adj


_SHORTHAND_HEX_TO_TILE = dict(
    x=None,
    **{
        hex(i)[2:].lower(): Tile(
            connections=Connection(i),
        )
        for i in range(16)
    },
)
_SHORTHAND_TILE_TO_HEX = {
    None: "x",
    **{Tile(connections=Connection(i)): hex(i)[2:].lower() for i in range(16)},
}


def state_from_shorthand(shorthand: str) -> State:
    """Return a State based on the shorthand string.

    >>> state_from_shorthand("")
    State(columns=[], queue=[])

    >>> state_from_shorthand("17-f3-a")
    State(columns=[[<Tile:ECBA>, <Tile:--BA>], [<Tile:E-B->]], queue=[<Tile:---A>, <Tile:-CBA>])

    >>> state_from_shorthand("0")
    State(columns=[], queue=[<Tile:---->])

    >>> state_from_shorthand("1")
    State(columns=[], queue=[<Tile:---A>])

    >>> state_from_shorthand("2")
    State(columns=[], queue=[<Tile:--B->])

    >>> state_from_shorthand("3")
    State(columns=[], queue=[<Tile:--BA>])

    >>> state_from_shorthand("4")
    State(columns=[], queue=[<Tile:-C-->])

    >>> state_from_shorthand("8")
    State(columns=[], queue=[<Tile:E--->])

    >>> state_from_shorthand("f")
    State(columns=[], queue=[<Tile:ECBA>])

    >>> state_from_shorthand("1234")
    State(columns=[], queue=[<Tile:---A>, <Tile:--B->, <Tile:--BA>, <Tile:-C-->])

    >>> state_from_shorthand("f-1234")
    State(columns=[[<Tile:---A>, <Tile:--B->, <Tile:--BA>, <Tile:-C-->]], queue=[<Tile:ECBA>])

    >>> state_from_shorthand("0-12-3")
    State(columns=[[<Tile:---A>, <Tile:--B->], [<Tile:--BA>]], queue=[<Tile:---->])
    """

    if not shorthand:
        return State()
    shorthand_parts = shorthand.split("-")
    queue, *columns = [
        [_SHORTHAND_HEX_TO_TILE[tilehex] for tilehex in tilehexes]
        for tilehexes in shorthand_parts
    ]
    return State(columns=columns, queue=queue)


def state_as_shorthand(state: State) -> str:
    """Return a shorthand for state.

    >>> t0 = Tile(connections=Connection(0x0))
    >>> t1 = Tile(connections=Connection(0x1))
    >>> t2 = Tile(connections=Connection(0x2))
    >>> t3 = Tile(connections=Connection(0x3))
    >>> t4 = Tile(connections=Connection(0x4))
    >>> t7 = Tile(connections=Connection(0x7))
    >>> t8 = Tile(connections=Connection(0x8))
    >>> ta = Tile(connections=Connection(0xa))
    >>> tf = Tile(connections=Connection(0xf))

    >>> state_as_shorthand(State(queue=[]))
    ''

    >>> state_as_shorthand(State(columns=[[tf, t3], [ta]], queue=[t1, t7]))
    '17-f3-a'

    >>> state_as_shorthand(State(queue=[t0]))
    '0'

    >>> state_as_shorthand(State(queue=[t1]))
    '1'

    >>> state_as_shorthand(State(queue=[t2]))
    '2'

    >>> state_as_shorthand(State(queue=[t3]))
    '3'

    >>> state_as_shorthand(State(queue=[t4]))
    '4'

    >>> state_as_shorthand(State(queue=[t8]))
    '8'

    >>> state_as_shorthand(State(queue=[tf]))
    'f'

    >>> state_as_shorthand(State(queue=[t1, t2, t3, t4]))
    '1234'

    >>> state_as_shorthand(State(columns=[[t1, t2, t3, t4]], queue=[tf]))
    'f-1234'

    >>> state_as_shorthand(State(columns=[[t1, t2], [t3]], queue=[t0]))
    '0-12-3'
    """

    shorthand_parts = [
        "".join([_SHORTHAND_TILE_TO_HEX[tile] for tile in tilelist])
        for tilelist in [state.queue, *state.columns]
    ]
    return "-".join(shorthand_parts)


if __name__ == "__main__":
    if argv[1:] == ["--doctest"]:
        import doctest

        doctest.testmod(optionflags=doctest.FAIL_FAST)
    else:
        site = "localhost"
        s = ThreadingHTTPServer(
            server_address=(site, 0),
            RequestHandlerClass=SlipUpsRequestHandler,
        )
        initial_state = State(
            columns=[[Tile.random()]],
            queue=[
                Tile.random(),
                Tile.random(),
            ],
        )
        url = f"http://{site}:{s.server_port}/" + state_as_shorthand(initial_state)
        wbopen(url=url)
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            ...
