from __future__ import annotations

import argparse
import collections
import collections.abc
import csv
import dataclasses
import datetime
import fnmatch
import functools
import inspect
import json
import operator
import pathlib
import traceback
import types
import typing


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
    unexpected: bool | None = None

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


class TypeHintHelper:
    def __init__(self, typehint) -> None:
        if typehint is None:
            raise TypeError("typehint should not be None")
        self._hint = typehint
        self._hint_origin = typing.get_origin(typehint)
        self._hint_args = typing.get_args(typehint)
        if type(self._hint) in (typing.Optional, typing.Union):
            typelist = [t for t in self._hint_args if t is not type(None)]
            self._type = functools.reduce(operator.or_, typelist)
        elif type(self._hint) is type:
            self._type = self._hint
        else:
            self._type = self._hint_origin
        self._origin = typing.get_origin(self._type)
        self._args = typing.get_args(self._type)
        if self._origin is list:
            self._item_helpers = [TypeHintHelper(a) for a in self._args]
        elif self._origin is dict and len(self._args) == 2:
            self._item_helpers = [TypeHintHelper(self._args[1])]
        else:
            self._item_helpers = []

    def cast(self, value):
        if value is None:
            return None
        if isinstance(value, bool) and self._type is bool:
            return value
        if isinstance(value, str) and self._type is str:
            return value
        if isinstance(value, str) and (self._type is list or self._origin is list):
            return [value]
        if isinstance(value, dict) and (self._type is dict or self._origin is dict):
            castdict = {}
            for k, item1 in value.items():
                for helper in self._item_helpers:
                    item2 = helper.cast(item1)
                    if item2 is not None:
                        castdict[k] = item2
                        break
                else:
                    castdict[k] = item1
            return castdict
        if isinstance(value, dict) and hasattr(self._type, "from_dict"):
            return self._type.from_dict(value)
        if isinstance(value, list) and self._origin is list:
            castlist = []
            for item1 in value:
                for helper in self._item_helpers:
                    item2 = helper.cast(item1)
                    if item2 is not None:
                        castlist.append(item2)
                        break
                else:
                    castlist.append(item1)
            return castlist
        raise NotImplementedError(
            "unhandled type pairing",
            self._hint,
            self._hint_origin,
            self._hint_args,
            "-----",
            self._type,
            self._origin,
            self._args,
            "-----",
            value,
        )


@dataclasses.dataclass
class _FromDict:
    @classmethod
    def from_dict(cls, data: dict) -> typing.Self:
        if not isinstance(data, dict):
            raise NotImplementedError(
                "expected dict",
                type(data).__name__,
                "for dataclass",
                cls.__name__,
            )
        typehints = {
            k: TypeHintHelper(v) for k, v in typing.get_type_hints(cls).items()
        }
        kwargs = {}
        for fld in dataclasses.fields(cls):
            if fld.name in data:
                inname = fld.name
            else:
                inname = fld.name.replace("_", "-")
            if inname in data:
                invalue = data.pop(inname)
                hint = typehints[fld.name]
                value = hint.cast(invalue)
                kwargs[fld.name] = value
        if data:
            raise NotImplementedError(
                "unhandled keys for dataclass",
                cls.__name__,
                *data.items(),
            )
        return cls(**kwargs)


############################################################


@dataclasses.dataclass
class ComposerPackageSupport(_FromDict):
    docs: str | None = None
    chat: str | None = None
    issues: str | None = None
    source: str | None = None


@dataclasses.dataclass
class ComposerPackageRepository(_FromDict):
    type: str
    url: str


@dataclasses.dataclass
class ComposerPackageConfig(_FromDict):
    sort_packages: bool | None = None
    allow_plugins: dict[str, bool] | None = None


@dataclasses.dataclass
class ComposerPackage(_FromDict):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    license: list[str] | None = None
    homepage: str | None = None
    support: ComposerPackageSupport | None = None
    repositories: list[ComposerPackageRepository] | None = None
    require: dict[str, str] | None = None
    conflict: dict[str, str] | None = None
    minimum_stability: str | None = None
    prefer_stable: bool | None = None
    config: ComposerPackageConfig | None = None
    extra: dict | None = None
    require_dev: dict[str, str] | None = None

    @classmethod
    def from_path(cls, path: pathlib.Path) -> ComposerPackage:
        path = pathlib.Path(path)
        if path.exists():
            data = json.loads(path.read_bytes())
        else:
            data = {}
        return cls.from_dict(data)


@dataclasses.dataclass
class ComposerLock(ComposerPackage):
    _readme: list[str] | None = None
    content_hash: str | None = None
    packages: list[ComposerPackage] | None = None


class ComposerProject:
    def __init__(
        self,
        project_dir: pathlib.Path,
        composer_json_name: str = "composer.json",
        composer_lock_name: str = "composer.lock",
    ) -> None:
        self.project_dir = pathlib.Path(project_dir)
        self.composer_json_file = self.project_dir / composer_json_name
        self.composer_lock_file = self.project_dir / composer_lock_name
        self.package = ComposerPackage.from_path(self.composer_json_file)
        self.lock = ComposerLock.from_path(self.composer_lock_file)


############################################################


class Classifier:
    def classify(self, relpath: str) -> Qualities:
        c = Qualities()
        parts = relpath.split("/")
        if not parts:
            raise NotImplementedError(
                "expected a relative path",
                relpath,
                type(self).__name__,
            )
        if parts[0] == "sites":
            c.sites = True
            if len(parts) > 2:
                if parts[1] == "default":
                    if len(parts) > 3:
                        if parts[2] == "files":
                            c.sites_files = True
                        else:
                            raise TODO(
                                *parts,
                                "sites default but not files",
                            )
                    elif parts[2] in {
                        "settings.php",
                    } or any(
                        fnmatch.fnmatch(parts[2], pat)
                        for pat in [
                            "default.*.yml",
                            "default.*.php",
                        ]
                    ):
                        ...
                    else:
                        raise TODO(
                            *parts,
                            "sites default but no subdir?",
                        )
                else:
                    raise NotImplementedError(
                        "unexpected sites subdirectory",
                        relpath,
                    )
        elif parts[0] == "core":
            ...
        elif parts[0] == "libraries":
            ...
        elif parts[0] == "modules":
            ...
        elif parts[0] == "profiles":
            ...
        elif parts[0] == "themes":
            ...
        elif parts[0] == "vendor":
            ...
        elif parts[0] in {
            "images",
            "jqueryFileTree",
        }:
            c.unexpected = True
        elif len(parts) == 1:
            pass
        else:
            raise TODO(*parts)
        return c


class LegacyClassifier(Classifier):
    def __init__(self):
        super().__init__()


class RecommendedClassifier(Classifier):
    def __init__(self, web_relative: str = "web/"):
        super().__init__()
        self.web_relative = str(web_relative).rstrip("/") + "/"

    def classify(self, relpath) -> Qualities:
        c = super().classify(relpath.removeprefix(self.web_relative))
        if relpath.startswith(self.web_relative):
            c.web = True
            relpath.removeprefix(self.web_relative)
        return c


@dataclasses.dataclass
class Judgements:
    judgments: dict[str, ValueJudgment] = dataclasses.field(default_factory=dict)

    def load_judgments_csv(self, judgements_csv: pathlib.Path):
        judgements_csv = pathlib.Path(judgements_csv)
        with judgements_csv.open("r", encoding="utf-8", newline=None) as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                self.judgments[row["relative_path"]] = ValueJudgment(
                    **unflatten_dict(
                        {
                            k: (
                                True
                                if k != "relative_path" and "." not in k and v == k
                                else v
                            )
                            for k, v in row.items()
                        }
                    )
                )

    def save_judgments_csv(self, judgements_csv):
        judgements_csv = pathlib.Path(judgements_csv)
        with judgements_csv.open("w", encoding="utf-8", newline=None) as f:
            wrtr = csv.DictWriter(
                f,
                flatten_dict(
                    dataclasses.asdict(ValueJudgment(None))  # type: ignore
                ).keys(),
            )
            wrtr.writeheader()
            for rp in sorted(self.judgments):
                vj = self.judgments[rp]
                wrtr.writerow(
                    {
                        k: (k if isinstance(v, bool) and v else v)
                        for k, v in flatten_dict(dataclasses.asdict(vj)).items()
                    }
                )

    def __getitem__(self, key):
        if not isinstance(key, str):
            raise NotImplementedError(
                "expected str",
                key,
            )
        if key not in self.judgments:
            self.judgments[key] = ValueJudgment(relative_path=pathlib.Path(key))
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
            vj.drifted = True

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


def judge_files(
    judgments_csv: pathlib.Path,
    legacy_dir: pathlib.Path,
    recommended_dir: pathlib.Path,
    recommended_web_relative: str = "web/",
):
    judgments_csv = pathlib.Path(judgments_csv)
    legacy_dir = pathlib.Path(legacy_dir)
    recommended_dir = pathlib.Path(recommended_dir)
    recommended_web_relative = recommended_web_relative.rstrip("/") + "/"

    recommended_web_dir = recommended_dir / recommended_web_relative

    legacy = ComposerProject(legacy_dir)
    recommended = ComposerProject(recommended_dir)

    if not recommended_dir.is_dir():
        raise TODO(
            "determine drupal version from legacy",
            "and then construct new recommended using the same version",
            legacy.package.name,
        )

    leg_cfier = LegacyClassifier()
    leg_cfications = {rp: leg_cfier.classify(rp) for rp in relative_walk(legacy_dir)}
    rec_cfier = RecommendedClassifier(web_relative=recommended_web_relative)
    rec_cfications = {
        rp: rec_cfier.classify(rp) for rp in relative_walk(recommended_dir)
    }

    judgements = Judgements()
    if judgments_csv.exists():
        judgements.load_judgments_csv(judgments_csv)

    for leg_relpath, leg_quals in leg_cfications.items():
        leg_file = legacy_dir / leg_relpath
        rec_relpath = leg_relpath
        rec_relpath, rec_dir = (
            (rec_relpath, recommended_dir)
            if rec_relpath in rec_cfications
            else (
                (_rec_web_relpath, recommended_web_dir)
                if (_rec_web_relpath := recommended_web_relative + leg_relpath)
                in rec_cfications
                else (None, None)
            )
        )
        if rec_relpath in rec_cfications:
            rec_quals = rec_cfications.pop(rec_relpath)
            rec_file = rec_dir / rec_relpath  # type: ignore
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
        rec_file = recommended_dir / rec_relpath
        judgements.missing(rec_relpath, rec_file)
        judgements.qualities(rec_relpath, rec_quals)

    if judgments_csv.exists():
        judgments_csv.rename(judgments_csv.with_suffix(".bak"))
    judgements.save_judgments_csv(judgments_csv)


############################################################


def argument_parser_from_function(
    f: collections.abc.Callable[..., typing.Any],
) -> argparse.ArgumentParser:
    s = inspect.signature(f)
    h = typing.get_type_hints(f)
    _ = h.pop("return", None)
    ap = argparse.ArgumentParser(
        description=f.__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    for n, t in h.items():
        opt = "--" + n.replace("_", "-")
        kw = dict(type=t)
        if s.parameters[n].default is not inspect.Parameter.empty:
            kw["default"] = s.parameters[n].default
            kw["help"] = n.replace("_", " ")
        ap.add_argument(opt, **kw)
    return ap


def meighn(
    actual_function: collections.abc.Callable,
    args: list[str] | None = None,
):
    ap = argument_parser_from_function(actual_function)
    ns = ap.parse_args(args).__dict__
    try:
        return actual_function(**ns)
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


class TODO(NotImplementedError): ...


if __name__ == "__main__":
    meighn(judge_files)
