#Requires -Version 5

Get-ChildItem Cert:\CurrentUser\My\ `
| Where-Object {
    $_.Issuer -match '^CN=DOD '
} `
| Remove-Item -Verbose
