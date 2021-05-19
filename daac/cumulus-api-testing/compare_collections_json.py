from glob import iglob
from json import loads
from pathlib import Path
from sys import argv

from dictdiffer import diff
from icecream import ic

glob_json_from_api = argv[1]
ic(glob_json_from_api)

collections_from_api = {}
for json_from_api in iglob(glob_json_from_api):
    ic(json_from_api)
    f = open(json_from_api)
    with f:
        j = loads(f.read())
        r = j["results"]
        if r:
            for c in r:
                for tskey in ("createdAt", "updatedAt", "timestamp"):
                    del c[tskey]
                collections_from_api[c["name"]] = c

ic(collections_from_api.keys())


path_collections_from_repo = Path(argv[2])
ic(path_collections_from_repo)

collections_from_repo = {}
for json_from_repo in path_collections_from_repo.glob("*.json"):
    name = Path(json_from_repo).stem
    ic(json_from_repo)
    f = open(json_from_repo)
    with f:
        c = loads(f.read())
        n = c["name"]
        if name != n:
            ic(name, n)
        collections_from_repo[n] = c

ic(collections_from_repo.keys())


keys_from_api = set(collections_from_api)
keys_from_repo = set(collections_from_repo)
ic(keys_from_api - keys_from_repo)
ic(keys_from_repo - keys_from_api)
badcollections = set()
for name in keys_from_api & keys_from_repo:
    a = collections_from_api[name]
    r = collections_from_repo[name]
    d = diff(a, r)
    for i in d:
        if i[0] == "change":
            if i[1] in ["meta.hyrax_processing", ["files", 1, "regex"]]:
                continue
        if i == ("change", "duplicateHandling", ("skip", "replace")):
            continue
        if i == ("remove", "", [("reportToEms", True)]):
            continue
        if i[0] == "add":
            if i[1] == "":
                if isinstance(i[2], list):
                    if isinstance(i[2][0], tuple):
                        if i[2][0][0] == "dataType":
                            continue
        ic(name, i)
        badcollections.add(name)
        break

ic(badcollections)
ic(keys_from_api - badcollections)
ic(len(badcollections), len(keys_from_api - badcollections))
