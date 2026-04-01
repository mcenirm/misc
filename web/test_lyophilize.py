from __future__ import annotations

import pathlib

import pytest

from lyophilize import extract_links, same_origin, url_to_local_path, save_response


# ---------------------------------------------------------------------------
# extract_links
# ---------------------------------------------------------------------------

class TestExtractLinks:
    def test_absolute_href(self):
        html = '<a href="https://example.com/page">link</a>'
        assert extract_links("https://example.com/", html) == ["https://example.com/page"]

    def test_relative_href_resolved(self):
        html = '<a href="/about">about</a>'
        assert extract_links("https://example.com/home", html) == ["https://example.com/about"]

    def test_fragment_stripped(self):
        html = '<a href="/page#section">link</a>'
        assert extract_links("https://example.com/", html) == ["https://example.com/page"]

    def test_all_supported_tags(self):
        html = """
        <a href="/a"></a>
        <link href="/b.css">
        <script src="/c.js"></script>
        <img src="/d.png">
        <source src="/e.mp4">
        <video src="/f.mp4"></video>
        <audio src="/g.mp3"></audio>
        <iframe src="/h.html"></iframe>
        """
        links = extract_links("https://example.com/", html)
        assert links == [
            "https://example.com/a",
            "https://example.com/b.css",
            "https://example.com/c.js",
            "https://example.com/d.png",
            "https://example.com/e.mp4",
            "https://example.com/f.mp4",
            "https://example.com/g.mp3",
            "https://example.com/h.html",
        ]

    def test_empty_html(self):
        assert extract_links("https://example.com/", "") == []

    def test_tag_with_no_relevant_attr(self):
        html = '<div class="foo"></div>'
        assert extract_links("https://example.com/", html) == []

    def test_anchor_missing_href(self):
        html = '<a name="anchor">text</a>'
        assert extract_links("https://example.com/", html) == []

    def test_duplicate_links_preserved(self):
        html = '<a href="/page">1</a><a href="/page">2</a>'
        result = extract_links("https://example.com/", html)
        assert result == ["https://example.com/page", "https://example.com/page"]


# ---------------------------------------------------------------------------
# same_origin
# ---------------------------------------------------------------------------

class TestSameOrigin:
    def test_same_scheme_and_host(self):
        assert same_origin("https://example.com/a", "https://example.com/b") is True

    def test_different_scheme(self):
        assert same_origin("https://example.com/", "http://example.com/") is False

    def test_different_host(self):
        assert same_origin("https://example.com/", "https://other.com/") is False

    def test_subdomain_is_different_origin(self):
        assert same_origin("https://example.com/", "https://sub.example.com/") is False

    def test_same_host_different_port(self):
        assert same_origin("https://example.com:443/", "https://example.com:8443/") is False

    def test_identical_urls(self):
        assert same_origin("https://example.com/page", "https://example.com/page") is True


# ---------------------------------------------------------------------------
# url_to_local_path
# ---------------------------------------------------------------------------

class TestUrlToLocalPath:
    def test_bare_origin(self, tmp_path):
        result = url_to_local_path(tmp_path, "https://example.com")
        assert result == tmp_path / "example.com" / "index.html"

    def test_trailing_slash(self, tmp_path):
        result = url_to_local_path(tmp_path, "https://example.com/dir/")
        assert result == tmp_path / "example.com" / "dir" / "index.html"

    def test_path_without_extension(self, tmp_path):
        result = url_to_local_path(tmp_path, "https://example.com/about")
        assert result == tmp_path / "example.com" / "about" / "index.html"

    def test_path_with_extension(self, tmp_path):
        result = url_to_local_path(tmp_path, "https://example.com/style.css")
        assert result == tmp_path / "example.com" / "style.css"

    def test_nested_path_with_extension(self, tmp_path):
        result = url_to_local_path(tmp_path, "https://example.com/assets/app.js")
        assert result == tmp_path / "example.com" / "assets" / "app.js"

    def test_query_string_ignored(self, tmp_path):
        # Query strings are not part of the path; path portion has no suffix
        result = url_to_local_path(tmp_path, "https://example.com/search?q=foo")
        assert result == tmp_path / "example.com" / "search" / "index.html"


# ---------------------------------------------------------------------------
# save_response
# ---------------------------------------------------------------------------

class TestSaveResponse:
    def test_creates_file_with_content(self, tmp_path):
        url = "https://example.com/page"
        content = b"<html>hello</html>"
        local = save_response(tmp_path, url, content)
        assert local.exists()
        assert local.read_bytes() == content

    def test_creates_parent_directories(self, tmp_path):
        url = "https://example.com/a/b/c.html"
        save_response(tmp_path, url, b"data")
        assert (tmp_path / "example.com" / "a" / "b" / "c.html").exists()

    def test_returns_correct_path(self, tmp_path):
        url = "https://example.com/img/logo.png"
        local = save_response(tmp_path, url, b"\x89PNG")
        assert local == tmp_path / "example.com" / "img" / "logo.png"

    def test_overwrites_existing_file(self, tmp_path):
        url = "https://example.com/page"
        save_response(tmp_path, url, b"old content")
        save_response(tmp_path, url, b"new content")
        local = url_to_local_path(tmp_path, url)
        assert local.read_bytes() == b"new content"
