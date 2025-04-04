foreach ($arg in $args) {
    $csvfile = Get-Item -Path $arg
    $csv = Import-Csv -LiteralPath $csvfile.FullName
    if ($null -ne $csv) {
        $exportsdir = Join-Path -Path $csvfile.Directory -ChildPath "$($csvfile.BaseName) exports"
        if (-not (Test-Path -LiteralPath $exportsdir -PathType Container)) {
            New-Item -ItemType Directory -Path $exportsdir | Out-Null
        }
        $exportsdir = Get-Item -LiteralPath $exportsdir

        $staticsdir = Join-Path -Path $csvfile.Directory -ChildPath "$($csvfile.BaseName) statics"
        if (-not (Test-Path -LiteralPath $staticsdir -PathType Container)) {
            New-Item -ItemType Directory -Path $staticsdir | Out-Null
        }
        $staticsdir = Get-Item -LiteralPath $staticsdir

        foreach ($setting in $csv) {
            $parts = $setting.path -split '\\'
            if ($parts[0] -eq '' -and $parts[1] -eq '') {
                $context = $parts[2]
                $path = $parts[3..$parts.Count] -join '\'
                $severity = $setting.severity -replace '\*', ''
                # from [System.IO.Path]::GetInvalidFileNameChars()
                $expname = $setting.title -replace '[\u0000\u0001\u0002\u0003\u0004\u0005\u0006\u0007\u0008\u0009\u000a\u000b\u000c\u000d\u000e\u000f\u0010\u0011\u0012\u0013\u0014\u0015\u0016\u0017\u0018\u0019\u001a\u001b\u001c\u001d\u001e\u001f\u0022\u002a\u002f\u003a\u003c\u003e\u003f\u005c\u007c]', ' '
                $expname = $expname -replace ' +', ' '
                $expname = $expname.Trim()
                [System.Collections.ArrayList] $words = $expname -split ' '
                $ascsid = $words[0]
                $words.RemoveAt(0)
                $expname = $words -join ' '
                $maxlen = 90
                $ellipsis = '⋯'
                if ($expname.Length -gt $maxlen -and $words.Count -gt 3) {
                    $words[$words.Count - 2] = $ellipsis
                    $expname = $words -join ' '
                }
                while ($expname.Length -gt $maxlen -and $words.Count -gt 4) {
                    $words.RemoveAt($words.Count - 3)
                    $expname = $words -join ' '
                }
                if ($expname.Length -gt $maxlen) {
                    $endlen = 6
                    $expname = @(
                        $expname.Substring(0, $maxlen - $endlen - $ellipsis.Length),
                        $ellipsis,
                        $expname.Substring($expname.Length - $endlen)
                    ) -join ''
                }
                $expname = @($severity, $ascsid, $expname) -join ' '

                if ($setting.type_ -eq 'WMI Query') {
                    $wmiqfile = Join-Path -Path $staticsdir -ChildPath "$expname.wmi-query.txt"
                    if (Test-Path -LiteralPath $wmiqfile) {
                        continue
                    }

                    $setting
                    $wmiqfile
                    break
                }

                if ($context -eq 'HKLM' -or $context -eq 'HKCU') {
                    $hkey = switch ($context) {
                        'HKLM' { 'HKEY_LOCAL_MACHINE' }
                        'HKCU' { 'HKEY_CURRENT_USER' }
                        default { $null }
                    }
                    $valname = $setting.nasa_control
                    $valname = $valname -replace '\\', '\\'
                    $valname = $valname -replace '"', '\"'
                    $valtype = $setting.type_
                    $value = $setting.control_setting

                    switch ($valtype) {
                        'REG_DWORD' {
                            $valtype = 'dword'
                            $comment = ''
                        }
                        'REG_SZ' {
                            $valtype = 'hex(1)'
                            $comment = "; value: ${value}`n"
                            $value = [System.Text.Encoding]::Unicode.GetBytes($value + "`0`0")
                        }
                        default { $null }
                    }

                    if ($null -eq $valtype -and '' -ne $value) {
                        # TODO
                        "Unsure how to handle a registry value missing a type"
                        $setting
                        break
                    }

                    if ($value -is [byte[]]) {
                        $value = ($value | ForEach-Object { "{0:X2}" -f $_ }) -join ','
                        $maxlen = 80
                        $hexsize = 3
                        $contchar = '\'
                        $indent = '  '
                        $spacer = "$contchar`n$indent"
                        $incr = $hexsize * [int][Math]::Floor(($maxlen - $contchar.Length - $indent.Length) / $hexsize)
                        $prefixlen = "`"${valname}`"=${valtype}:".Length
                        [System.Collections.ArrayList]$lines = @()
                        $i = 0
                        $j = $hexsize * [int][Math]::Floor(($maxlen - $prefixlen) / $hexsize)
                        while ($j -lt $value.Length) {
                            $lines.Add($value.Substring($i, $j - $i)) | Out-Null
                            $i = $j
                            $j += $incr
                        }
                        if ($i -lt $value.Length) {
                            $lines.Add($value.Substring($i)) | Out-Null
                        }
                        $value = $lines -join $spacer
                    }

                    $expext = '.reg.txt'
                    if ($null -eq $valtype -and '' -eq $value) {
                        $expext = '.reg.TODO'
                        $valtype = '<<TODO>>'
                        $value = '<<TODO>>'
                    }
                    # $key = "${context}:\$path"
                    # & reg export "$context\$path" dummy.reg /y
                    $expfile = Join-Path -Path $exportsdir -ChildPath "$expname$expext"
                    $exp = New-Item -ItemType File -Path $expfile -Force -Value @"
Windows Registry Editor Version 5.00

; $($setting.title)
$comment

[${hkey}\${path}]
"${valname}"=${valtype}:${value}

"@
                    continue
                }
                elseif ($context -eq 'Security Template') {
                    # TODO
                    continue
                }
                elseif ($context -eq 'Audit Policy') {
                    # TODO
                    continue
                }
            }
            $setting
            break
        }
    }
}
