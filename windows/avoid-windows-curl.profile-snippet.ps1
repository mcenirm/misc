# Note: Add to `$PROFILE`


### Avoid Windows curl
function Guess-BestCurlExe {
    $curlsToAvoid = @(
        "$($env:SystemRoot)\System32\curl.exe"
    )

    $existingCurls = Get-Command -Name curl -CommandType Application | Where-Object {
        $curlsToAvoid -notcontains $_.Source
    }
    if ($existingCurls.Count -gt 0) {
        return $existingCurls[0].Source
    }

    $giArgs = @{
        ErrorAction = 'SilentlyContinue'
        Path        = @(
            $env:LOCALAPPDATA
            'Microsoft'
            'WinGet'
            'Packages'
            'cURL.cURL_Microsoft.Winget.Source_8wekyb3d8bbwe'
            'curl-*-mingw'
            'bin'
            'curl.exe'
        ) -join '\'
    }
    $winGetCurls = Get-Item @giArgs | Where-Object {
        $_.VersionInfo.ProductName -eq 'The curl executable'
    } | Sort-Object {
        $_.VersionInfo.ProductVersionRaw -as [version]
    } -Descending
    if ($winGetCurls.Count -gt 0) {
        return $winGetCurls[0].FullName
    }

    return $null
}
if (Test-Path Alias:curl) { Remove-Item Alias:curl }
if (Test-Path Alias:curl) { Remove-Item Alias:curl }
Guess-BestCurlExe | ForEach-Object {
    if ($null -ne $_) {
        Set-Alias -Name curl -Value $_
    }
}
