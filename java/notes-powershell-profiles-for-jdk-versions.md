
* Extract contents of JDK 21 to `C:\B\jdk\jdk21\` (ie, such that `C:\B\jdk\jdk21\bin\java.exe` exists)

* Create `C:\B\jdk\jdk21.ps1`:

```pwsh
$env:JAVA_HOME = "$PSScriptRoot\jdk21"

$env:PATH = (
    @("$($env:JAVA_HOME)\bin") + (
        $env:PATH -split ';' |
        Where-Object {
            $_ -ne "$($env:JAVA_HOME)\bin"
        }
    )
) -join ';'
```

* Repeat for other JDK versions

* Add snippet to `$PROFILE`:

```pwsh
Get-ChildItem -Path C:\B\jdk -Filter jdk*.ps1 |
ForEach-Object {
    Set-Alias -Name $_.BaseName -Value "$($_.Directory)\$($_.BaseName)"
}
```

To switch to a JDK version:

```pwsh
jdk21
Get-Command java
java -version
```
