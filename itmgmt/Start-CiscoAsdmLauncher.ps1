#Requires -Version 5

<#
.SYNOPSIS
    Launch Cisco ASDM
#>

[CmdletBinding()]
param (
    [string]
    $LauncherDir = "$PSScriptRoot\cisco-asdm"
    ,
    [string]
    $SocksProxyHost = ''
    ,
    [int]
    $SocksProxyPort = 0
)

$ErrorActionPreference = 'stop'

$JavaExe = Get-Command -Name java.exe -CommandType Application -All | Where-Object Version -Match 8.* | ForEach-Object Source
$LauncherMainClass = 'com.cisco.launcher.Launcher'
$LauncherMainJar = 'asdm-launcher.jar'
$LauncherMoreJars = @('lzma.jar', 'jploader.jar', 'retroweaver-rt-2.0.jar')
$JavaOpts = @('-Xms64m', '-Xmx512m', '-Dsun.swing.enableImprovedDragGesture=true')
$DefaultCertName = 'cert.PEM'

if ($SocksProxyHost) {
    $JavaOpts += "-DsocksProxyHost=$($SocksProxyHost)"
}

if ($SocksProxyPort -gt 0) {
    $JavaOpts += "-DsocksProxyPort=$($SocksProxyPort)"
}

$asjar = $true

$ArgumentList = $JavaOpts
if ($asjar) {
    $ArgumentList += @('-classpath', ($LauncherMoreJars -join ';'), '-jar', $LauncherMainJar)
}
else {
    $ArgumentList += @('-classpath', (($LauncherMoreJars + @($LauncherMainJar)) -join ';'), $LauncherMainClass)
}
if ($args.Count -gt 0) {
    $ArgumentList += $args
}
elseif (Test-Path -Path (Join-Path -Path $LauncherDir -ChildPath $DefaultCertName) -PathType Leaf) {
    $ArgumentList += @($DefaultCertName)
}

# @($JavaExe) + $ArgumentList | Out-GridView

Start-Process -FilePath $JavaExe -ArgumentList $ArgumentList -WorkingDirectory $LauncherDir
