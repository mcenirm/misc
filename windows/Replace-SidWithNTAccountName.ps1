using namespace System.Security.Principal
using namespace System.Text.RegularExpressions

[CmdletBinding(DefaultParameterSetName = 'Sid')]
param (
    [Parameter(ParameterSetName = 'Sid', ValueFromPipelineByPropertyName, Mandatory, Position = 0)]
    [string[]]
    $Sid,

    [Parameter(ParameterSetName = 'File', ValueFromPipelineByPropertyName)]
    [Alias('PSPath')]
    [string[]]
    $Path,

    [Parameter(ParameterSetName = 'Object', ValueFromPipeline)]
    [psobject]
    $InputObject,

    [ValidateCount(2, 2)]
    [string[]]
    $MarkerPair = ("{{", "}}"),

    [switch]
    $SkipDomain,

    [string[]]
    $UnskippableDomains = ('NT SERVICE', 'RESTRICTED SERVICES', 'Window Manager')
)

begin {
    function sidToName([string]$sid) {
        $name = ([SecurityIdentifier]$sid).Translate([NTAccount]).Value
        if ($SkipDomain -and ($name -like '*\*')) {
            $domain, $name = $name -split '\\'
            if ($UnskippableDomains -contains $domain) {
                $name = $domain + '\' + $name
            }
        }
        return $name
    }
    $pattern = '\bS-1-(\d+-){1,14}\d+'
    $callback = {
        param([Match]$match)
        $sid = $match.Value
        $name = try { $MarkerPair -join (sidToName -sid $sid) } catch { $sid }
        return $name
    }
}

process {
    switch ($PSCmdlet.ParameterSetName) {
        'Sid' {
            foreach ($sid_ in $Sid) {
                $name = try { sidToName -sid $sid_ } catch { $null }
                [PSCustomObject]@{
                    Sid  = $sid_
                    Name = $name
                }
            }
        }
        'File' {
            Get-Content -Path $Path | ForEach-Object {
                [regex]::Replace($_.ToString(), $pattern, $callback, [RegexOptions]::IgnoreCase)
            }
        }
        'Object' {
            $InputObject | ForEach-Object {
                [regex]::Replace($_.ToString(), $pattern, $callback, [RegexOptions]::IgnoreCase)
            }
        }
    }
}
