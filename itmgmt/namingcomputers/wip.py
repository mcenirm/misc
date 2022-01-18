###################################################################


def callable_with_extras(f: Callable, *extra_args, **extra_kwargs) -> Callable:
    def wrapper(*args, **kwargs):
        return f(*(args + extra_args), **{**kwargs, **extra_kwargs})

    return wrapper


def make_anchor_date_parser(format: str) -> Callable:
    def parse(anchor: bs4.element.Tag) -> datetime.date:
        return datetime.datetime.strptime(anchor["href"], format).date()

    return parse


def anchor_has_most_recent_date_as_href(
    anchors: bs4.element.ResultSet,
    *,
    anchor_date_parser: Callable,
) -> bs4.element.Tag:
    most_recent_anchor = None
    most_recent_date = None
    for anchor in anchors:
        try:
            date = anchor_date_parser(anchor)
            if most_recent_date is None or date > most_recent_date:
                most_recent_date = date
                most_recent_anchor = anchor
        except ValueError:
            continue
    return most_recent_anchor


def rule_first_anchor(anchors: bs4.element.ResultSet) -> bs4.element.Tag:
    return anchors[0]


def find_single_link_by_rule(
    url: str,
    rule: Callable,
    *,
    find_all_kwargs: dict = {},
) -> bs4.element.Tag:
    listing = requests.get(url)
    with bs4.BeautifulSoup(listing.text, "html.parser") as soup:
        matching = rule(soup.find_all("a", **find_all_kwargs))
        matches = len(matching)
        if matches == 0:
            raise MatchingLinkNotFound(
                url=url,
                html=listing.text,
            )
        elif matches > 1:
            raise MultipleLinksFound(
                url=url,
                html=listing.text,
            )
        href = matching[0]["href"]
        return urllib.parse.urljoin(top_url, href)


def get_dumps_date_url(
    *,
    top_url: str = ENWIKTIONARY_DUMPS_TOP,
    dump_date: Union[str, Callable] = "latest/",
) -> str:
    find_all_kwargs = {}
    if callable(dump_date):
        rule = ""
    else:
        rule = next
        find_all_kwargs["string"] = dump_date
    return find_single_link_by_rule(
        top_url,
        rule,
        find_all_kwargs=find_all_kwargs,
    )


def runzzz(**kwargs):
    kwargs_by_function = {
        f: {
            k: v
            for k, v in kwargs.items()
            if k in inspect.signature(f).parameters.keys()
        }
        for f in [
            download,
            foo,
            get_dumps_date_url,
        ]
    }
    if "dumps_date_url" not in kwargs:
        kwargs_by_function[foo]["dumps_date_url"] = get_dumps_date_url(
            **kwargs_by_function[get_dumps_date_url]
        )
    rich.inspect(kwargs_by_function[foo]["dumps_date_url"])
    rich.inspect(foo(**kwargs_by_function[foo]))
