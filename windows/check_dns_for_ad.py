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
import dns.rdata
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes.ANY.CNAME
import dns.rdtypes.IN.A
import dns.rdtypes.IN.SRV
import dns.resolver
import dns.rrset

# https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/c1987d42-1847-4cc9-acf7-aab2136d6952
# 6.3.2.3 SRV Records


# https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-adts/272a3d3b-b15a-40e1-9f20-652aabb2603d
# 6.3.2.4 Non-SRV Records


_MSDCS = "_msdcs"
_SITES = "_sites"


class Service(enum.StrEnum):
    KERBEROS = enum.auto()
    LDAP = enum.auto()
    KPASSWD = enum.auto()
    GC = enum.auto()

    @functools.cache
    def for_srv(self) -> str:
        return "_" + self.name.lower()

    def default_port(self) -> Port:
        return getattr(Port, self.name)


class Port(enum.IntEnum):
    KERBEROS = 88
    LDAP = 389
    KPASSWD = 464
    GC = 3268

    def default_service(self) -> Service:
        return getattr(Service, self.name)


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

    def should_exist(self) -> bool:
        return self in {PendingAction.KEEP, PendingAction.PROMOTE}

    def __repr__(self) -> str:
        return self.__class__.__name__ + "." + self.name


class DnsName:
    def __init__(self, *args) -> None:
        if not args:
            raise ValueError("missing args")
        labels: list[bytes] = []
        for i, arg in enumerate(args):
            if isinstance(arg, DnsName):
                ext = arg.name.labels
            elif isinstance(arg, dns.name.Name):
                ext = arg.labels
            elif isinstance(arg, str):
                ext = arg.lower().encode().split(b".")
            elif isinstance(arg, bytes):
                ext = arg.lower().split(b".")
            else:
                raise ValueError("bad label at index", i, arg)
            labels.extend(ext)
        self._name = dns.name.Name(labels).canonicalize()

    @property
    def name(self) -> dns.name.Name:
        return dns.name.Name(self.labels)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple([str(x, encoding="utf8") for x in self._name.labels])

    def anchor(self) -> typing.Self:
        if not self._name.is_absolute():
            self._name = dns.name.Name(list(self.labels) + [b""])
        return self

    def __eq__(self, value: object) -> bool:
        if isinstance(value, DnsName):
            return self.name == value.name
        else:
            raise NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)

    def __str__(self) -> str:
        return self._name.to_text(omit_final_dot=False)

    def __repr__(self) -> str:
        return (
            self.__class__.__name__
            + "("
            + ", ".join([repr(x) for x in self.labels])
            + ")"
        )

    def __truediv__(self, other) -> DnsName:
        if isinstance(other, (DnsName, dns.name.Name)):
            suffix_labels = other.labels
        elif isinstance(other, (str, bytes)):
            suffix_labels = [other]
        else:
            raise NotImplemented
        return DnsName(*suffix_labels, *self.labels)

    def __lt__(self, other) -> bool:
        if isinstance(other, DnsName):
            return self._name < other._name
        else:
            raise NotImplemented


type DnsRecordType = dns.rdatatype.RdataType
type DnsRecordData = dns.rdata.Rdata


@dataclasses.dataclass(frozen=True, kw_only=True)
class DnsRecord:
    name: DnsName
    type_: DnsRecordType
    data: DnsRecordData
    action: PendingAction

    @property
    def target(self) -> str:
        return self.data.to_text()

    def __hash__(self) -> int:
        return hash((self.name, self.type_, self.target))

    def __lt__(self, other) -> bool:
        if isinstance(other, DnsRecord):
            return (self.name, self.type_, self.data) < (
                other.name,
                other.type_,
                other.data,
            )
        else:
            raise NotImplemented

    @classmethod
    def _make(
        cls,
        *,
        name: DnsName,
        type_: DnsRecordType,
        action: PendingAction,
        **rdargs,
    ) -> DnsRecord:
        name = DnsName(name).anchor()
        ctr: typing.Type[dns.rdata.Rdata] = {
            dns.rdatatype.A: dns.rdtypes.IN.A.A,
            dns.rdatatype.CNAME: dns.rdtypes.ANY.CNAME.CNAME,
            dns.rdatatype.SRV: dns.rdtypes.IN.SRV.SRV,
        }[type_]
        rdargs = dict(rdargs)
        if "target" in rdargs:
            rdargs["target"] = rdargs["target"].anchor().name
        rd = ctr(rdclass=dns.rdataclass.IN, rdtype=type_, **rdargs)
        return cls(name=name, type_=type_, data=rd, action=action)

    @classmethod
    def A(
        cls, *, name: DnsName, target: ipaddress.IPv4Address, action: PendingAction
    ) -> DnsRecord:
        return cls._make(
            name=name, type_=dns.rdatatype.A, action=action, address=target
        )

    @classmethod
    def CNAME(
        cls, *, name: DnsName, target: DnsName, action: PendingAction
    ) -> DnsRecord:
        return cls._make(
            name=name, type_=dns.rdatatype.CNAME, action=action, target=target
        )

    @classmethod
    def SRV(
        cls,
        *,
        service: Service,
        port: Port,
        protocol: Protocol,
        base: DnsName,
        action: PendingAction,
        target: DnsName,
        priority=0,
        weight=100,
    ) -> DnsRecord:
        name = DnsName(service.for_srv(), protocol.for_srv(), base)
        return cls._make(
            name=name,
            type_=dns.rdatatype.SRV,
            action=action,
            port=port.value,
            priority=int(priority),
            weight=int(weight),
            target=target,
        )


@dataclasses_json.dataclass_json(
    letter_case=dataclasses_json.LetterCase.KEBAB,  # pyright: ignore[reportArgumentType]
)
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


@dataclasses_json.dataclass_json(
    letter_case=dataclasses_json.LetterCase.KEBAB,  # pyright: ignore[reportArgumentType]
)
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


@dataclasses_json.dataclass_json(
    letter_case=dataclasses_json.LetterCase.KEBAB,  # type: ignore
)
@dataclasses.dataclass
class ServerConfig:
    name: str
    dsa_guid: uuid.UUID
    ipv4: list[ipaddress.IPv4Address]
    is_gc: bool = False
    is_pdc: bool = False
    is_rodc: bool = False
    pending_action: PendingAction = PendingAction.KEEP

    def __hash__(self) -> int:
        return hash((self.name, self.dsa_guid))

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
        *   _ldap    ._tcp.{SITE-NAME}._sites.gc._msdcs.{FOREST}.   SRV     0 100 3268 {SERVER}.{DOMAIN}.
        *   _gc      ._tcp.{SITE-NAME}._sites          .{FOREST}.   SRV     0 100 3268 {SERVER}.{DOMAIN}.

        # non-RODC and GC
        *   _ldap    ._tcp                   .gc._msdcs.{FOREST}.   SRV     0 100 3268 {SERVER}.{DOMAIN}.
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
            r.append(
                DnsRecord.A(
                    name=domain_fqdn,
                    target=addr,
                    action=action_all,
                )
            )
        r.append(
            DnsRecord.CNAME(
                name=forest_fqdn / _MSDCS / str(self.dsa_guid),
                target=my_fqdn,
                action=action_all,
            )
        )
        for site_name in site_names:
            for port in [
                Port.LDAP,
                Port.KERBEROS,
            ]:
                for base in [
                    domain_fqdn / _MSDCS / "dc" / _SITES / site_name,
                    domain_fqdn / _SITES / site_name,
                ]:
                    r.append(
                        DnsRecord.SRV(
                            service=port.default_service(),
                            port=port,
                            protocol=Protocol.TCP,
                            base=base,
                            target=my_fqdn,
                            action=action_all,
                        )
                    )

        # non-RODC
        for port, protocol, base in [
            [Port.LDAP, Protocol.TCP, domain_fqdn],
            [Port.LDAP, Protocol.TCP, domain_fqdn / _MSDCS / "dc"],
            [
                Port.LDAP,
                Protocol.TCP,
                forest_fqdn / _MSDCS / "domains" / str(domain_guid),
            ],
            [Port.KPASSWD, Protocol.UDP, domain_fqdn],
            [Port.KPASSWD, Protocol.TCP, domain_fqdn],
            [Port.KERBEROS, Protocol.UDP, domain_fqdn],
            [Port.KERBEROS, Protocol.TCP, domain_fqdn],
            [Port.KERBEROS, Protocol.TCP, domain_fqdn / _MSDCS / "dc"],
        ]:
            r.append(
                DnsRecord.SRV(
                    service=port.default_service(),
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
                DnsRecord.A(
                    name=domain_fqdn / _MSDCS / "gc",
                    target=addr,
                    action=action_gc,
                )
            )
        for site_name in site_names:
            for service, base in [
                [Service.LDAP, forest_fqdn / _MSDCS / "gc" / _SITES / site_name],
                [Service.GC, forest_fqdn / _SITES / site_name],
            ]:
                r.append(
                    DnsRecord.SRV(
                        service=service,
                        port=Port.GC,
                        protocol=Protocol.TCP,
                        base=base,
                        target=my_fqdn,
                        action=action_gc,
                    )
                )

        # non-RODC and GC
        for service, base in [
            [Service.LDAP, forest_fqdn / _MSDCS / "gc"],
            [Service.GC, forest_fqdn],
        ]:
            r.append(
                DnsRecord.SRV(
                    service=service,
                    port=Port.GC,
                    protocol=Protocol.TCP,
                    base=base,
                    target=my_fqdn,
                    action=action_non_rodc_and_gc,
                )
            )

        # PDC
        r.append(
            DnsRecord.SRV(
                service=Service.LDAP,
                port=Port.LDAP,
                protocol=Protocol.TCP,
                base=domain_fqdn / _MSDCS / "pdc",
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
    return [DomainConfig.from_dict(data) for data in domainslist]  # type: ignore


def dump_extras(d: dict, label: str) -> None:
    if d:
        print(f"EXTRA {str(label).upper()}")
        print(d)
        print()


def dump_attrs_for_dns_object(o: object) -> None:
    for k, v in ((k, getattr(o, k)) for k in dir(o) if not k.startswith("_")):
        kpadded = k.ljust(20)
        if v is None:
            print("**", kpadded, "is ", "None")
        elif hasattr(v, "name"):
            print("**", kpadded, " = ", getattr(v, "name"))
        elif isinstance(v, (dns.rdatatype.RdataType,)):
            print("**", kpadded, " = ", v.name)
        elif isinstance(v, (str, int)):
            print("**", kpadded, " = ", repr(v))
        elif isinstance(v, (dns.name.Name,)):
            print("**", kpadded, " = ", v)
        elif callable(v):
            pass
        else:
            print("**", kpadded, "isa", type(v))


def flatten(container) -> typing.Generator[object, None, None]:
    if isinstance(container, str):
        yield container
    elif isinstance(container, collections.abc.Iterable):
        for item in container:
            yield from flatten(item)
    else:
        yield str(container)


@dataclasses.dataclass(frozen=True, kw_only=True)
class AllDnsRecordsThatMightBeNeeded:
    server_to_action_to_records: dict[
        ServerConfig, dict[PendingAction, list[DnsRecord]]
    ]
    name_to_records: dict[DnsName, list[DnsRecord]]
    record_to_server: dict[DnsRecord, ServerConfig]


def get_all_dns_records_that_might_be_needed(
    domain: DomainConfig,
) -> AllDnsRecordsThatMightBeNeeded:
    server_to_action_to_records: dict[
        ServerConfig, dict[PendingAction, list[DnsRecord]]
    ] = collections.defaultdict(lambda: collections.defaultdict(list))
    dnsname_to_records: dict[DnsName, list[DnsRecord]] = collections.defaultdict(list)
    record_to_server: dict[DnsRecord, ServerConfig] = dict()
    for site in domain.sites:
        for server in site.servers:
            records = server.get_dns_records(
                forest_name=domain.dns_name,
                domain_name=domain.dns_name,
                domain_guid=domain.domain_guid,
                site_names=[site.name],
            )
            for r in records:
                server_to_action_to_records[server][r.action].append(r)
                dnsname_to_records[r.name].append(r)
                record_to_server[r] = server
    return AllDnsRecordsThatMightBeNeeded(
        server_to_action_to_records=server_to_action_to_records,
        name_to_records=dnsname_to_records,
        record_to_server=record_to_server,
    )


def resolve_name_to_type_to_record_data_list(
    name_type_pairs: collections.abc.Iterable[tuple[DnsName, DnsRecordType]],
) -> dict[DnsName, dict[DnsRecordType, list[DnsRecordData]]]:
    pairs = set(name_type_pairs)
    name_to_type_to_records: dict[DnsName, dict[DnsRecordType, list[DnsRecordData]]] = (
        collections.defaultdict(lambda: collections.defaultdict(list))
    )
    res = dns.resolver.Resolver()
    for n, t in pairs:
        try:
            for rrs in res.resolve(n.name, t, raise_on_no_answer=False).response.answer:
                name_to_type_to_records[DnsName(rrs.name)][rrs.rdtype].extend(
                    rrs.items.keys()
                )
        except dns.resolver.NXDOMAIN:
            pass
    return name_to_type_to_records


def split_rrs(rrs: dns.rrset.RRset) -> list[dns.rrset.RRset]:
    r = []
    rd: dns.rdata.Rdata
    for rd in rrs.items.keys():
        newrrs = dns.rrset.RRset(
            name=rrs.name,
            rdclass=rrs.rdclass,
            rdtype=rrs.rdtype,
            covers=rrs.covers,
            deleting=rrs.deleting,
        )
        newrrs.add(rd=rd, ttl=rrs.ttl)
        r.append(newrrs)
    return r


def make_record_printer(
    name_width: int, type_width=6, target_width=40, print_=print
) -> collections.abc.Callable[[DnsRecord, str | None], None]:
    def record_printer(r: DnsRecord, flag: str | None):
        na = str(r.name).rjust(name_width)
        ty = r.type_.name.upper().ljust(type_width)
        ta = r.target.ljust(target_width)
        if flag is None:
            print_(na, ty, ta)
        else:
            print_(na, ty, ta, flag)

    return record_printer


def main():
    configfile = pathlib.Path(sys.argv[1])
    for domain in load_domains_config_from_json(configfile):
        print("#", "Domain:", domain.dns_name, domain.domain_guid)
        adrtmbn = get_all_dns_records_that_might_be_needed(domain)
        existing_name_to_type_to_record_data_list = (
            resolve_name_to_type_to_record_data_list(
                (r.name, r.type_) for r in adrtmbn.record_to_server.keys()
            )
        )
        existing = {
            (n, t, d)
            for n, t2ds in existing_name_to_type_to_record_data_list.items()
            for t, ds in t2ds.items()
            for d in ds
        }
        expected = {(r.name, r.type_, r.data) for r in adrtmbn.record_to_server.keys()}
        existing_but_not_expected = existing - expected
        expected_but_not_existing = expected - existing
        if False:
            print(f"{len(existing)=}")
            print(f"{len(expected)=}")
            print(f"{len(existing_but_not_expected)=}")
            print(f"{len(expected_but_not_existing)=}")
            testcase = sorted(existing)[0]
            print(testcase)
            for i in range(3):
                print(testcase[i])
                for r in expected:
                    if r[i] == testcase[i]:
                        print(testcase == r, r)
            raise SystemExit
        record_printer = make_record_printer(
            1 + max([len(str(r.name)) for r in adrtmbn.record_to_server.keys()])
        )
        for server, action_to_records in adrtmbn.server_to_action_to_records.items():
            print(
                "##",
                server.pending_action.name,
                "Server:",
                server.name,
                server.dsa_guid,
                "GC" if server.is_gc else "",
                "PDC" if server.is_pdc else "",
                "RODC" if server.is_rodc else "",
            )
            for action, records in action_to_records.items():
                should_exist = action.should_exist()
                filtered = [r for r in records if r.action == action]
                to_be_removed = []
                to_be_added = []
                for record in sorted(filtered):
                    exists = (
                        record.data
                        in existing_name_to_type_to_record_data_list.get(
                            record.name, {}
                        ).get(record.type_, [])
                    )
                    record_printer(
                        record, flag(exists=exists, should_exist=should_exist)
                    )
                    if exists and not should_exist:
                        to_be_removed.append(record)
                    elif should_exist and not exists:
                        to_be_added.append(record)
        print()
        print("## Changes needed")
        only_should_exist_records: list[DnsRecord] = []
        for name, records in sorted(adrtmbn.name_to_records.items()):
            possible_types = {r.type_ for r in records}
            if len(possible_types) != 1:
                raise NotImplementedError(
                    "name without exactly one possible type",
                    dict(name=name, possible_types=possible_types, records=records),
                )
            possible_type = list(possible_types)[0]
            existing_targets = existing_name_to_type_to_record_data_list.get(
                name, {}
            ).get(possible_type, [])
            for record in sorted(records):
                exists = record.data in existing_targets
                should_exist = record.action.should_exist()
                record_printer(record, flag(exists=exists, should_exist=should_exist))
                if should_exist:
                    only_should_exist_records.append(record)
            print()
        print()
        print("## Only the records that should exist")
        for r in sorted(only_should_exist_records):
            record_printer(r, None)
        print()
        if existing_but_not_expected:
            print("## Existing but not expected")
            for n, t, d in sorted(existing_but_not_expected):
                record_printer(
                    DnsRecord(name=n, type_=t, data=d, action=PendingAction.KEEP), None
                )
            print()


def flag(exists: bool, should_exist: bool, concise=False) -> str:
    if concise:
        flag = "??"
        if exists:
            if should_exist:
                flag = "oo"
            else:
                flag = "--"
        else:
            if should_exist:
                flag = "++"
            else:
                flag = ";;"
    else:
        if exists:
            if should_exist:
                flag = ".. do not remove"
            else:
                flag = "REMOVE"
        else:
            if should_exist:
                flag = "ADD"
            else:
                flag = ".. do not add"
        flag = "# " + flag
    return flag


if __name__ == "__main__":
    sys.exit(main())
