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

$JavaExe = 'C:\B\jdk8u302-b08-jre\bin\java.exe'
$LauncherMainClass = 'com.cisco.launcher.Launcher'
$LauncherMainJar = 'asdm-launcher.jar'
$LauncherMoreJars = @('lzma.jar', 'jploader.jar', 'retroweaver-rt-2.0.jar')
$JavaOpts = @('-Xms64m', '-Xmx512m', '-Dsun.swing.enableImprovedDragGesture=true')

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
$ArgumentList += $args

@($JavaExe) + $ArgumentList | Out-GridView

Start-Process -FilePath $JavaExe -ArgumentList $ArgumentList -WorkingDirectory $LauncherDir
