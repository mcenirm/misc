#Requires -Version 5

$SourcePathName = 'officedownloads'
$OfficeSetupName = 'officesetup.exe'
$ConfigurationXmlName = 'officeconfig.xml'

$SourcePath = Join-Path -Path $PSScriptRoot -ChildPath $SourcePathName
$OfficeSetupPath = Join-Path -Path $PSScriptRoot -ChildPath $OfficeSetupName
$ConfigurationXmlPath = Join-Path -Path $PSScriptRoot -ChildPath $ConfigurationXmlName
$TempConfigPath = Join-Path -Path $PSScriptRoot -ChildPath "temp-$ConfigurationXmlName"

# Create downloads directory if it doesn't exist
if (-not (Test-Path $SourcePath -PathType Container)) {
    New-Item -ItemType Directory -Path $SourcePath | Out-Null
}

# Copy existing configuration to temp and update SourcePath
# TODO if missing config file, then link to https://config.office.com/ to generate new one
[xml]$Cfg = Get-Content -Path $ConfigurationXmlPath
$Cfg.Configuration.Add.SourcePath = (Resolve-Path $SourcePath) -as [string]
$Cfg.Save($TempConfigPath)

# Download Office updates
# TODO if missing setup, then link to https://www.microsoft.com/en-us/download/details.aspx?id=49117 to download
& $OfficeSetupPath /download $TempConfigPath

# Determine latest version and clean old versions
$OfficeDataDir = Join-Path -Path $SourcePath -ChildPath 'Office\Data'
$GoalCabPath = Join-Path -Path $OfficeDataDir -ChildPath 'v64.cab'
if (Test-Path -LiteralPath $GoalCabPath) {
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
}

# TODO show installation command: setup /configure xml
