# Note: Add to `$PROFILE`


### Avoid Windows curl
function Guess-BestCurlExe {
    $CurlsToAvoid = @(
        "$($env:SystemRoot)\System32\curl.exe"
    )

    # First found (eg, in PATH) is best
    $ExistingCurls = Get-Command -Name curl -CommandType Application | Where-Object {
        $CurlsToAvoid -notcontains $_.Source
    }
    if ($ExistingCurls.Count -gt 0) {
        return $ExistingCurls[0].Source
    }

    # Highest version is best
    $WinGetCurls = Get-Item -Path "$($env:LOCALAPPDATA)\Microsoft\WinGet\Packages\cURL.cURL_Microsoft.Winget.Source_8wekyb3d8bbwe\curl-*-mingw\bin\curl.exe" | Where-Object {
        $_.VersionInfo.ProductName -eq 'The curl executable'
    } | Sort-Object {
        $_.VersionInfo.ProductVersionRaw -as [version]
    } -Descending
    if ($WinGetCurls.Count -gt 0) {
        return $WinGetCurls[0].FullName
    }

    return $null
}
# TODO I forget why this needed two attempts...
if (Test-Path Alias:curl) { Remove-Item Alias:curl }
if (Test-Path Alias:curl) { Remove-Item Alias:curl }
Set-Alias -Name curl -Value (Guess-BestCurlExe)
