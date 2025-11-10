from __future__ import annotations

import collections.abc
import dataclasses
import enum
import functools
import ipaddress
import json
import pathlib
import sys
import typing
import uuid

import dataclasses_json
import dns.name

# https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/c1987d42-1847-4cc9-acf7-aab2136d6952
# 6.3.2.3 SRV Records


# https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/272a3d3b-b15a-40e1-9f20-652aabb2603d
# 6.3.2.4 Non-SRV Records


_MSDCS = "_msdcs"
_SITES = "_sites"


class WellKnownSrvPort(enum.IntEnum):
    KERBEROS = 88
    LDAP = 389
    KPASSWD = 464
    GC = 3268

    @functools.cache
    def for_srv(self) -> str:
        return "_" + self.name.lower()


class Protocol(enum.StrEnum):
    TCP = enum.auto()
    UDP = enum.auto()

    @functools.cache
    def for_srv(self) -> str:
        return "_" + self.name.lower()


class PendingAction(enum.StrEnum):
    KEEP = enum.auto()
    PROMOTE = enum.auto()
    DEMOTE = enum.auto()
    REMOVE = enum.auto()


class DnsRecordType(enum.StrEnum):
    A = enum.auto()
    CNAME = enum.auto()
    SRV = enum.auto()


class DnsName:
    def __init__(self, *args) -> None:
        if not args:
            raise ValueError("missing args")
        labels: list[bytes | str] = []
        for i, arg in enumerate(args):
            if isinstance(arg, DnsName):
                ext = arg._name.labels
            elif isinstance(arg, str):
                ext = arg.split(".")
            elif isinstance(arg, bytes):
                ext = arg.split(b".")
            elif isinstance(arg, dns.name.Name):
                ext = arg.labels
            else:
                raise ValueError("bad label at index", i, arg)
            labels.extend(ext)
        self._name = dns.name.Name(labels).canonicalize()

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple([str(x, encoding="utf8") for x in self._name.labels])

    def anchor(self) -> typing.Self:
        self._name = self._name.concatenate(dns.name.empty)
        return self

    def __str__(self) -> str:
        return self._name.to_text(omit_final_dot=False)

    def __truediv__(self, other) -> DnsName:
        return DnsName(DnsName(other)._name.concatenate(self._name))

    def __lt__(self, other) -> bool:
        if isinstance(other, DnsName):
            return self._name < other._name.__lt__
        else:
            raise NotImplemented


@dataclasses.dataclass(order=True)
class DnsRecord:
    name: DnsName
    type: DnsRecordType
    target: str
    action: PendingAction

    @classmethod
    def a(
        cls,
        *,
        name: DnsName,
        target: ipaddress.IPv4Address,
        action: PendingAction,
    ) -> DnsRecord:
        return cls(
            name=name.anchor(), type=DnsRecordType.A, target=str(target), action=action
        )

    @classmethod
    def cname(
        cls, *, name: DnsName, target: DnsName, action: PendingAction
    ) -> DnsRecord:
        return cls(
            name=name.anchor(),
            type=DnsRecordType.CNAME,
            target=str(target),
            action=action,
        )

    @classmethod
    def srv_record(
        cls,
        *,
        port: WellKnownSrvPort,
        protocol: Protocol,
        base: DnsName,
        action: PendingAction,
        target: DnsName,
        priority=0,
        weight=100,
    ) -> DnsRecord:
        return cls(
            name=DnsName(port.for_srv(), protocol.for_srv(), base).anchor(),
            type=DnsRecordType.SRV,
            target=" ".join([str(x) for x in [priority, weight, port, target]]),
            action=action,
        )


@dataclasses_json.dataclass_json(letter_case=dataclasses_json.LetterCase.KEBAB)
@dataclasses.dataclass
class DomainConfig:
    dns_name: str
    domain_guid: uuid.UUID
    sites: list[SiteConfig]

    def get_dns_records(self) -> list[DnsRecord]:
        r = []
        # TODO do we care about forest vs domain?
        forest_name = self.dns_name

        for site in self.sites:
            r.extend(site.get_dns_records(forest_name, self.dns_name, self.domain_guid))
        return r


@dataclasses_json.dataclass_json(letter_case=dataclasses_json.LetterCase.KEBAB)
@dataclasses.dataclass
class SiteConfig:
    name: str
    servers: list[ServerConfig]

    def get_dns_records(
        self,
        forest_name: str,
        domain_name: str,
        domain_guid: uuid.UUID,
    ) -> list[DnsRecord]:
        r = []
        # TODO Can a server be in more than one site? The references say they can.
        for server in self.servers:
            r.extend(
                server.get_dns_records(
                    forest_name, domain_name, domain_guid, [self.name]
                )
            )
        return r


@dataclasses_json.dataclass_json(letter_case=dataclasses_json.LetterCase.KEBAB)
@dataclasses.dataclass
class ServerConfig:
    name: str
    dsa_guid: uuid.UUID
    ipv4: list[ipaddress.IPv4Address]
    is_gc: bool = False
    is_pdc: bool = False
    is_rodc: bool = False
    pending_action: PendingAction = PendingAction.KEEP

    def get_dns_records(
        self,
        forest_name: str,
        domain_name: str,
        domain_guid: uuid.UUID,
        site_names: list[str],
    ) -> list[DnsRecord]:
        """

        # all domain controllers
        *                                               {DOMAIN}.   A       {SERVER-IPv4}
        *                             {DSA-GUID}._msdcs.{FOREST}.   CNAME   {SERVER}.{DOMAIN}.
        *   _ldap    ._tcp.{SITE-NAME}._sites.dc._msdcs.{DOMAIN}.   SRV     0 100 389 {SERVER}.{DOMAIN}.
        *   _ldap    ._tcp.{SITE-NAME}._sites          .{DOMAIN}.   SRV     0 100 389 {SERVER}.{DOMAIN}.
        *   _kerberos._tcp.{SITE-NAME}._sites.dc._msdcs.{DOMAIN}.   SRV     0 100 88 {SERVER}.{DOMAIN}.
        *   _kerberos._tcp.{SITE-NAME}._sites          .{DOMAIN}.   SRV     0 100 88 {SERVER}.{DOMAIN}.

        # non-RODC
        *   _ldap    ._tcp                             .{DOMAIN}.   SRV     0 100 389 {SERVER}.{DOMAIN}.
        *   _ldap    ._tcp                   .dc._msdcs.{DOMAIN}.   SRV     0 100 389 {SERVER}.{DOMAIN}.
        *   _ldap    ._tcp.{DOMAIN-GUID}.domains._msdcs.{FOREST}.   SRV     0 100 389 {SERVER}.{DOMAIN}.
        *   _kpasswd ._udp                             .{DOMAIN}.   SRV     0 100 464 {SERVER}.{DOMAIN}.
        *   _kpasswd ._tcp                             .{DOMAIN}.   SRV     0 100 464 {SERVER}.{DOMAIN}.
        *   _kerberos._udp                             .{DOMAIN}.   SRV     0 100 88 {SERVER}.{DOMAIN}.
        *   _kerberos._tcp                             .{DOMAIN}.   SRV     0 100 88 {SERVER}.{DOMAIN}.
        *   _kerberos._tcp                   .dc._msdcs.{DOMAIN}.   SRV     0 100 88 {SERVER}.{DOMAIN}.

        # GC
        *                                     gc._msdcs.{DOMAIN}.   A       {SERVER-IPv4}
        *   _ldap    ._tcp.{SITE-NAME}._sites.gc._msdcs.{FOREST}.   SRV     0 100 389 {SERVER}.{DOMAIN}.
        *   _gc      ._tcp.{SITE-NAME}._sites          .{FOREST}.   SRV     0 100 3268 {SERVER}.{DOMAIN}.

        # non-RODC and GC
        *   _ldap    ._tcp                   .gc._msdcs.{FOREST}.   SRV     0 100 389 {SERVER}.{DOMAIN}.
        *   _gc      ._tcp                             .{FOREST}.   SRV     0 100 3268 {SERVER}.{DOMAIN}.

        # PDC
        *   _ldap    ._tcp                  .pdc._msdcs.{DOMAIN}.   SRV     0 100 389 {SERVER}.{DOMAIN}.

        """
        r = []

        forest_fqdn = DnsName(forest_name)
        domain_fqdn = DnsName(domain_name)
        my_fqdn = domain_fqdn / self.name

        action_all = action_non_rodc = action_gc = action_non_rodc_and_gc = (
            action_pdc
        ) = self.pending_action
        if self.pending_action not in (PendingAction.DEMOTE, PendingAction.REMOVE):
            if not (not self.is_rodc):
                action_non_rodc = PendingAction.REMOVE
            if not (self.is_gc):
                action_gc = PendingAction.REMOVE
            if not (not self.is_rodc and self.is_gc):
                action_non_rodc_and_gc = PendingAction.REMOVE
            if not (self.is_pdc):
                action_pdc = PendingAction.REMOVE

        # all domain controllers
        for addr in self.ipv4:
            r.append(DnsRecord.a(name=domain_fqdn, target=addr, action=action_all))
        r.append(
            DnsRecord.cname(
                name=forest_fqdn / _MSDCS / str(self.dsa_guid),
                target=my_fqdn,
                action=action_all,
            )
        )
        for site_name in site_names:
            for port in [WellKnownSrvPort.LDAP, WellKnownSrvPort.KERBEROS]:
                for base in [
                    domain_fqdn / _MSDCS / "dc" / _SITES / site_name,
                    domain_fqdn / _SITES / site_name,
                ]:
                    r.append(
                        DnsRecord.srv_record(
                            port=port,
                            protocol=Protocol.TCP,
                            base=base,
                            target=my_fqdn,
                            action=action_all,
                        )
                    )

        # non-RODC
        for port, protocol, base in [
            [WellKnownSrvPort.LDAP, Protocol.TCP, domain_fqdn],
            [WellKnownSrvPort.LDAP, Protocol.TCP, domain_fqdn / _MSDCS / "dc"],
            [
                WellKnownSrvPort.LDAP,
                Protocol.TCP,
                forest_fqdn / _MSDCS / "domains" / str(domain_guid),
            ],
            [WellKnownSrvPort.KPASSWD, Protocol.UDP, domain_fqdn],
            [WellKnownSrvPort.KPASSWD, Protocol.TCP, domain_fqdn],
            [WellKnownSrvPort.KERBEROS, Protocol.UDP, domain_fqdn],
            [WellKnownSrvPort.KERBEROS, Protocol.TCP, domain_fqdn],
            [WellKnownSrvPort.KERBEROS, Protocol.TCP, domain_fqdn / _MSDCS / "dc"],
        ]:
            r.append(
                DnsRecord.srv_record(
                    port=port,
                    protocol=protocol,
                    base=base,
                    target=my_fqdn,
                    action=action_non_rodc,
                )
            )

        # GC
        for addr in self.ipv4:
            r.append(
                DnsRecord.a(
                    name=domain_fqdn / _MSDCS / "gc", target=addr, action=action_gc
                )
            )
            for site_name in site_names:
                for port, protocol, base in [
                    [
                        WellKnownSrvPort.LDAP,
                        Protocol.TCP,
                        forest_fqdn / _MSDCS / "gc" / _SITES / site_name,
                    ],
                    [
                        WellKnownSrvPort.GC,
                        Protocol.TCP,
                        forest_fqdn / _SITES / site_name,
                    ],
                ]:
                    r.append(
                        DnsRecord.srv_record(
                            port=port,
                            protocol=protocol,
                            base=base,
                            target=my_fqdn,
                            action=action_gc,
                        )
                    )

        # non-RODC and GC
        for port, protocol, base in [
            [WellKnownSrvPort.LDAP, Protocol.TCP, forest_fqdn / _MSDCS / "gc"],
            [WellKnownSrvPort.GC, Protocol.TCP, forest_fqdn],
        ]:
            r.append(
                DnsRecord.srv_record(
                    port=port,
                    protocol=protocol,
                    base=base,
                    target=my_fqdn,
                    action=action_non_rodc_and_gc,
                )
            )

        # PDC
        for port, protocol, base in [
            [WellKnownSrvPort.LDAP, Protocol.TCP, domain_fqdn / _MSDCS / "pdc"],
        ]:
            r.append(
                DnsRecord.srv_record(
                    port=port,
                    protocol=protocol,
                    base=base,
                    target=my_fqdn,
                    action=action_pdc,
                )
            )

        return r


def load_domains_config_from_json(configfile: pathlib.Path) -> list[DomainConfig]:
    configfile = pathlib.Path(configfile)
    configdict = json.loads(configfile.read_text())
    domainslist = configdict.pop("domains")
    dump_extras(configdict, "config")
    return [DomainConfig.from_dict(data) for data in domainslist]


def dump_extras(d: dict, label: str) -> None:
    if d:
        print(f"EXTRA {str(label).upper()}")
        print(d)
        print()


def flatten(container) -> typing.Generator[object, None, None]:
    if isinstance(container, str):
        yield container
    elif isinstance(container, collections.abc.Iterable):
        for item in container:
            yield from flatten(item)
    else:
        yield str(container)


def main():
    configfile = pathlib.Path(sys.argv[1])
    for domain in load_domains_config_from_json(configfile):
        records = domain.get_dns_records()
        w = max([len(str(r.name)) for r in records])
        for action in PendingAction:
            filtered = [r for r in records if r.action == action]
            if filtered:
                print("##", action.name)
                for r in sorted(filtered):
                    print(
                        str(r.name).ljust(w),
                        "  ",
                        r.type.name.ljust(6),
                        "  ",
                        r.target,
                    )
                print()


if __name__ == "__main__":
    sys.exit(main())
