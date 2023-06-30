#Requires -Version 5

$ErrorActionPreference = 'Stop'


# TODO - Decide if version comparison is even valid between ODT package and setup.exe
# Is setup.exe always older than the ODT package?
#
#  | Version          | File                                 |
#  | ---------------- | ------------------------------------ |
#  | 16.0.16501.20196 | officedeploymenttool_16501-20196.exe |
#  | 16.0.16501.20140 | setup.exe (contained in above)       |
#
$SKIP_VERSION_COMPARISONS = $true


# Constants
$ODT_DOWNLOAD_DETAILS = 'https://www.microsoft.com/en-us/download/details.aspx?id=49117'
$ODT_DOWNLOAD_CONFIRMATION = 'https://www.microsoft.com/en-us/download/confirmation.aspx?id=49117'
$ODT_FILENAME_PREFIX = 'officedeploymenttool_'
$ODT_DOWNLOAD_REGEX = "(https://download\.microsoft\.com/.*?/${ODT_FILENAME_PREFIX}.*?\.exe)"
$ODT_SETUP_IN_PACKAGE = 'setup.exe'
$ODT_VERSION_PREFIX = '16.0.'


# Default filenames
$SourcePathName = 'officedownloads'
$OfficeSetupName = 'officesetup.exe'
$ConfigurationXmlName = 'officeconfig.xml'
$OdtConfirmationCache = "${ODT_FILENAME_PREFIX}confirmation.html"


# Full paths to files
$SourcePath = Join-Path -Path $PSScriptRoot -ChildPath $SourcePathName
$OfficeSetupPath = Join-Path -Path $PSScriptRoot -ChildPath $OfficeSetupName
$ConfigurationXmlPath = Join-Path -Path $PSScriptRoot -ChildPath $ConfigurationXmlName
$TempConfigPath = Join-Path -Path $PSScriptRoot -ChildPath "temp-$ConfigurationXmlName"
$OdtConfirmationCachePath = Join-Path -Path $PSScriptRoot -ChildPath $OdtConfirmationCache


function Get-SetupVersion ($SetupPath) {
    try {
        [System.Version]$v = (Get-ItemPropertyValue -LiteralPath $SetupPath -Name VersionInfo).FileVersion
        # Write-Warning "Version of '$([System.IO.Path]::GetFileName($SetupPath))' is '$v'"
        $v
    }
    catch {
        $null
    }
}


function Get-SetupVersionFromPackageName ($PackageName) {
    $n = $PackageName -replace $ODT_FILENAME_PREFIX, $ODT_VERSION_PREFIX
    $n = $n -replace '-', '.'
    [System.Version]$v = $n
    # Write-Warning "Version from package '$PackageName' is '$v'"
    $v
}


function Test-NeedToUpdate ($ExistingVersion, $LatestVersion) {
    if ($SKIP_VERSION_COMPARISONS) {
        $null -eq $ExistingVersion
    }
    else {
        ($null -eq $ExistingVersion) -or ($ExistingVersion -lt $LatestVersion)
    }
}


function Expand-SetupExe ($SetupExe, $DestinationPath) {
    $cmd = $null
    $errors = [System.Collections.ArrayList]@()
    foreach ($name in @('7z', "${env:ProgramFiles}\7-Zip\7z.exe", "${env:ProgramFiles(x86)}\7-Zip\7z.exe")) {
        try {
            $cmd = (Get-Command -CommandType Application -Name $name).Source
        }
        catch {
            $errors += $_
        }
    }
    if ($null -eq $cmd) {
        $errors | Write-Warning
        throw $errors[0]
    }
    & $cmd e '-aoa' "-o$DestinationPath" $SetupExe
}


# Create configuration file if it does not exist,
# and warn that the file needs manual editing.
if (-not (Test-Path -LiteralPath $ConfigurationXmlPath -PathType Leaf)) {
    Set-Content -LiteralPath $ConfigurationXmlPath -Value @"
<Configuration ID="$(New-Guid)">
  <Info Description="Offline updates for Office 2019" />
<!--

FIXME - SourcePath

Note: This can be the path on the computers without network access.

-->
  <Add
      SourcePath="C:\FIXME\PATH\TO\${SourcePathName}"
      OfficeClientEdition="64"
      Channel="PerpetualVL2019"
      AllowCdnFallback="FALSE"
      >
<!--

FIXME - PIDKEY

-->
    <Product
        PIDKEY="FIXME-FIXME-FIXME-FIXME-FIXME"
        ID="ProPlus2019Volume"
        >
      <Language ID="en-us" />
      <!-- <ExcludeApp ID="Access" /> -->
      <!-- <ExcludeApp ID="Excel" /> -->
      <ExcludeApp ID="Groove" />
      <ExcludeApp ID="Lync" />
      <ExcludeApp ID="OneDrive" />
      <ExcludeApp ID="OneNote" />
      <ExcludeApp ID="Outlook" />
      <!-- <ExcludeApp ID="PowerPoint" /> -->
      <ExcludeApp ID="Publisher" />
      <!-- <ExcludeApp ID="Word" /> -->
    </Product>
  </Add>
  <Property Name="AUTOACTIVATE" Value="1" />
  <Property Name="DeviceBasedLicensing" Value="0" />
  <Property Name="FORCEAPPSHUTDOWN" Value="TRUE" />
  <Property Name="SCLCacheOverride" Value="0" />
  <Property Name="SharedComputerLicensing" Value="0" />
  <Updates Enabled="FALSE" />
  <RemoveMSI />
  <AppSettings>
    <Setup Name="Company" Value="$((Get-ComputerInfo).WindowsRegisteredOrganization)" />
    <User Key="software\microsoft\office\16.0\excel\options" Name="defaultformat" Value="51" Type="REG_DWORD" App="excel16" Id="L_SaveExcelfilesas" />
    <User Key="software\microsoft\office\16.0\powerpoint\options" Name="defaultformat" Value="27" Type="REG_DWORD" App="ppt16" Id="L_SavePowerPointfilesas" />
    <User Key="software\microsoft\office\16.0\word\options" Name="defaultformat" Value="" Type="REG_SZ" App="word16" Id="L_SaveWordfilesas" />
  </AppSettings>
  <Display Level="Full" AcceptEULA="TRUE" />
</Configuration>
"@
    Write-Warning "Created a new Office deployment configuration file:  $ConfigurationXmlPath"
    Write-Warning 'Replace "FIXME" items before trying to use it for installation.'
}


# Create downloads directory if it does not exist
if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
    New-Item -ItemType Directory -Path $SourcePath | Out-Null
}


# Copy existing configuration to temp for download and update SourcePath
[xml]$Cfg = Get-Content -Path $ConfigurationXmlPath
$Cfg.Configuration.Add.SourcePath = (Resolve-Path $SourcePath) -as [string]
$Cfg.Save($TempConfigPath)


# Get details about latest version of officedeploymenttool
try {
    $OdtConfirmationCacheAge = (Get-Date) - (Get-Item -LiteralPath $OdtConfirmationCachePath).LastWriteTime
}
catch {
    $OdtConfirmationCacheAge = $null
}
if (($null -eq $OdtConfirmationCacheAge) -or ($OdtConfirmationCacheAge -gt [timespan]::FromDays(1))) {
    Write-Progress 'Prepare' -Status 'Downloading ODT version information'
    Invoke-WebRequest -Uri $ODT_DOWNLOAD_CONFIRMATION -UseBasicParsing -OutFile $OdtConfirmationCachePath
}
$BestOdtDownloadMatch = Select-String -Pattern $ODT_DOWNLOAD_REGEX -LiteralPath $OdtConfirmationCachePath -AllMatches `
| ForEach-Object -MemberName Matches | ForEach-Object -MemberName Value | Group-Object -NoElement `
| Sort-Object -Property Count -Descending | Select-Object -First 1
if ($null -eq $BestOdtDownloadMatch) {
    Write-Error -Message @"
Unable to determine officedeploymenttool version.

* To troubleshoot, inspect the contents of '$OdtConfirmationCache'.
* Or manually download officedeploymenttool and extract 'setup.exe' as '$OfficeSetupName'
  <$ODT_DOWNLOAD_DETAILS>
"@
}
$OdtDownloadUri = $BestOdtDownloadMatch.Name

# Derive more filenames and paths
$OdtPackageFilename = $OdtDownloadUri -split '/' | Select-Object -Last 1
$OdtPackageName = [System.IO.Path]::GetFileNameWithoutExtension($OdtPackageFilename)
$OdtPackageVersion = Get-SetupVersionFromPackageName $OdtPackageName
$OdtPackagePath = Join-Path -Path $PSScriptRoot -ChildPath $OdtPackageFilename
$OdtPackageExpandedPath = Join-Path -Path $PSScriptRoot -ChildPath $OdtPackageName
$OdtSetupInPackagePath = Join-Path -Path $OdtPackageExpandedPath -ChildPath $ODT_SETUP_IN_PACKAGE


# If officesetup.exe does not exist or is older than latest available,
# then download officedeploymenttool and extract setup.exe.
$OfficeSetupVersion = Get-SetupVersion $OfficeSetupPath
if (Test-NeedToUpdate -ExistingVersion $OfficeSetupVersion -LatestVersion $OdtPackageVersion) {
    # See if we already expanded the package
    $OdtSetupInPackageVersion = Get-SetupVersion $OdtSetupInPackagePath
    if (Test-NeedToUpdate -ExistingVersion $OdtSetupInPackageVersion -LatestVersion $OdtPackageVersion) {
        # See if we already downloaded the package
        if (-not (Test-Path -LiteralPath $OdtPackagePath -PathType Leaf)) {
            Write-Progress 'Prepare' -Status "Downloading ODT package"
            Invoke-WebRequest -Uri $OdtDownloadUri -UseBasicParsing -OutFile $OdtPackagePath
        }
        # Create a folder to hold the contents of the package
        New-Item -Path $OdtPackageExpandedPath -ItemType Directory -Force | Out-Null
        Write-Progress 'Prepare' -Status "Extracting ODT package"
        Expand-SetupExe -SetupExe $OdtPackagePath -DestinationPath $OdtPackageExpandedPath
    }
    # Copy setup.exe to officesetup.exe
    Copy-Item -LiteralPath $OdtSetupInPackagePath -Destination $OfficeSetupPath
}


Write-Progress 'Prepare' -Completed


# Download Office
Write-Progress 'Download' -Status "Running Office downloader"
& $OfficeSetupPath /download $TempConfigPath
if ($false -eq $?) {
    Write-Error "Download failed"
}
Write-Progress 'Download' -Completed

# Determine latest version and clean old versions
$OfficeDataDir = Join-Path -Path $SourcePath -ChildPath 'Office\Data'
$GoalCabPath = Join-Path -Path $OfficeDataDir -ChildPath 'v64.cab'
if (Test-Path -LiteralPath $GoalCabPath) {
    Write-Progress 'Cleaning' -Status "Cleaning"
    $GoalHash = (Get-Item -LiteralPath $GoalCabPath | Get-FileHash).Hash
    Get-ChildItem $OfficeDataDir -Attributes Directory | ForEach-Object {
        $Version = $_.Name
        $Cab = Get-Item -LiteralPath (Join-Path $OfficeDataDir "v64_$Version.cab")
        $Hash = ($Cab | Get-FileHash).Hash
        if ($Hash -eq $GoalHash) {
            Write-Output "Latest version:  $Version"
        }
        else {
            Write-Output "Cleaning old version:  $Version"
            $Cab, $_ | Remove-Item -Recurse
        }
    }
    Write-Progress 'Cleaning' -Completed
}

# TODO show installation command: setup /configure xml
