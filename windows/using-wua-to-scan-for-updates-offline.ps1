# https://docs.microsoft.com/en-us/windows/win32/wua_sdk/using-wua-to-scan-for-updates-offline

$ErrorActionPreference = 'Stop'

$SecurityUpdatesCatalogFile = 'wsusscn2.cab'
$SecurityUpdatesCatalogPath = "$PSScriptRoot\wsusscn2.cab"

if (-not (Test-Path -LiteralPath $SecurityUpdatesCatalogPath)) {
    Write-Warning "Missing security updates catalog: $SecurityUpdatesCatalogFile"
    Write-Warning 'Obtain it from: http://download.windowsupdate.com/microsoftupdate/v6/wsusscan/wsusscn2.cab'
    Write-Error "Missing security updates catalog: $SecurityUpdatesCatalogFile"
}

$UpdateSession = New-Object -ComObject Microsoft.Update.Session
$UpdateServiceManager = New-Object -ComObject Microsoft.Update.ServiceManager
$UpdateService = $UpdateServiceManager.AddScanPackageService('Offline Sync Service', $SecurityUpdatesCatalogPath)
$UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
$UpdateSearcher.ServerSelection = 3 # ssOthers
$UpdateSearcher.ServiceID = $UpdateService.ServiceID

Write-Progress -Activity 'Searching for updates...'
$SearchResult = $UpdateSearcher.Search('IsInstalled=0')
Write-Progress -Activity 'Searching for updates...' -Completed

$global:MissingMicrosoftUpdates = $SearchResult.Updates
if ($global:MissingMicrosoftUpdates.Count -lt 1) {
    Write-Warning 'There are no applicable updates.'
}
else {
    $global:MissingMicrosoftUpdates | ForEach-Object {
        [PSCustomObject]@{
            KBs       = $_.KBArticleIDs -join ','
            Bulletins = $_.SecurityBulletinIDs -join ','
            Title     = $_.Title
        }
    } | Format-Table -AutoSize | Out-String | Write-Warning
    Write-Warning 'Note: The list of missing updates is stored in $MissingMicrosoftUpdates'
}
