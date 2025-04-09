from __future__ import annotations

import enum
import winreg

HIVES_BY_ABBR = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
}


class RegDataType(enum.IntEnum):
    REG_NONE = winreg.REG_NONE
    REG_SZ = winreg.REG_SZ
    REG_EXPAND_SZ = winreg.REG_EXPAND_SZ
    REG_BINARY = winreg.REG_BINARY
    REG_DWORD = winreg.REG_DWORD
    REG_DWORD_BIG_ENDIAN = winreg.REG_DWORD_BIG_ENDIAN
    REG_LINK = winreg.REG_LINK
    REG_MULTI_SZ = winreg.REG_MULTI_SZ
    REG_RESOURCE_LIST = winreg.REG_RESOURCE_LIST
    REG_FULL_RESOURCE_DESCRIPTOR = winreg.REG_FULL_RESOURCE_DESCRIPTOR
    REG_RESOURCE_REQUIREMENTS_LIST = winreg.REG_RESOURCE_REQUIREMENTS_LIST
    REG_QWORD = winreg.REG_QWORD
