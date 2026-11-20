#requires -Version 7

[CmdletBinding(PositionalBinding = $false)]
param (
    [Parameter(Position = 0)]
    [Alias('Version', 'MajorVersion', 'Release')]
    [ValidateSet('8', '11', '17', '21', '25', '29')]
    [string]
    $FeatureRelease = '25',

    [Parameter(Position = 1)]
    [Alias('Type')]
    [ValidateSet('JDK', 'JRE')]
    [string]
    $ImageType = 'JDK',

    [Parameter()]
    [Alias('OS')]
    [ValidateSet('windows', 'mac', 'linux', 'aix', 'alpine-linux', 'solaris')]
    [string]
    $OperatingSystem = $(
        if ($IsWindows) { 'windows' }
        elseif ($IsMacOS) { 'mac' }
        elseif ($IsLinux) { 'linux' }
        else { 'windows' }
    ),

    [Parameter()]
    [Alias('Arch')]
    [ValidateSet('x64', 'x86', 'x32', 'aarch64', 'arm', 'ppc64', 'ppc64le', 'riscv64', 's390x', 'sparcv9')]
    [string]$Architecture = $(
        switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture) {
            'X86' { 'x86' }
            'X64' { 'x64' }
            'Arm' { 'arm' }
            'Arm64' { 'aarch64' }
            'S390x' { 's390x' }
            'Ppc64le' { 'ppc64le' }
            'RiscV64' { 'riscv64' }
            default { 'x64' }
        }
    ),

    [Parameter()]
    [ValidateSet('hotspot')]
    [string]$JvmImpl = 'hotspot',

    [Parameter()]
    [ValidateScript(
        { Test-Path $_ -PathType Container },
        ErrorMessage = "Destination directory '{0}' was not found.")
    ]
    [string]
    $DestinationPath = $PWD.Path
)

$relSlug = $FeatureRelease.ToLowerInvariant()
$jvmImplSlug = 'hotspot'
$osSlug = $OperatingSystem.ToLowerInvariant()
$archSlug = $Architecture.ToLowerInvariant()
$imgTypeSlug = $ImageType.ToLowerInvariant()

$params = @{
    architecture = $archSlug
    image_type   = $imgTypeSlug
    os           = $osSlug
}
$queryString = ($params.GetEnumerator() | Sort-Object Key | ForEach-Object {
        "{0}={1}" -f [System.Uri]::EscapeDataString($_.Key), [System.Uri]::EscapeDataString($_.Value)
    }) -join '&'
$apiUrl = 'https://api.adoptium.net/v3/assets/latest/{0}/{1}?{2}' -f @(
    [System.Uri]::EscapeDataString($relSlug)
    [System.Uri]::EscapeDataString($jvmImplSlug)
    $queryString
)

$latest = (Invoke-RestMethod -Uri $apiUrl)[0]
$pkg = $latest.binary.package
$link = $pkg.link
$path = [System.Uri]::EscapeDataString($pkg.name)

$dest = Resolve-Path -Path $DestinationPath
if ($dest.Path -ne $PWD.Path) {
    $path = Join-Path -Path $dest -ChildPath $path
}

if (
    (
        Test-Path -LiteralPath $path
    ) -and (
        (
            (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
        ) -eq (
            $pkg.checksum
        )
    )
) {
    Write-Host "Skipping download of $path"
}
else {
    Write-Host "Downloading $path"
    Write-Host ".......from $link"
    $curlExe = (Get-Command curl -CommandType Application -ErrorAction Stop).Source
    $curlOpts = @(
        '--write-out=%header{location:all:\n}\n'
        '--clobber'
        '--globoff'
        '--location'
        '--remote-time'
        '--output', $path
    )
    & $curlExe @curlOpts $link
}
Get-Item -LiteralPath $path
