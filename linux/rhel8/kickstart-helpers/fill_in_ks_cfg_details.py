import io
import itertools
import sys
from argparse import ArgumentParser, Namespace
from difflib import unified_diff
from json import load
from pathlib import Path

from icecream import ic
from pykickstart.handlers.rhel8 import RHEL8Handler
from pykickstart.parser import KickstartParser

from kscfg_templates import TEMPLATES, prepare_template_parameters


class Settings:
    machines: list
    outputs_path: Path
    template_name: str
    template_str: str

    @classmethod
    def from_parsed_arguments(cls, parsed_arguments: Namespace):
        tmplname = parsed_arguments.template_name
        assert tmplname in TEMPLATES
        outpath = Path(parsed_arguments.outputs_dir)
        inpath = Path(parsed_arguments.machines_json)
        with open(inpath) as f:
            machines_data = load(f)
        assert isinstance(machines_data, list)
        assert len(machines_data) > 0
        s = cls()
        s.template_name = tmplname
        s.template_str = TEMPLATES[tmplname]
        s.outputs_path = outpath
        s.machines = machines_data
        return s


def run(settings: Settings):
    for machine in settings.machines:
        parameters = prepare_template_parameters(machine)
        kscfg_str = settings.template_str.format(**parameters)
        handler = RHEL8Handler()
        ksparser = KickstartParser(handler)
        ksparser.readKickstartFromString(kscfg_str)
        ksoutpath = settings.outputs_path / (machine["name"] + "-ks.cfg")
        ksout = open(ksoutpath, "w")
        with ksout:
            ksout.write(kscfg_str)
        print(ksoutpath)
        testpath = Path(ksoutpath.name)
        if testpath.exists():
            testlines = open(testpath).readlines()
            sys.stdout.writelines(
                itertools.islice(
                    unified_diff(
                        a=testlines,
                        b=io.StringIO(kscfg_str).readlines(),
                        fromfile=str(testpath),
                        tofile=str(testpath),
                    ),
                    10,
                )
            )


def make_argument_parser(prog=None):
    argument_parser = ArgumentParser(prog=prog)
    argument_parser.add_argument("machines_json", help="machines definition file")
    argument_parser.add_argument("--outputs-dir", default="outputs")
    argument_parser.add_argument("--template-name", default="experiment1")
    return argument_parser


def main():
    argument_parser = make_argument_parser()
    args = argument_parser.parse_args()
    settings = Settings.from_parsed_arguments(args)
    run(settings)


if __name__ == "__main__":
    main()
