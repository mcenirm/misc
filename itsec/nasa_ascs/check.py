from __future__ import annotations

import dataclasses
import typing
import winreg

from frustra.windows import RegDataType

if typing.TYPE_CHECKING:
    from .setting import Setting


@dataclasses.dataclass
class Check:
    s: Setting


@dataclasses.dataclass
class WMIQueryCheck(Check):
    namespace: str
    classname: str
    expected: int | str


@dataclasses.dataclass
class RegistryCheck(Check):
    hive: winreg.HKEYType
    keypath: str
    valuename: str
    valuedatatype: RegDataType
    expected: int | str | None = None

    def __lt__(self, other: typing.Self) -> bool:
        return (
            self.hive,
            self.keypath,
            self.valuename,
        ) < (
            other.hive,
            other.keypath,
            other.valuename,
        )


@dataclasses.dataclass
class RegValueExistsCheck(RegistryCheck):
    pass


@dataclasses.dataclass
class SecurityTemplateCheck(Check):
    section: str
    name: str
    expected: int | str

    def __lt__(self, other: typing.Self) -> bool:
        return (self.section, self.name) < (other.section, other.name)


@dataclasses.dataclass
class SystemAccessCheck(SecurityTemplateCheck):
    pass


@dataclasses.dataclass
class PrivilegeRightsCheck(SecurityTemplateCheck):
    pass


@dataclasses.dataclass
class ServiceGeneralSettingCheck(SecurityTemplateCheck):
    pass


@dataclasses.dataclass
class AuditPolicyCheck(Check):
    category: str | None = None  #     'Account Logon'
    subcategory: str | None = None  #  'Credential Validation'
    setting: str | None = None  #      'Success and Failure'
    success: bool | None = None  #     'True'
    failure: bool | None = None  #     'True'

    def __lt__(self, other: typing.Self) -> bool:
        return (self.category, self.subcategory) < (other.category, other.subcategory)
