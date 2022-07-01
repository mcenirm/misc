[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [string]
    $BackupName,
    [Parameter(Mandatory = $true)]
    [string]
    $GpoName
)

$ErrorActionPreference = 'Stop'
$LgpoExe = "${PSScriptRoot}\..\LGPO_30\lgpo.exe"
$BackupPath = "${PSScriptRoot}\backup ${env:COMPUTERNAME} ${BackupName}"

if (Test-Path -LiteralPath $BackupPath) {
    Write-Error -Message "Backup path already exists: ${BackupPath}"
}

$BackupDirectory = New-Item -Path $BackupPath -ItemType Directory

& $LgpoExe /b $BackupPath /n $GpoName
