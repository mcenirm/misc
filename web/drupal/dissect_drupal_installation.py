from __future__ import annotations

import argparse
import dataclasses
import os
import pathlib
import subprocess

import platformdirs
from icecream import ic  # type: ignore


@dataclasses.dataclass(frozen=True)
class PathDetails:
    x: pathlib.Path

    @classmethod
    def from_path(cls, p: pathlib.Path) -> PathDetails:
        return cls(
            x=p,
        )


@dataclasses.dataclass(frozen=True)
class FileDetails(PathDetails):
    @classmethod
    def from_path(cls, p):
        return super().from_path(p)


FileDetailsDict = dict[str, FileDetails]


@dataclasses.dataclass(frozen=True)
class DirectoryDetails(PathDetails):
    @classmethod
    def from_path(cls, p):
        return super().from_path(p)


DirectoryDetailsDict = dict[str, DirectoryDetails]


def dissect_drupal_installation(
    drupal_root: pathlib.Path,
    download_cache: pathlib.Path,
):
    directories, files = scan_drupal_installation(drupal_root)
    v = detect_drupal_version(files)
    ic(v)
    xxx


def scan_drupal_installation(
    drupal_root: pathlib.Path,
) -> tuple[DirectoryDetailsDict, FileDetailsDict]:
    drupal_root = pathlib.Path(drupal_root).absolute()

    directories: dict[str, DirectoryDetails] = {}
    files: dict[str, FileDetails] = {}
    for dirpath, dirnames, filenames, dirfd in os.fwalk(
        top=drupal_root,
        topdown=False,
        # onerror=None,
        follow_symlinks=False,
        # dir_fd=None,
    ):
        this_dir_path = pathlib.Path(dirpath).absolute()
        this_dir = DirectoryDetails.from_path(this_dir_path)
        this_dir_relative_path = this_dir_path.relative_to(drupal_root)
        directories[this_dir_relative_path.as_posix()] = this_dir
        for filename in filenames:
            this_file_path = this_dir_path / filename
            this_file = FileDetails.from_path(this_file_path)
            files[(this_dir_relative_path / filename).as_posix()] = this_file
    ic(len(directories))
    ic(len(files))
    return directories, files


D7_BOOTSTRAP = "includes/bootstrap.inc"


def detect_drupal_version(
    files: FileDetailsDict,
) -> str | None:
    if D7_BOOTSTRAP in files:
        bootstrap = files[D7_BOOTSTRAP]
        v = run_php_r(
            [
                f'require "{bootstrap.x.absolute()}";',
                "echo VERSION;",
            ]
        )
        return v
    else:
        # TODO Drupal 8+
        return None


def run_php_r(code: str | list[str]) -> None:
    if isinstance(code, list):
        code = " ".join(code)
    command = ["php", "-r", code]
    out = subprocess.check_output(command, text=True)
    return out


def drupal_download_url_for_version(v: str, ext: str = ".tar.gz") -> str:
    if v is None:
        return None
    v = v.strip()
    if v.startswith("7."):
        return f"https://ftp.drupal.org/files/projects/drupal-{v}{ext}"
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Determine origins for each file in a Drupal installation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "drupal_root",
        metavar="DRUPAL_ROOT",
        help="path to top folder of Drupal installation",
        default=".",
    )
    ap.add_argument(
        "--download-cache",
        "-c",
        help="path to download cache folder",
        default=platformdirs.user_cache_dir(appname=pathlib.Path(__file__).stem),
    )
    ns = ap.parse_args()
    ic(ns)
    drupal_root = pathlib.Path(ns.drupal_root)
    download_cache = pathlib.Path(ns.download_cache)
    dissect_drupal_installation(
        drupal_root=drupal_root,
        download_cache=download_cache,
    )


if __name__ == "__main__":
    main()
