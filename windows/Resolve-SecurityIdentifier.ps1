param (
    [string]$SID
)

$securityIdentifier = New-Object System.Security.Principal.SecurityIdentifier($SID)
$identity = $securityIdentifier.Translate([System.Security.Principal.NTAccount])
Write-Output $identity.Value
