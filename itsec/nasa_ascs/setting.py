from __future__ import annotations

import dataclasses
import re
import typing

from frustra.strings import str_to_identifier


@dataclasses.dataclass
class Setting:
    linenum: int | None = None
    nasa_ascs_id: str | None = None
    severity: str | None = None
    check_type: str | None = None
    path: str | None = None
    nasa_control: str | None = None
    control_setting: str | None = None
    type_: str | None = None
    title: str | None = None
    nist_sp_800_53r5_reference: str | None = None
    stig_reference: str | None = None
    wmi_namespace: str | None = None
    wmi_class: str | None = None
    wmi_result: str | None = None
    registry_hive: str | None = None
    registry_key_path: str | None = None
    registry_value_name: str | None = None
    registry_value_type: str | None = None
    registry_value_data: str | None = None
    security_template_section: str | None = None
    security_template_name: str | None = None
    security_template_value: str | None = None
    audit_category: str | None = None
    audit_subcategory: str | None = None
    audit_setting: str | None = None
    audit_success: bool | None = None
    audit_failure: bool | None = None

    def __lt__(self, other: typing.Self) -> bool:
        return self.nasa_ascs_id < other.nasa_ascs_id


class Specification:
    def __init__(self, lines: list[str]):
        self.lines = [str(s) for s in lines]
        self.settings: list[Setting] = []
        self.document_identifier: str = None
        self.document_version: str = None

        md = None
        s = None
        t = None
        for linenum, line in enumerate(self.lines, 1):
            m_heading = re.compile(r"=+\s+(?P<title>NASA-ASCS-\d+:\s+.*\S)\s*").match(
                line
            )
            if m_heading:
                if t is not None:
                    raise ValueError(
                        "Still in table at start of new setting",
                        dict(linenum=linenum, line=line, oldsetting=s),
                    )
                if s is not None:
                    self.settings.append(guess_setting_from_dict(s))
                s = dict(m_heading.groupdict())
                s["linenum"] = linenum
                t = None
                continue

            if s is None:
                m_doc = re.compile(
                    r":(?P<n>document-identifier|document-version):\s+(?P<v>.*\S)\s*$"
                ).match(line)
                if m_doc:
                    n = m_doc.group("n")
                    v = m_doc.group("v")
                    n = str_to_identifier(n)
                    if md is None:
                        md = {}
                    md[n] = v
                    continue
                else:
                    # Skip everything before first setting block
                    continue

            if line.startswith("[cols="):
                # Skip table attribute inside setting block
                continue

            if line == "|===":
                # Table begin vs end
                if t is None:
                    if s is None:
                        raise ValueError(
                            "Unexpected table outside of setting block",
                            dict(linenum=linenum),
                        )
                    t = True
                else:
                    t = None
                continue

            if t is None:
                # Skip everything else that is not inside the table
                continue

            m_nv = re.compile(r"\|(?P<n>[^|]+)\|(?P<v>.*)$").match(line)
            if m_nv:
                # Get name and value from table row
                n = m_nv.group("n")
                v = m_nv.group("v")
                n = str_to_identifier(n)
                s[n] = v
                continue

            raise ValueError(
                "Unexpected line in setting table",
                dict(linenum=linenum, line=line, setting=s),
            )

        if s is not None:
            self.settings.append(guess_setting_from_dict(s))

        if md is not None:
            self.document_identifier = md.get("document_identifier")
            self.document_version = md.get("document_version")


def guess_setting_from_dict(d: dict[str, str]) -> Setting:
    s = Setting(**d)

    sep = "\\"
    parts = s.path.split(sep)
    if len(parts) < 4 or parts[0] != "" or parts[1] != "":
        raise ValueError(
            "Bad context in path", dict(setting=s, path=path, pathparts=parts)
        )
    context = parts[2]
    path = sep.join(parts[3:]) if len(parts) > 3 else None

    if s.type_ == "WMI Query":
        s.check_type = s.type_
        if context != "HKLM":
            raise ValueError("Bad WMI context", dict(setting=s, context=context))
        s.wmi_namespace = path
        s.wmi_class = s.nasa_control
        s.wmi_result = s.control_setting
        s.type_ = None
        s.path = None
        s.nasa_control = None
        s.control_setting = None
    elif context in {"HKLM", "HKCU"}:
        s.check_type = "Registry"
        s.registry_hive = context
        s.registry_key_path = path
        s.registry_value_name = s.nasa_control
        s.registry_value_type = s.type_
        s.registry_value_data = s.control_setting
        if s.registry_value_type is None:
            if s.registry_value_name is not None:
                s.check_type = "Registry value exists"
            else:
                s.check_type = "Registry key exists"
        elif s.registry_value_type not in {
            "REG_DWORD",
            "REG_MULTI_SZ",
            "REG_SZ",
        }:
            raise ValueError(
                "Bad registry value type",
                dict(setting=s, registry_value_type=s.registry_value_type),
            )
        s.path = None
        s.nasa_control = None
        s.type_ = None
        s.control_setting = None
    elif context == "Security Template":
        s.check_type = context
        s.security_template_section = path
        s.security_template_name = s.nasa_control
        s.security_template_value = s.control_setting
        s.path = None
        s.nasa_control = None
        s.control_setting = None
    elif context == "Audit Policy":
        s.check_type = context
        s.audit_category = path
        s.audit_subcategory = s.nasa_control
        s.audit_setting = s.control_setting
        s.audit_success = s.audit_setting in {"Success and Failure", "Success"}
        s.audit_failure = s.audit_setting in {"Success and Failure", "Failure"}
        if s.audit_setting not in {"Success and Failure", "Success", "Failure"}:
            raise ValueError(
                "Bad audit setting", dict(setting=s, audit_setting=s.audit_setting)
            )
        s.path = None
        s.nasa_control = None
        s.control_setting = None
    else:
        raise ValueError("Unable to categorize setting", dict(setting=s))
    return s
