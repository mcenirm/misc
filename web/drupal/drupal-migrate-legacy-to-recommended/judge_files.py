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
import os
import pathlib
import subprocess
import sys
import traceback
import types
import typing

import dacite

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
    core: bool | None = None
    libraries: bool | None = None
    modules: bool | None = None
    profiles: bool | None = None
    themes: bool | None = None
    unexpected: bool | None = None


@dataclasses.dataclass
class FileMetadata:
    size_bytes: int | None = None
    mtime_utc: datetime.datetime | None = None

    def set_from_path(self, path: pathlib.Path):
        if path.exists():
            st = path.stat(follow_symlinks=False)
            self.size_bytes = st.st_size
            self.mtime_utc = datetime.datetime.fromtimestamp(
                int(st.st_mtime),
                tz=datetime.timezone.utc,
            ).replace(tzinfo=None)


@dataclasses.dataclass
class ValueJudgment(Qualities, SomethingThatHasARelativePath):
    added: bool | None = None
    changed: bool | None = None
    custom: bool | None = None
    drifted: bool | None = None
    missing: bool | None = None

    actual: FileMetadata = dataclasses.field(default_factory=FileMetadata)
    expected: FileMetadata = dataclasses.field(default_factory=FileMetadata)

    library: str | None = None
    module: str | None = None
    profile: str | None = None
    theme: str | None = None
    package_guess: str | None = None
    legacy_version: str | None = None
    recommended_version: str | None = None

    def __post_init__(self):
        if not isinstance(self.actual, FileMetadata):
            self.actual = FileMetadata(**self.actual)
        if not isinstance(self.expected, FileMetadata):
            self.expected = FileMetadata(**self.expected)


############################################################


@dataclasses.dataclass
class ComposerPackageUrl:
    type: str | None = None
    url: str | None = None


@dataclasses.dataclass
class ComposerPackageAuthor:
    name: str | None = None
    email: str | None = None
    homepage: str | None = None
    role: str | None = None


@dataclasses.dataclass
class ComposerPackageAutoload:
    classmap: list[str] | None = None
    exclude_from_classmap: list[str] | None = None
    files: list[str] | None = None
    psr_0: dict[str, str] | None = None
    psr_4: dict[str, str | list[str]] | None = None


@dataclasses.dataclass
class ComposerPackageDist(ComposerPackageUrl):
    reference: str | None = None
    shasum: str | None = None


@dataclasses.dataclass
class ComposerPackageSource(ComposerPackageUrl):
    reference: str | None = None


@dataclasses.dataclass
class ComposerPackageSupport:
    chat: str | None = None
    docs: str | None = None
    documentation: str | None = None
    email: str | None = None
    forum: str | None = None
    irc: str | None = None
    issues: str | None = None
    rss: str | None = None
    security: str | None = None
    slack: str | None = None
    source: str | None = None
    wiki: str | None = None


@dataclasses.dataclass
class ComposerPackageRepository:
    type: str
    url: str


@dataclasses.dataclass
class ComposerPackageConfig:
    sort_packages: bool | None = None
    allow_plugins: dict[str, bool] | None = None


@dataclasses.dataclass
class ComposerPackage:
    config: ComposerPackageConfig | None = None
    conflict: dict[str, str] | None = None
    description: str | None = None
    extra: dict[str, typing.Any] | None = None
    homepage: str | None = None
    license: str | list[str] | None = None
    minimum_stability: str | None = None
    name: str | None = None
    prefer_stable: bool | None = None
    repositories: list[ComposerPackageRepository] | None = None
    require: dict[str, str] | None = None
    require_dev: dict[str, str] | None = None
    support: ComposerPackageSupport | None = None
    type: str | None = None

    def __post_init__(self):
        if isinstance(self.license, str):
            self.license = [self.license]


@dataclasses.dataclass
class ComposerPackageLocked(ComposerPackage):
    abandoned: bool | str | None = None
    authors: list[ComposerPackageAuthor] | None = None
    autoload: ComposerPackageAutoload | None = None
    bin: list[str] | None = None
    dist: ComposerPackageDist | None = None
    funding: list[ComposerPackageUrl] | None = None
    include_path: list[str] | None = None
    keywords: list[str] | None = None
    notification_url: str | None = None
    provide: dict[str, str] | None = None
    replace: dict[str, str] | None = None
    scripts: dict[str, list[str]] | None = None
    source: ComposerPackageSource | None = None
    suggest: dict[str, str] | None = None
    time: str | None = None
    version: str | None = None


@dataclasses.dataclass
class ComposerPackageInstalled(ComposerPackageLocked):
    install_path: str | None = None
    installation_source: str | None = None
    version_normalized: str | None = None


@dataclasses.dataclass
class ComposerLock:
    _readme: list[str] | None = None
    aliases: list[str] | None = None
    content_hash: str | None = None
    minimum_stability: str | None = None
    packages: list[ComposerPackageLocked] | None = None
    packages_dev: list[ComposerPackageLocked] | None = None
    platform: dict[str, str] | None = None
    platform_dev: dict[str, str] | None = None
    platform_overrides: dict[str, str] | None = None
    plugin_api_version: str | None = None
    prefer_lowest: bool | None = None
    prefer_stable: bool | None = None
    stability_flags: dict[str, int] | None = None


@dataclasses.dataclass
class ComposerInstalled:
    dev: bool | None = None
    dev_package_names: list[str] | None = None
    packages: list[ComposerPackageInstalled] | None = None


class ComposerProject:
    def __init__(
        self,
        project_dir: pathlib.Path,
        composer_json_name: str = "composer.json",
        composer_lock_name: str = "composer.lock",
        composer_installed_name: str = "vendor/composer/installed.json",
    ) -> None:
        self.project_dir = pathlib.Path(project_dir)
        self.composer_json_file = self.project_dir / composer_json_name
        self.composer_lock_file = self.project_dir / composer_lock_name
        self.composer_installed_file = self.project_dir / composer_installed_name
        self.package = from_composer_file(ComposerPackage, self.composer_json_file)
        self.lock = from_composer_file(ComposerLock, self.composer_lock_file)
        self.installed = from_composer_file(
            ComposerInstalled, self.composer_installed_file
        )

        self._installed_name_to_pkg: dict[str, ComposerPackageInstalled] = {}
        self._install_prefix_to_name: dict[str, str] = {}
        if self.installed.packages:
            for pkg in self.installed.packages:
                if pkg.name:
                    if pkg.name in self._installed_name_to_pkg:
                        raise NotImplementedError(
                            "installed package name conflict",
                            pkg.name,
                            self._installed_name_to_pkg[pkg.name],
                            pkg,
                            self.composer_installed_file,
                        )
                    else:
                        self._installed_name_to_pkg[pkg.name] = pkg
                if pkg.install_path:
                    prefix = self.composer_installed_file.parent / pkg.install_path
                    # "...\home\vendor\composer\../../web/core"

                    prefix = pathlib.Path(os.path.normpath(prefix))
                    # "...\home\web\core"

                    prefix = prefix.relative_to(self.project_dir)
                    # "web\core"

                    prefix = prefix.as_posix() + "/"
                    # "web/core/"

                    if prefix in self._install_prefix_to_name:
                        raise NotImplementedError(
                            "installed package install_path conflict",
                            prefix,
                            self._install_prefix_to_name[prefix].name,
                            pkg.name,
                            self.composer_installed_file,
                        )
                    else:
                        self._install_prefix_to_name[prefix] = pkg.name

    def get_installed_package_by_name(
        self,
        package_name: str,
    ) -> ComposerPackageInstalled | None:
        if package_name is None:
            return None
        return self._installed_name_to_pkg.get(package_name)

    def guess_package(self, relative_path: str) -> str | None:
        if relative_path is None:
            return None
        candidates = [
            (prefix, pkgname)
            for prefix, pkgname in self._install_prefix_to_name.items()
            if relative_path.startswith(prefix)
        ]
        if not candidates:
            return None
        if len(candidates) == 1:
            prefix, pkgname = candidates[0]
            return pkgname
        raise NotImplementedError(
            "too many candidate packages for install path",
            relative_path,
            *candidates,
        )


def from_composer_file[T](cls: type[T], path: pathlib.Path) -> T:
    path = pathlib.Path(path)
    if path.exists():
        data = json.loads(path.read_bytes())
    else:
        data = {}
    data = composer_json_keys_to_python_identifiers(data)
    try:
        return dacite.from_dict(
            data_class=cls,
            data=data,
            config=dacite.Config(
                type_hooks={
                    dict: empty_list_to_dict,
                    dict[str, str]: empty_list_to_dict,
                    dict[str, int]: empty_list_to_dict,
                },
                cast=[],
                forward_references=None,
                check_types=True,
                strict=True,
                strict_unions_match=False,
                convert_key=convert_key_composer_json_to_python_identifiers,
            ),
        )
    except dacite.UnexpectedDataError as ude:
        exctype, excobj, tb = sys.exc_info()
        data_class_stack: list[types.FrameType] = []
        while tb:
            fl = tb.tb_frame.f_locals
            if fl and "data_class" in fl:
                data_class_stack.append(fl["data_class"])
            tb = tb.tb_next
        raise NotImplementedError(
            *traceback.format_exception_only(ude),
            "----------",
            *ude.keys,
            "----------",
            *data_class_stack,
            "----------",
        )


def empty_list_to_dict(value):
    if isinstance(value, list) and not value:
        value = {}
    return value


def convert_key_composer_json_to_python_identifiers(key: str) -> str:
    return key.replace("-", "_")


def composer_json_keys_to_python_identifiers(data):
    if isinstance(data, dict):
        return {
            convert_key_composer_json_to_python_identifiers(
                k
            ): composer_json_keys_to_python_identifiers(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [composer_json_keys_to_python_identifiers(item) for item in data]
    return data


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
            c.core = True
        elif parts[0] == "libraries":
            c.libraries = True
            # TODO identify library
        elif parts[0] == "modules":
            c.modules = True
            # TODO identify module
        elif parts[0] == "profiles":
            c.profiles = True
            # TODO identify profile
        elif parts[0] == "themes":
            c.themes = True
            # TODO identify theme
        elif parts[0] == "vendor":
            c.vendor = True
            # TODO identify package
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
        return c


@dataclasses.dataclass
class Judgments:
    judgments: dict[str, ValueJudgment] = dataclasses.field(default_factory=dict)

    def load_judgments_csv(self, judgments_csv: pathlib.Path):
        judgments_csv = pathlib.Path(judgments_csv)
        with judgments_csv.open("r", encoding="utf-8", newline=None) as f:
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

    def save_judgments_csv(self, judgments_csv):
        judgments_csv = pathlib.Path(judgments_csv)
        with judgments_csv.open("w", encoding="utf-8", newline=None) as f:
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
        if contestant_file.exists and role_model_file.exists:
            vj.changed = vj.expected.size_bytes != vj.actual.size_bytes
            vj.drifted = vj.expected.mtime_utc != vj.actual.mtime_utc

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
    if legacy.package.name is None:
        raise NotImplementedError(
            "could not find name of legacy project",
            legacy.composer_json_file,
        )

    recommended = ComposerProject(recommended_dir)
    if recommended.package.name is None:
        if recommended_dir.is_dir() and list(recommended_dir.iterdir()):
            raise NotImplementedError(
                "recommended project directory should be empty",
                recommended_dir,
            )
        for p in legacy.lock.packages or []:
            if p.name == "drupal/core":
                legacy_locked_version = p.version
                break
        else:
            raise NotImplementedError(
                "unable to extract drupal/core version",
                legacy.composer_lock_file,
            )
        subprocess.check_call(
            [
                "composer",
                "create-project",
                f"drupal/recommended-project:{legacy_locked_version}",
                str(recommended_dir),
                "--ignore-platform-reqs",
                "--no-ansi",
                "--no-interaction",
            ],
            universal_newlines=True,
        )
        recommended = ComposerProject(recommended_dir)

    leg_cfier = LegacyClassifier()
    leg_cfications = {rp: leg_cfier.classify(rp) for rp in relative_walk(legacy_dir)}
    rec_cfier = RecommendedClassifier(web_relative=recommended_web_relative)
    rec_cfications = {
        rp: rec_cfier.classify(rp) for rp in relative_walk(recommended_dir)
    }

    judgments = Judgments()
    if judgments_csv.exists():
        judgments.load_judgments_csv(judgments_csv)

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
            judgments.compare(leg_relpath, leg_file, rec_file)
        else:
            rec_quals = Qualities()
            judgments.added(leg_relpath, leg_file)

        judgments.qualities(
            leg_relpath,
            dataclasses.replace(
                leg_quals,
                **{k: v for k, v in rec_quals.__dict__.items() if v is not None},
            ),
        )
        vj = judgments[leg_relpath]

        leg_guessed_name = legacy.guess_package(leg_relpath)
        rec_guessed_name = recommended.guess_package(rec_relpath)
        vj.package_guess = leg_guessed_name or rec_guessed_name or None

        if leg_guessed_name:
            if vj.libraries:
                vj.library = leg_guessed_name
            if vj.modules:
                vj.module = leg_guessed_name
            if vj.profiles:
                vj.profile = leg_guessed_name
            if vj.themes:
                vj.theme = leg_guessed_name

        leg_guess = legacy.get_installed_package_by_name(leg_guessed_name)
        if leg_guess:
            vj.legacy_version = leg_guess.version

        rec_guess = recommended.get_installed_package_by_name(rec_guessed_name)
        if rec_guess:
            vj.recommended_version = rec_guess.version

    for rec_relpath, rec_quals in rec_cfications.items():
        rec_file = recommended_dir / rec_relpath
        judgments.missing(rec_relpath, rec_file)
        judgments.qualities(rec_relpath, rec_quals)

    if judgments_csv.exists():
        judgments_csv.rename(judgments_csv.with_suffix(".bak"))
    judgments.save_judgments_csv(judgments_csv)


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
