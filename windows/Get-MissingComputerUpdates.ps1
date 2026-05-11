#Requires -RunAsAdministrator

# from https://gist.github.com/joerodgers/07cd97c6e4d84c23d4609d9a3b81bcae

# download latest wsusscn2.cab from http://go.microsoft.com/fwlink/p/?linkid=74689
$wsussCabPath = "$PSScriptRoot\wsusscn2.cab"

function timestamp { Get-Date -Format 'yyyy-MM-dd HH:mm:ss' }

Write-Host "$(timestamp) - Loading Windows Update offline scan file"

# setup

$session = New-Object -ComObject Microsoft.Update.Session 
$serviceManager = New-Object -ComObject Microsoft.Update.ServiceManager 
$packageService = $serviceManager.AddScanPackageService("Offline Sync Service", $wsussCabPath, 1) 

# create the update searcher

$updateSearcher = $session.CreateUpdateSearcher()
$updateSearcher.ServerSelection = 3 # Indicates some update service other than those listed previously. If the ServerSelection property of a Windows Update Agent API object is set to ssOthers, then the ServiceID property of the object contains the ID of the service.
$updateSearcher.ServiceID = $packageService.ServiceID.ToString() 
$updateSearcher.IncludePotentiallySupersededUpdates = $false

Write-Host "$(timestamp) - Scanning $($env:COMPUTERNAME) for missing updates"
 
# search for missing updates: IsInstalled=0

$searchResult = $updateSearcher.Search("IsInstalled=0")

# save results

$missingUpdates = $searchResult.Updates | Select-Object Title, Description, MsrcSeverity

$missingUpdates | Export-Csv -Path "MissingUpdates_$($env:COMPUTERNAME)_$(Get-Date -Format 'yyyy-MM-dd-HHmmss').csv" -NoTypeInformation

if ($missingUpdates.Count -lt 1) {
    Write-Host "$(timestamp) - No missing updates found"
}
else {
    Write-Host "$(timestamp) - Found $($missingUpdates.Count) missing updates"
    $missingUpdates | Format-Table Title, MsrcSeverity -Auto
}
