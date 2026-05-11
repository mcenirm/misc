$f = 'wsusscn2.cab'
$u = "https://catalog.s.download.windowsupdate.com/microsoftupdate/v6/wsusscan/$f"
$curlArgs = @(
    if (Test-Path -LiteralPath $f) {
        '--time-cond', $f
    }
    '--write-out', '%{response_code}  (200 OK; 304 Not Modified)'
    '--location'
    '--remote-time'
    '--output', $f
    $u
)

& curl.exe @curlArgs
