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
    $SocksProxyHost = $null
    ,
    [int]
    $SocksProxyPort = $null
)

$JavaExe = 'C:\B\jdk8u302-b08-jre\bin\java.exe'
$LauncherMainClass = 'com.cisco.launcher.Launcher'
$LauncherMainJar = 'asdm-launcher.jar'
$LauncherMoreJars = @('lzma.jar', 'jploader.jar', 'retroweaver-rt-2.0.jar')
$JavaOpts = @('-Xms64m', '-Xmx512m', '-Dsun.swing.enableImprovedDragGesture=true')

if ($SocksProxyHost -ne $null) {
    $JavaOpts += "-DsocksProxyHost=$($SocksProxyHost)"
}

if ($SocksProxyPort -ne $null) {
    $JavaOpts += "-DsocksProxyPort=$($SocksProxyPort)"
}

$asjar = $true

$cmdpart1 = @( $JavaExe ) + $JavaOpts
if ($asjar) {
    $cmdpart2 = @('-classpath', ($LauncherMoreJars -join ';'), '-jar', $LauncherMainJar)
}
else {
    $cmdpart2 = @('-classpath', (($LauncherMoreJars + @($LauncherMainJar)) -join ';'), $LauncherMainClass)
}
$cmdpart3 = $args

$cmd = $cmdpart1 + $cmdpart2 + $cmdpart3
$cmd | Out-GridView

& ($cmd | Select-Object -First 1) ($cmd | Select-Object -Skip 1)
