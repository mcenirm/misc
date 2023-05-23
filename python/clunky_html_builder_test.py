import itertools
import typing
import unittest

import clunky_html_builder as chb


# fmt: off
class HtmlFake1(chb.HtmlElement): ...
class Fake2(chb.HtmlElement): ...
class Fake3(chb.HtmlVoidElement): ...
# fmt: on


class TestHtml(unittest.TestCase):
    def assert_chunks(
        self,
        expected_chunks: typing.Sequence[str],
        test_element: chb.HtmlElement,
        *,
        indent: str | None = None,
        islice_start: int = 0,
        islice_stop: int | None = None,
        islice_step: int = 1,
    ):
        gen = test_element.chunks(indent=indent)
        actual_chunks = itertools.islice(
            gen,
            islice_start,
            islice_stop,
            islice_step,
        )
        expected_list = list(expected_chunks)
        actual_list = list(actual_chunks)
        self.assertListEqual(
            expected_list,
            actual_list,
        )

    def test_tags(self):
        for expected, actual in [
            ("html", chb.Html()),
            ("fake1", HtmlFake1()),
            ("fake2", Fake2()),
            ("fake3", Fake3()),
        ]:
            with self.subTest(msg=actual.__class__.__name__):
                self.assertEqual(expected, actual.tag)

    def test_children(self):
        with self.subTest("void element"):
            self.assertListEqual([], Fake3().children)
        with self.subTest("void element error if children"):
            with self.assertRaises(ValueError):
                Fake3()["text"]
        with self.subTest("no children"):
            self.assertListEqual([], Fake2().children)
        with self.subTest("one text child"):
            self.assertListEqual(["text"], Fake2()["text"].children)
        with self.subTest("two text children"):
            self.assertListEqual(
                ["line 1", "line 2"], Fake2()["line 1", "line 2"].children
            )

    def test_chunks_without_children(self):
        for expected, actual in [
            (["<fake1></fake1>"], HtmlFake1()),
            (["<fake2></fake2>"], Fake2()),
            (["<fake3>"], Fake3()),
            (
                ['<fake2 a="1" b="2" c="" d></fake2>'],
                Fake2({"a": "1", "b": 2, "c": "", "d": None}),
            ),
            (["<fake3 a b>"], Fake3({"b": None, "a": None})),
        ]:
            msg = ", ".join(
                [
                    actual.tag,
                    f"{len(actual.attrs)} attrs",
                ]
            )
            with self.subTest(msg=msg):
                self.assert_chunks(expected, actual)

    def test_chunks_with_children(self):
        for expected, actual in [
            (["<fake1>", "<fake2></fake2>", "</fake1>"], HtmlFake1()[Fake2()]),
        ]:
            msg = ", ".join(
                [
                    actual.tag,
                    f"{len(actual.attrs)} attrs",
                    f"{len(actual.children)} children",
                ]
            )
            with self.subTest(msg=msg):
                self.assert_chunks(expected, actual)

    def test_chunks_indent(self):
        indent = "  "
        with self.subTest("no children"):
            self.assert_chunks(
                ["<fake1></fake1>"],
                HtmlFake1(),
                indent=indent,
            )
        with self.subTest("one text child"):
            self.assert_chunks(
                ["<fake1>text</fake1>"],
                HtmlFake1()["text"],
                indent=indent,
            )
        with self.subTest("three text children"):
            self.assert_chunks(
                ["<fake1>", "  line 1", "  line 2", "  line 3", "</fake1>"],
                HtmlFake1()["line 1", "line 2", "line 3"],
                indent=indent,
            )
        with self.subTest("one empty element child"):
            self.assert_chunks(
                ["<fake1>", "  <fake2></fake2>", "</fake1>"],
                HtmlFake1()[Fake2()],
                indent=indent,
            )
        with self.subTest("one void element child"):
            self.assert_chunks(
                ["<fake1>", "  <fake3>", "</fake1>"],
                HtmlFake1()[Fake3()],
                indent=indent,
            )
        with self.subTest("three levels"):
            self.assert_chunks(
                [
                    "<div>",
                    "  text 1",
                    "  <div>",
                    "    text 2",
                    "    <div>",
                    "      text 3",
                    "      <br>",
                    "      text 4",
                    "    </div>",
                    "    text 5",
                    "  </div>",
                    "  text 6",
                    "</div>",
                ],
                chb.Div()[
                    "text 1",
                    chb.Div()[
                        "text 2",
                        chb.Div()[
                            "text 3",
                            chb.Br(),
                            "text 4",
                        ],
                        "text 5",
                    ],
                    "text 6",
                ],
                indent=indent,
            )
