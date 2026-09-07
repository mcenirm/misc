from __future__ import annotations

import collections
import collections.abc
import csv
import dataclasses
import datetime
import difflib
import pathlib
import sys
import traceback
import typing

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
JUDGMENT_CSV = OUT / "judgement.csv"


WEBSITE_ROOT = HERE.parent.parent
DRUPAL_URL_PATH = "home"
LEGACY_ROOT = WEBSITE_ROOT / "html_ssl" / DRUPAL_URL_PATH
LEGACY_WEB = LEGACY_ROOT
RECOMMENDED_ROOT = WEBSITE_ROOT / ("drupal-" + DRUPAL_URL_PATH.replace("/", "-"))
RECOMMENDED_WEB = RECOMMENDED_ROOT / "web"


############################################################


complained = False
for label, path in [
    ("Website root", WEBSITE_ROOT),
    ("Legacy root", LEGACY_ROOT),
    ("Legacy web", LEGACY_WEB),
    ("Recommended root", RECOMMENDED_ROOT),
    ("Recommended web", RECOMMENDED_WEB),
]:
    if not path.is_dir():
        print("!!", "directory does not exist:", path)
        complained = True

if complained:
    sys.exit(1)


############################################################


@dataclasses.dataclass
class SomethingThatHasARelativePath:
    relative_path: pathlib.Path


@dataclasses.dataclass
class Qualities:
    vendor: bool | None = None
    web: bool | None = None
    sites: bool | None = None
    sites_files: bool | None = None
    modules: bool | None = None
    themes: bool | None = None
    libraries: bool | None = None
    site: str | None = None
    module: str | None = None
    theme: str | None = None
    library: str | None = None
    installed_package: str | None = None


@dataclasses.dataclass
class FileMetadata:
    size_bytes: int | None = None
    mtime: datetime.datetime | None = None

    def set_from_path(self, path: pathlib.Path):
        if path.exists():
            st = path.stat(follow_symlinks=False)
            self.size_bytes = st.st_size
            self.mtime = datetime.datetime.fromtimestamp(
                st.st_mtime, tz=datetime.timezone.utc
            )


@dataclasses.dataclass
class ValueJudgment(Qualities, SomethingThatHasARelativePath):
    added: bool | None = None
    changed: bool | None = None
    custom: bool | None = None
    drifted: bool | None = None
    missing: bool | None = None
    actual: FileMetadata = dataclasses.field(default_factory=FileMetadata)
    expected: FileMetadata = dataclasses.field(default_factory=FileMetadata)

    def __post_init__(self):
        if not isinstance(self.actual, FileMetadata):
            self.actual = FileMetadata(**self.actual)
        if not isinstance(self.expected, FileMetadata):
            self.expected = FileMetadata(**self.expected)


############################################################


class Classifier:
    def classify(self, relpath: str) -> Qualities:
        c = Qualities()
        return c


class LegacyClassifier(Classifier):
    def __init__(self):
        super().__init__()


class RecommendedClassifier(Classifier):
    def __init__(self, web_relative: str = "web/"):
        super().__init__()
        self.web_relative = str(web_relative).rstrip("/") + "/"

    def classify(self, relpath) -> Qualities:
        c = super().classify(relpath)
        if relpath.startswith(self.web_relative):
            c.web = True
            relpath.removeprefix(self.web_relative)
        return c


@dataclasses.dataclass
class Judgements:
    judgments: dict[str, ValueJudgment] = dataclasses.field(default_factory=dict)

    def load_judgments_csv(self, judgements_csv=JUDGMENT_CSV):
        with judgements_csv.open("r", encoding="utf-8", newline=None) as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                self.judgments[row["relative_path"]] = ValueJudgment(
                    **unflatten_dict(row)
                )

    def save_judgments_csv(self, judgements_csv=JUDGMENT_CSV):
        with judgements_csv.open("w", encoding="utf-8", newline=None) as f:
            wrtr = csv.DictWriter(
                f,
                flatten_dict(
                    dataclasses.asdict(ValueJudgment(relative_path=""))
                ).keys(),
            )
            wrtr.writeheader()
            for rp in sorted(self.judgments):
                vj = self.judgments[rp]
                wrtr.writerow(flatten_dict(dataclasses.asdict(vj)))

    def __getitem__(self, key):
        if not isinstance(key, str):
            raise NotImplementedError(
                "expected str",
                key,
            )
        if key not in self.judgments:
            self.judgments[key] = ValueJudgment(relative_path=key)
        return self.judgments[key]

    def added(self, relpath: str, contestant_file: pathlib.Path):
        vj = self[relpath]
        vj.added = True
        vj.actual.set_from_path(contestant_file)

    def missing(self, relpath: str, role_model_file: pathlib.Path):
        vj = self[relpath]
        vj.missing = True
        vj.expected.set_from_path(role_model_file)

    def compare(
        self, relpath: str, contestant_file: pathlib.Path, role_model_file: pathlib.Path
    ):
        vj = self[relpath]
        vj.actual.set_from_path(contestant_file)
        vj.expected.set_from_path(role_model_file)
        if vj.expected.size_bytes != vj.actual.size_bytes:
            vj.changed = True
        if vj.expected.mtime != vj.actual.mtime:
            vj.drift = True

    def qualities(self, relpath: str, q: Qualities):
        vj = self[relpath]
        for k, v in q.__dict__.items():
            if v is not None:
                setattr(vj, k, v)


def relative_walk(start: pathlib.Path) -> collections.abc.Generator[str, None, None]:
    for root, dirs, files in start.walk(
        top_down=True, on_error=None, follow_symlinks=False
    ):
        rr = root.relative_to(start)
        if rr.is_absolute():
            raise NotImplementedError(
                "unexpected absolute for relative path",
                start,
                root,
                rr,
            )
        for f in files:
            yield (rr / f).as_posix()


def just_files(start: pathlib.Path) -> dict[pathlib.Path, pathlib.Path]:
    return set(
        sorted(
            root / n
            for root, _, files in start.walk(
                top_down=False, on_error=None, follow_symlinks=False
            )
            for n in files
        )
    )


def just_dirs(start: pathlib.Path) -> set[pathlib.Path]:
    return set(
        sorted(
            root
            for root, _, _ in start.walk(
                top_down=False, on_error=None, follow_symlinks=False
            )
        )
    )


def flatten_dict(d: dict, sep: str = ".", parent_key: str = "") -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.extend(flatten_dict(v, sep=sep, parent_key=new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: dict, sep: str = ".") -> dict:
    result = {}
    for key, value in d.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return result


def main(
    judgment_csv: pathlib.Path = JUDGMENT_CSV,
    legacy_dir: pathlib.Path = LEGACY_WEB,
    recommended_root_dir: pathlib.Path = RECOMMENDED_ROOT,
    recommended_web_dir: pathlib.Path = RECOMMENDED_WEB,
):
    leg_cfier = LegacyClassifier()
    leg_cfications = {rp: leg_cfier.classify(rp) for rp in relative_walk(legacy_dir)}
    web_relative = recommended_web_dir.relative_to(recommended_root_dir)
    rec_cfier = RecommendedClassifier(web_relative=web_relative)
    rec_cfications = {
        rp: rec_cfier.classify(rp) for rp in relative_walk(recommended_root_dir)
    }

    judgements = Judgements()
    if judgment_csv.exists():
        judgements.load_judgments_csv()

    for leg_relpath, leg_quals in leg_cfications.items():
        leg_file = legacy_dir / leg_relpath
        rec_relpath = leg_relpath
        rec_relpath, rec_dir = (
            (rec_relpath, recommended_root_dir)
            if rec_relpath in rec_cfications
            else (
                (_rec_web_relpath, recommended_web_dir)
                if (_rec_web_relpath := str(web_relative / leg_relpath))
                in rec_cfications
                else (None, None)
            )
        )
        if rec_relpath in rec_cfications:
            rec_quals = rec_cfications.pop(rec_relpath)
            rec_file = rec_dir / rec_relpath
            judgements.compare(leg_relpath, leg_file, rec_file)
        else:
            rec_quals = Qualities()
            judgements.added(leg_relpath, leg_file)

        judgements.qualities(
            leg_relpath,
            dataclasses.replace(
                leg_quals,
                **{k: v for k, v in rec_quals.__dict__.items() if v is not None},
            ),
        )

    for rec_relpath, rec_quals in rec_cfications.items():
        rec_file = recommended_root_dir / rec_relpath
        judgements.missing(rec_relpath, rec_file)
        judgements.qualities(rec_relpath, rec_quals)

    if judgment_csv.exists():
        judgment_csv.rename(judgment_csv.with_suffix(".bak"))
    judgements.save_judgments_csv()


class TODO(NotImplementedError): ...


if __name__ == "__main__":
    try:
        main()
    except NotImplementedError as e:
        print(type(e).__name__)
        for a in e.args:
            r = a
            if r is not None:
                r = repr(r)
                if "\n" in r:
                    r = repr(str(a))
                r = r[:80]
            print(" ●", r)
        print()
        print(traceback.format_exception(e)[-2])
        print()
