from __future__ import annotations

from codecs import getwriter
from dataclasses import dataclass
from enum import Enum, auto
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        adjacents = list(state.adjacent_states())

        encoding = "utf-8"
        outlines = [
            "HTTP/1.1 200 OK",
            f"content-type: text/html; charset={encoding}",
            "",
            "<!doctype html>",
            "<html><body>",
        ]
        try:
            outlines += [
                f"<p>HELLO, {escape(str(state.tile.name))}</p>",
            ]
            if adjacents:
                outlines += [
                    "<ul>",
                ]
                try:
                    outlines += [
                        f"<li><a href='{state_as_shorthand(adj)}'>{adj.tile.name}</a></li>"
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


class Tile(Enum):
    ONE = auto()
    TWO = auto()


@dataclass(frozen=True, kw_only=True)
class State:
    tile: Tile
    # TODO
    # * board of tiles
    # * next tile (or queue of next tiles)
    # * maybe put adjacent_state logic in separate classes?

    def adjacent_states(self) -> Generator[State, None, None]:
        if self.tile == Tile.ONE:
            yield State(tile=Tile.TWO)
        if self.tile == Tile.TWO:
            yield State(tile=Tile.ONE)


def state_from_shorthand(shorthand: str) -> State:
    return State(tile=Tile(int(shorthand)))


def state_as_shorthand(state: State) -> str:
    return str(state.tile.value)


if __name__ == "__main__":
    site = "localhost"
    s = ThreadingHTTPServer(
        server_address=(site, 0),
        RequestHandlerClass=SlipUpsRequestHandler,
    )
    initial_state = State(tile=Tile.ONE)
    url = f"http://{site}:{s.server_port}/" + state_as_shorthand(initial_state)
    wbopen(url=url)
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        ...
