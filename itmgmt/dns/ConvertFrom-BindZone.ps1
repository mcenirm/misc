<#
    .SYNOPSIS
        Parses BIND DNS zone file content and outputs structured PSCustomObjects.
    .DESCRIPTION
        Accepts raw BIND zone text via pipeline or parameter, handles multi-line records,
        tracks $ORIGIN and $TTL directives, and outputs objects with normalized fields.
    .PARAMETER ZoneContent
        The raw lines or full text content of a BIND zone file.
    .EXAMPLE
        Get-Content ./example.com.zone | ConvertFrom-BindZone | Out-GridView
    .EXAMPLE
        $zoneText = Get-Content ./example.com.zone
        ConvertFrom-BindZone -ZoneContent $zoneText | Export-Csv -Path ./records.csv -NoTypeInformation
    #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, ValueFromPipeline = $true, ValueFromPipelineByPropertyName = $true)]
    [AllowEmptyString()]
    [string[]]$ZoneContent,

    [Parameter(Mandatory = $false, Position = 0)]
    [string]$Origin = 'example.com'
)

begin {
    $script:lines = [System.Collections.Generic.List[string]]::new()
    $script:inParentheses = $false
    $script:buffer = ""

    # Parser state variables
    $script:origin = $Origin
    $script:defaultTtl = "3600"
    $script:lastOwner = "@"

    # Regex pattern matching standard Resource Records (RRs) and directives
    $script:rrRegex = [regex](
        @(
            '^'
            '(?<Name>\S*\s+)?'
            '(?:(?<TTL>\d+[smhdw]?)\s+)?'
            '(?:(?<Class>IN|CH|HS)\s+)?'
            '(?<Type>A|AAAA|CNAME|MX|TXT|NS|PTR|SRV|SOA)\s+'
            '(?<Data>.+)'
            '$'
        ) -join ''
    )
}

process {
    foreach ($item in $ZoneContent) {
        if ([string]::IsNullOrEmpty($item)) { continue }

        # Split multiline inputs (e.g. from Get-Content -Raw) into discrete lines
        $inputLines = $item -split '\r?\n'

        foreach ($line in $inputLines) {
            # Strip BIND comments starting with ';' unless escaped or inside quotes
            $lineClean = ($line -split ';(?=(?:[^"]*"[^"]*")*[^"]*$)')[0].TrimEnd()
            if ([string]::IsNullOrWhiteSpace($lineClean)) { continue }

            # Handle multi-line records wrapped in parentheses (e.g., SOA or multiline TXT)
            if ($lineClean -match '\(' -and -not ($lineClean -match '\)')) {
                $script:inParentheses = $true
                $script:buffer += ($lineClean -replace '\(', ' ') + " "
                continue
            }

            if ($script:inParentheses) {
                if ($lineClean -match '\)') {
                    $script:inParentheses = $false
                    $script:buffer += ($lineClean -replace '\)', ' ')
                    $script:lines.Add($script:buffer.Trim())
                    $script:buffer = ""
                }
                else {
                    $script:buffer += $lineClean + " "
                }
                continue
            }

            $script:lines.Add($lineClean)
        }
    }
}

end {
    foreach ($line in $script:lines) {
        # 1. Check for $ORIGIN directive
        if ($line -match '^\$ORIGIN\s+(?<Origin>\S+)') {
            $script:origin = $Matches['Origin'].TrimEnd('.')
            continue
        }

        # 2. Check for $TTL directive
        if ($line -match '^\$TTL\s+(?<TTL>\S+)') {
            $script:defaultTtl = $Matches['TTL']
            continue
        }

        # 3. Parse Resource Records
        if ($line -match $script:rrRegex) {
            $name = $Matches['Name']
            $ttl = if ($Matches['TTL']) { $Matches['TTL'] } else { $script:defaultTtl }
            $class = if ($Matches['Class']) { $Matches['Class'] } else { "IN" }
            $type = $Matches['Type']
            $data = $Matches['Data'].Trim()

            # Inherit previous record's owner name if blank (starts with space/tab in BIND)
            if ([string]::IsNullOrWhiteSpace($name)) {
                $name = $script:lastOwner
            }
            else {
                $name = $name.Trim()
                $script:lastOwner = $name
            }

            # Resolve standard BIND FQDN expansion rules
            $fqdn = $name
            if ($name -eq "@") {
                $fqdn = if ($script:origin) { $script:origin } else { "@" }
            }
            elseif (-not $name.EndsWith(".") -and $script:origin) {
                $fqdn = "$name.$script:origin"
            }
            $fqdn = $fqdn.TrimEnd('.') + '.'

            # Clean up whitespace
            $data = $data -replace '\s+', ' '

            # Output PSCustomObject down the pipeline
            [PSCustomObject]@{
                PSTypeName = 'BindZoneRecord'
                Name       = $name
                FQDN       = $fqdn
                TTL        = $ttl
                Class      = $class
                Type       = $type
                Data       = $data
            }
        }
    }
}
