
# Sheet 1: Records exported from legacy nameserver (no documentation)

* Column A: Disposition (eg, Delete, Internal, Public)
* Column B: FQDN
* Column C: Record Type
* Column D: Record Data
* Column E: Category (of each record, ignored by comparison formula)
* Column F: Comparison with Sheet 2
* Column G: PowerShell "Add-DnsServerResourceRecord" command line


# Sheet 2 "current internal": Exported from internal nameserver

* Column A: FQDN
* Column B: Record Type
* Column C: Record Data

Sheet 2 is generated using "Export-DnsServerZone", and then normalized using:

```powershell
cat current-internal.zone.txt `
| .\ConvertFrom-BindZone.ps1 -Origin example.com `
| ConvertTo-CSV FQDN,Type,Data -NoTypeInformation
```


# Comparison formula for Sheet 1, Column F

```excel
=LET(
  thisname, TRIM(B2),
  thistype, TRIM(C2),
  thisdata, TRIM(D2),
  matches, FILTER('current internal'!C$2:C,'current internal'!A$2:A = thisname,'current internal'!B$2:B = thistype),
  match_count, IF(ISERROR(matches), 0, ROWS(matches)),
  IFS(
    match_count = 0, "Missing",
    match_count = 1, IF(matches = thisdata, "Same (single)", "Different (single)"),
    match_count > 1, IF(COUNTIF(matches, thisdata) > 0, "Found (multiple)", "Not Found (multiple)")
  )
)
```


# Formula to add missing for Sheet 1, Column G

```excel
=IF(
  AND(
    F2 = "Missing",
    A2 <> "Delete",
  ),
  LET(
    domain, "example.com",
    domaindot, domain & ".",
    dotdomaindot, "." & domaindot,
    trimname, TRIM(B2),
    thisname, IF(
      trimname = domaindot,
      ".",
      IF(
        RIGHT(trimname, LEN(dotdomaindot)) = dotdomaindot,
        LEFT(trimname, LEN(trimname) - LEN(dotdomaindot)),
        trimname
      )
    ),
    thistype, TRIM(C2),
    thisdata, TRIM(D2),
    words, IFERROR(
      TEXTSPLIT(thisdata, " "),
      SPLIT(thisdata, " ", TRUE, TRUE)
    ),
    "Add-DnsServerResourceRecord"
    & " " & domain
    & " " & thisname
    & " -" & thistype
    & " " & REDUCE(
      SWITCH(
        thistype,
        "A", "-IPv4Address {1}",
        "NS", 2,
        "CNAME", "-HostNameAlias {1}",
        "SOA", 6,
        "PTR", 12,
        "MX", "-Preference {1} -MailExchange {2}",
        "TXT", "-DescriptiveText '" & thisdata & "'",
        "AAAA", 28,
        "SRV", "-Priority {1} -Weight {2} -Port {3} -DomainName {4}",
        "OPT", 41,
        "DS", 43,
        "RRSIG", 46,
        "NSEC", 47,
        "DNSKEY", 48,
        "TLSA", 52,
        "SVCB", 64,
        "HTTPS", 65,
        "CAA", 257,
        "ANY", 255,
        "Unknown Type"
      ),
      SEQUENCE(1, COLUMNS(words)),
      LAMBDA(
        text,
        idx,
        SUBSTITUTE(
          text,
          "{" & idx & "}",
          INDEX(words, 1, idx)
        )
      )
    )
  ),
  ""
)
```

# Notes

Handle function difference between Excel and Google Sheets using `IFERROR`:

```excel
    IFERROR(
      TEXTSPLIT(thisdata, " "),
      SPLIT(thisdata, " ", TRUE, TRUE)
    ),
```
