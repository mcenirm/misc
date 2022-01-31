#Requires -Version 5

<#
.SYNOPSIS
    Report on local users' password expirations
#>

[CmdletBinding()]
param (
    [string[]]$Name = '*'
)

$Today = [datetime]::Today

Get-LocalUser -Name $Name                            `
| Where-Object { $_.Enabled }                        `
| Select-Object -Property Name, PasswordExpires      `
| Sort-Object -Property PasswordExpires -Descending  `
| ForEach-Object {
    $ExpiresInDays = ($_.PasswordExpires - $Today).TotalDays
    Add-Member                                 `
        -InputObject  $_                       `
        -MemberType   NoteProperty             `
        -Name         'PasswordExpiresInDays'  `
        -Value        $ExpiresInDays
    $_
}
