EXPORT_NS = "http://www.mediawiki.org/xml/export-0.10/"

FORMAT = "format"
MEDIAWIKI = "mediawiki"
MODEL = "model"
PAGE = "page"
TEXT = "text"
TITLE = "title"

SKIPS = set(
    [
        MEDIAWIKI,
        "siteinfo",
        "sitename",
        "dbname",
        "base",
        "generator",
        "case",
        "namespaces",
        "namespace",
        PAGE,
        "ns",
        "id",
        "revision",
        "parentid",
        "timestamp",
        "contributor",
        "username",
        "minor",
        "sha1",
        "comment",
        "ip",
    ]
)
EXPECTING_TEXT_TAGS = set(
    [
        TITLE,
        MODEL,
        FORMAT,
        TEXT,
    ]
)

WIKITEXT_MODEL = "wikitext"
WIKITEXT_FORMAT = "text/x-wiki"
