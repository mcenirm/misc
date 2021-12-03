#Requires -Version 5

Get-ChildItem Cert:\CurrentUser\My\ `
| Where-Object {
    $_.NotAfter -lt [datetime]::now
} `
| Remove-Item -Verbose
