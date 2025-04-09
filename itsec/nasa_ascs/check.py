from __future__ import annotations

import abc
import dataclasses
import typing
import winreg

from frustra.dump import dump
from frustra.strings import guess_words
from frustra.windows import HIVES_BY_ABBR, RegDataType

if typing.TYPE_CHECKING:
    from .setting import Setting


@dataclasses.dataclass
class Check:
    s: Setting

    @classmethod
    @abc.abstractmethod
    def from_setting(cls, s: Setting) -> typing.Self:
        raise NotImplementedError(cls)

    def __init_subclass__(cls):
        words = guess_words(cls.__name__.removesuffix("Check"))
        _CHECK_TYPES[" ".join(map(str.lower, words))] = cls

    def __lt__(self, other: typing.Self) -> bool:
        return self.s < other.s


_CHECK_TYPES: dict[str, type[Check]] = {}


@dataclasses.dataclass
class WMIQueryCheck(Check):
    namespace: str
    classname: str
    expected: int | str

    @classmethod
    def from_setting(cls, s) -> typing.Self:
        return WMIQueryCheck(
            s,
            s.wmi_namespace,
            s.wmi_class,
            _int_or_str(s.wmi_result),
        )


@dataclasses.dataclass
class RegistryCheck(Check):
    hive: winreg.HKEYType
    keypath: str
    valuename: str
    valuedatatype: RegDataType
    expected: int | str | None = None

    @classmethod
    def from_setting(cls, s: Setting) -> typing.Self:
        hive = s.registry_hive
        regpath = s.registry_key_path

        if hive in HIVES_BY_ABBR:
            hive = HIVES_BY_ABBR[hive]
        else:
            raise ValueError("bad reg hive", dict(setting=s, hive=hive))

        type_ = getattr(RegDataType, s.registry_value_type, None)
        if type_ is None and not s.registry_value_name:
            raise ValueError("bad reg type", dict(setting=s, type_=type_))

        return cls(
            s, hive, regpath, s.registry_value_name, type_, s.registry_value_data
        )

    def __lt__(self, other: typing.Self) -> bool:
        return super().__lt__(other) or (
            self.hive,
            self.keypath,
            self.valuename,
        ) < (
            getattr(other, "hive", 0),
            getattr(other, "keypath", ""),
            getattr(other, "valuename", ""),
        )


@dataclasses.dataclass
class RegistryValueExistsCheck(RegistryCheck):
    @classmethod
    def from_setting(cls, s):
        return super().from_setting(s)


@dataclasses.dataclass
class SecurityTemplateCheck(Check):
    section: str
    name: str
    expected: int | str

    @classmethod
    def from_setting(cls, s: Setting) -> typing.Self:
        section_name = s.security_template_section
        cls = _CHECK_TYPES.get((section_name or "").lower())
        if cls is None:
            raise ValueError("bad section", dict(setting=s, section=section_name))

        return cls(
            s,
            section_name,
            s.security_template_name,
            _int_or_str(s.security_template_value),
        )

    def __lt__(self, other: typing.Self) -> bool:
        return super().__lt__(other) or (
            self.section,
            self.name,
        ) < (
            getattr(other, "section", ""),
            getattr(other, "name", ""),
        )


@dataclasses.dataclass
class SystemAccessCheck(SecurityTemplateCheck):
    @classmethod
    def from_setting(cls, s: Setting) -> typing.Self:
        raise NotImplementedError(cls)


@dataclasses.dataclass
class PrivilegeRightsCheck(SecurityTemplateCheck):
    @classmethod
    def from_setting(cls, s: Setting) -> typing.Self:
        raise NotImplementedError(cls)


@dataclasses.dataclass
class ServiceGeneralSettingCheck(SecurityTemplateCheck):
    @classmethod
    def from_setting(cls, s: Setting) -> typing.Self:
        raise NotImplementedError(cls)


@dataclasses.dataclass
class AuditPolicyCheck(Check):
    category: str | None = None  #     'Account Logon'
    subcategory: str | None = None  #  'Credential Validation'
    setting: str | None = None  #      'Success and Failure'
    success: bool | None = None  #     'True'
    failure: bool | None = None  #     'True'

    @classmethod
    def from_setting(cls, s: Setting) -> typing.Self:
        if s.audit_success is None:
            success = None
        else:
            success = bool(s.audit_success)
        if s.audit_failure is None:
            failure = None
        else:
            failure = bool(s.audit_failure)
        return cls(
            s,
            s.audit_category,
            s.audit_subcategory,
            s.audit_setting,
            success,
            failure,
        )

    def __lt__(self, other: typing.Self) -> bool:
        return super().__lt__(other) or (
            self.category,
            self.subcategory,
        ) < (
            getattr(other, "category", ""),
            getattr(other, "subcategory", ""),
        )


def check_from_setting(s: Setting) -> Check:
    ct = (s.check_type or "").lower()
    cls = _CHECK_TYPES.get(ct)
    if cls is None:
        return Check(s)
    chk = cls.from_setting(s)
    if chk is None:
        dump(cls)
    return chk


def _int_or_str(s: str) -> int | str:
    try:
        return int(s)
    except ValueError as ve:
        return s
