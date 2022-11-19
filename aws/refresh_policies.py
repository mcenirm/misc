import datetime
import json
import os
import subprocess
from abc import abstractclassmethod, abstractmethod
from pathlib import Path

from icecream import ic

ID_ARN = "arn"
ID_AWS = "aws"
ID_IAM = "iam"
SCHEME_ARN = ID_ARN + ":"

PATH_OUT = Path("out")
EXT_JSON = ".json"
NAME_IAM_LIST_POLICIES = "iam-list-policies"

JSON_ARN = "Arn"
JSON_POLICIES = "Policies"
JSON_UPDATE_DATE = "UpdateDate"

NOW = datetime.datetime.utcnow()
EXPIRY = datetime.timedelta(days=1)


class CachedJSON:
    def __init__(self, path, **kwargs):
        self.path = Path(path)
        self.kwargs = kwargs

        self.args = None
        self.data = None
        self.out = None
        self._expiration = NOW + EXPIRY

        if self.path.exists():
            self.load()
        self._refresh()

    def load(self):
        with open(self.path) as f:
            self.data = json.load(f)
        self._on_load()

    @abstractmethod
    def _on_load(self):
        pass

    @abstractmethod
    def _refresh(self):
        pass

    def refresh(self, force=False):
        if force or self.expired:
            self._refresh()
            self._on_load()
            with open(self.path, "w") as f:
                ic(self.path)
                json.dump(self.data, f, indent=2, sort_keys=True)

    @property
    def expired(self):
        ic(NOW, self._expiration)
        return NOW > self._expiration


class IAMListPoliciesJSON(CachedJSON):
    def __init__(self, path, **kwargs):
        self._max_update_date = None
        self._max_update_date_as_datetime = None
        super().__init__(path, **kwargs)

    @property
    def policies(self):
        return self.data[JSON_POLICIES]

    @property
    def max_update_date(self):
        if self.policies and not self._max_update_date:
            self._max_update_date = max([_[JSON_UPDATE_DATE] for _ in self.policies])
        return self._max_update_date

    @property
    def max_update_date_as_datetime(self):
        if self.max_update_date and not self._max_update_date_as_datetime:
            self._max_update_date_as_datetime = datetime.datetime.fromisoformat(
                self.max_update_date
            )
            self._expiration = self._max_update_date_as_datetime + EXPIRY
        return self._max_update_date_as_datetime

    def _on_load(self):
        self._max_update_date = None
        self._max_update_date_as_datetime = None
        if self.policies:
            self.policies.sort(key=arn_for_object)
        ic(self.max_update_date_as_datetime)

    def _refresh(self):
        self.command = AWSCLICommand("iam", "list-policies", **self.kwargs)
        self.data = self.command.data


class AWSCLICommand:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        cmd = ["aws", "--output", "json"]
        cmd.extend(args)
        for k, v in kwargs.items():
            cmd.append("--" + k.replace("-", "_"))
            cmd.append(v)
        self.cmd = cmd
        ic(self.cmd)
        self.out = subprocess.check_output(args=cmd)
        self.data = json.loads(self.out)


def arn_for_object(o):
    s = str(o)
    if s.startswith(SCHEME_ARN):
        return s
    if isinstance(o, dict) and JSON_ARN in o.keys():
        return o[JSON_ARN]
    return None


def service_for_arn(arn):
    arn = arn_for_object(arn)
    if arn is None:
        return None
    parts = arn.split(":")
    if parts[:2] == [ID_ARN, ID_AWS]:
        return parts[2]
    return None


def path_for_out(o):
    name = str(o)
    # arn = arn_for_object(o)
    # if arn:
    #     service = service_for_arn(arn)
    return PATH_OUT / (name + EXT_JSON)


def set_mtime_fromisoformat(path, date_string):
    path = Path(path)
    same_atime_ns = path.stat().st_atime_ns
    as_datetime = datetime.datetime.fromisoformat(date_string)
    as_timestamp = as_datetime.timestamp()
    new_mtime_ns = int(as_timestamp * 1e9)
    ns = (same_atime_ns, new_mtime_ns)
    os.utime(path, ns=ns)


# whoami = AWSCall("sts", "get-caller-identity")
# ic(whoami.data)

saved_iam_list_policies_path = path_for_out(NAME_IAM_LIST_POLICIES)
saved_iam_list_policies = IAMListPoliciesJSON(saved_iam_list_policies_path, scope="AWS")
saved_iam_list_policies.refresh()
set_mtime_fromisoformat(
    saved_iam_list_policies_path,
    saved_iam_list_policies.max_update_date,
)


# new_policies = policies.data[JSON_POLICIES]
# ic(new_policies[0][JSON_ARN])
# new_policies.sort(key=arn_for_object)
# ic(new_policies[0][JSON_ARN])
