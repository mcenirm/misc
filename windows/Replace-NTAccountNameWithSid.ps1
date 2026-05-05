using namespace System.Security.Principal
using namespace System.Text.RegularExpressions

[CmdletBinding(DefaultParameterSetName = 'Name')]
param (
    [Parameter(ParameterSetName = 'Name', ValueFromPipelineByPropertyName, Mandatory, Position = 0)]
    [string[]]
    $AccountName,

    [Parameter(ParameterSetName = 'File', ValueFromPipelineByPropertyName)]
    [Alias('PSPath')]
    [string[]]
    $Path,

    [Parameter(ParameterSetName = 'Object', ValueFromPipeline)]
    [psobject]
    $InputObject,

    [ValidateCount(2, 2)]
    [string[]]
    $MarkerPair = ("{{", "}}")
)

begin {
    function nameToSid([string]$name) {
        return ([NTAccount]$name).Translate([SecurityIdentifier]).Value
    }

    $pattern = [regex]::Escape($MarkerPair[0]) + '(?<AccountName>.+?)' + [regex]::Escape($MarkerPair[1])

    $callback = {
        param([Match]$match)
        $name = $match.Groups['AccountName'].Value
        $sid = try { nameToSid -name $name } catch { $match.Value }
        return $sid
    }
}

process {
    switch ($PSCmdlet.ParameterSetName) {
        'Name' {
            $AccountName | ForEach-Object {
                $acctName = $_
                $sid = try { nameToSid -name $acctName } catch { $null }
                [PSCustomObject]@{
                    Name = $acctName
                    Sid  = $sid
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
