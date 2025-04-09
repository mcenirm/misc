from __future__ import annotations

import typing
import winreg

from frustra.windows import RegDataType

from .check import (
    AuditPolicyCheck,
    PrivilegeRightsCheck,
    RegistryCheck,
    ServiceGeneralSettingCheck,
    SystemAccessCheck,
    WMIQueryCheck,
)
from .report import CheckReport, CheckResult, ResultState

if typing.TYPE_CHECKING:
    from .check import Check


class Checklist:
    def __init__(self):
        self.registry_checks_by_hive_keypath_valuename: dict[
            str, dict[str, dict[str, list[RegistryCheck]]]
        ] = {}
        self.wmi_query_checks_by_namespace: dict[str, list[WMIQueryCheck]] = {}
        self.system_access_checks: list[SystemAccessCheck] = []
        self.privilege_rights_checks: list[PrivilegeRightsCheck] = []
        self.service_general_setting_checks: list[ServiceGeneralSettingCheck] = []
        self.audit_policy_checks: list[AuditPolicyCheck] = []

    def add(self, chk: Check) -> typing.Self:
        if isinstance(chk, RegistryCheck):
            if chk.hive not in self.registry_checks_by_hive_keypath_valuename:
                self.registry_checks_by_hive_keypath_valuename[chk.hive] = {}
            if (
                chk.keypath
                not in self.registry_checks_by_hive_keypath_valuename[chk.hive]
            ):
                self.registry_checks_by_hive_keypath_valuename[chk.hive][
                    chk.keypath
                ] = {}
            if (
                chk.valuename
                not in self.registry_checks_by_hive_keypath_valuename[chk.hive][
                    chk.keypath
                ]
            ):
                self.registry_checks_by_hive_keypath_valuename[chk.hive][chk.keypath][
                    chk.valuename
                ] = []
            self.registry_checks_by_hive_keypath_valuename[chk.hive][chk.keypath][
                chk.valuename
            ].append(chk)
        elif isinstance(chk, SystemAccessCheck):
            self.system_access_checks.append(chk)
        elif isinstance(chk, PrivilegeRightsCheck):
            self.privilege_rights_checks.append(chk)
        elif isinstance(chk, WMIQueryCheck):
            if chk.namespace not in self.wmi_query_checks_by_namespace:
                self.wmi_query_checks_by_namespace[chk.namespace] = []
            self.wmi_query_checks_by_namespace[chk.namespace].append(chk)
        elif isinstance(chk, ServiceGeneralSettingCheck):
            self.service_general_setting_checks.append(chk)
        elif isinstance(chk, AuditPolicyCheck):
            self.audit_policy_checks.append(chk)
        else:
            raise ValueError("TODO add check type", dict(chk=chk))
        return self

    def run(self) -> CheckReport:
        return CheckReport(
            results={}
            | self.run_registry_checks().results
            | self.run_wmi_query_checks().results
            | self.run_system_access_checks().results
            | self.run_privilege_rights_checks().results
            | self.run_service_general_setting_checks().results
            | self.run_audit_policy_checks().results
        )

    def run_registry_checks(self) -> CheckReport:
        report = CheckReport()
        for hive in sorted(self.registry_checks_by_hive_keypath_valuename.keys()):
            for keypath in sorted(
                self.registry_checks_by_hive_keypath_valuename[hive].keys()
            ):
                try:
                    hkey = winreg.OpenKey(hive, keypath)
                except FileNotFoundError as fnfe:
                    hkey = None
                for valuename in sorted(
                    self.registry_checks_by_hive_keypath_valuename[hive][keypath].keys()
                ):
                    checks = self.registry_checks_by_hive_keypath_valuename[hive][
                        keypath
                    ][valuename]
                    for chk in checks:
                        if hkey is None:
                            report.add(
                                CheckResult(
                                    chk=chk,
                                    state=ResultState.FAILED,
                                    reason="Missing registry key",
                                )
                            )
                        else:
                            try:
                                actual_data, actual_type = winreg.QueryValueEx(
                                    hkey, chk.valuename
                                )
                                actual_type = RegDataType(actual_type)
                                if actual_type != chk.valuedatatype:
                                    report.add(
                                        CheckResult(
                                            chk=chk,
                                            state=ResultState.FAILED,
                                            reason="Mismatch registry value data type",
                                            expected=chk.valuedatatype.name,
                                            actual=actual_type.name,
                                        )
                                    )
                                elif actual_data != chk.expected:
                                    report.add(
                                        CheckResult(
                                            chk=chk,
                                            state=ResultState.FAILED,
                                            reason="Different registry value data",
                                            expected=chk.expected,
                                            actual=actual_data,
                                        )
                                    )
                                else:
                                    report.add(
                                        CheckResult(
                                            chk=chk,
                                            state=ResultState.PASSED,
                                            expected=chk.expected,
                                            actual=actual_data,
                                        )
                                    )
                            except FileNotFoundError as fnfe:
                                report.add(
                                    CheckResult(
                                        chk=chk,
                                        state=ResultState.FAILED,
                                        reason="Missing registry value",
                                    )
                                )
        return report

    def run_wmi_query_checks(self) -> CheckReport:
        report = CheckReport()
        for ns in sorted(self.wmi_query_checks_by_namespace.keys()):
            for chk in self.wmi_query_checks_by_namespace[ns]:
                report.add(CheckResult(chk, ResultState.TODO))
        return report

    def run_system_access_checks(self) -> CheckReport:
        report = CheckReport()
        for chk in sorted(self.system_access_checks):
            report.add(CheckResult(chk, ResultState.TODO))
        return report

    def run_privilege_rights_checks(self) -> CheckReport:
        report = CheckReport()
        for chk in sorted(self.privilege_rights_checks):
            report.add(CheckResult(chk, ResultState.TODO))
        return report

    def run_service_general_setting_checks(self) -> CheckReport:
        report = CheckReport()
        for chk in sorted(self.service_general_setting_checks):
            report.add(CheckResult(chk, ResultState.TODO))
        return report

    def run_audit_policy_checks(self) -> CheckReport:
        report = CheckReport()
        for chk in sorted(self.audit_policy_checks):
            report.add(CheckResult(chk, ResultState.TODO))
        return report
