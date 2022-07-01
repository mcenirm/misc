
$ErrorActionPreference = 'Stop'

$OutputAsJson = $false

$ComputerName = $env:COMPUTERNAME
if ($ComputerName -match 'localhost') {
    $Answer = (Read-Host -Prompt "Computer name? [$ComputerName]").Trim()
    if ([bool] $Answer) {
        $ComputerName = $Answer
    }
}

$InventoryTimestamp = [datetime]::UtcNow
$InventoryTimestampS = $InventoryTimestamp.ToString("yyyyMMdd'-'HHmmss'z'", [System.Globalization.DateTimeFormatInfo]::InvariantInfo)

$WhereWhen = [ordered] @{
    InventoryTimestampUtc = $InventoryTimestamp
    ComputerName          = $ComputerName
}
$WhereWhenS = "$ComputerName $InventoryTimestampS"

$ResultsDirectoryName = "Inventory $WhereWhenS"
$Prefix = "$ResultsDirectoryName\$WhereWhenS "

New-Item -ItemType Directory -Path . -Name $ResultsDirectoryName | Out-Null

$ProgressActivity = 'Collecting inventory'

##########

$Tag = 'LocalUser'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
$LocalUsers = Get-LocalUser | Sort-Object -Property Name
if ($OutputAsJson) {
    $LocalUsers | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$LocalUsers | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            Name        = $_.Name
            Description = $_.Description

            # AccountExpires         = $_.AccountExpires
            Enabled     = $_.Enabled
            FullName    = $_.FullName
            # LastLogon              = $_.LastLogon
            # ObjectClass            = $_.ObjectClass
            # PasswordChangeableDate = $_.PasswordChangeableDate
            # PasswordExpires        = $_.PasswordExpires
            # PasswordLastSet        = $_.PasswordLastSet
            # PasswordRequired       = $_.PasswordRequired
            # PrincipalSource        = $_.PrincipalSource
            # SID                    = $_.SID
            # UserMayChangePassword  = $_.UserMayChangePassword
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$LocalGroups = Get-LocalGroup | Sort-Object -Property Name
$LocalGroupsWithMembers = $LocalGroups | ForEach-Object {
    $m = $_ | Get-LocalGroupMember | Sort-Object -Property Name
    if ($null -eq $m) {
        # ConvertTo-Json writes $null as empty object "{}" instead of empty list "[]"
        $m = @()
    }
    @{
        Group   = $_
        Members = $m
    }
}

$Tag = 'LocalGroup'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
if ($OutputAsJson) {
    $LocalGroups | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$LocalGroups | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            Name        = $_.Name
            Description = $_.Description

            # ObjectClass     = $_.ObjectClass
            # PrincipalSource = $_.PrincipalSource
            # SID             = $_.SID
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

$Tag = 'LocalGroupMember'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
if ($OutputAsJson) {
    $LocalGroupsWithMembers | ConvertTo-Json -Depth 2 | Set-Content -Path "${Prefix}${Tag}.json"
}
$LocalGroupsWithMembers | ForEach-Object {
    $g = $_.Group.Name
    $_.Members | ForEach-Object {
        New-Object PSObject -Property ($WhereWhen + [ordered] @{
                Group                 = $g
                Member                = $_.Name
                MemberObjectClass     = $_.ObjectClass
                MemberPrincipalSource = $_.PrincipalSource
            })
    }
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$Tag = 'Win32 Package'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
$Win32Packages = Get-Package -AllVersions -IncludeWindowsInstaller -IncludeSystemComponent | Sort-Object -Property Name, Version
if ($OutputAsJson) {
    $Win32Packages | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$Win32Packages | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            Status               = $_.Status
            Name                 = $_.Name
            Version              = $_.Version
            FullPath             = $_.FullPath
            
            # AppliesToMedia             = $_.AppliesToMedia
            # Attributes                 = $_.Attributes
            CanonicalId          = $_.CanonicalId
            # Culture                    = $_.Culture
            # Dependencies               = $_.Dependencies
            # Entities                   = $_.Entities
            # Evidence                   = $_.Evidence
            FastPackageReference = $_.FastPackageReference
            FromTrustedSource    = $_.FromTrustedSource
            # IsCorpus                   = $_.IsCorpus
            # IsPatch                    = $_.IsPatch
            # IsSupplemental             = $_.IsSupplemental
            # Links                      = $_.Links
            # Meta                       = $_.Meta
            # Metadata                   = $_.Metadata
            # PackageFilename            = $_.PackageFilename
            # Payload                    = $_.Payload
            # PropertyOfSoftwareIdentity = $_.PropertyOfSoftwareIdentity
            ProviderName         = $_.ProviderName
            # SearchKey                  = $_.SearchKey
            # Source                     = $_.Source
            # Summary                    = $_.Summary
            # SwidTags                   = $_.SwidTags
            # SwidTagText                = $_.SwidTagText
            # TagId                      = $_.TagId
            # TagVersion                 = $_.TagVersion
            VersionScheme        = $_.VersionScheme
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$Tag = 'AppxPackage AllUsers'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
$AppxPackages = @("Bundle", "Framework", "Main", "Resource", "None") | ForEach-Object {
    Get-AppxPackage -AllUsers -PackageTypeFilter $_ | Add-Member 'PackageType' $_ -PassThru
} | Sort-Object -Property Name, Version
if ($OutputAsJson) {
    $AppxPackages | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$AppxPackages | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            Name                   = $_.Name
            Version                = $_.Version
            StatusName             = $_.Status.Tostring()
        
            PackageType            = $_.PackageType
            ArchitectureName       = $_.Architecture.Tostring()
            SignatureKindName      = $_.SignatureKind.Tostring()
            
            Architecture           = $_.Architecture
            # Dependencies           = $_.Dependencies
            InstallLocation        = $_.InstallLocation
            IsBundle               = $_.IsBundle
            IsDevelopmentMode      = $_.IsDevelopmentMode
            IsFramework            = $_.IsFramework
            IsPartiallyStaged      = $_.IsPartiallyStaged
            IsResourcePackage      = $_.IsResourcePackage
            NonRemovable           = $_.NonRemovable
            PackageFamilyName      = $_.PackageFamilyName
            PackageFullName        = $_.PackageFullName
            # PackageUserInformation = $_.PackageUserInformation
            Publisher              = $_.Publisher
            PublisherId            = $_.PublisherId
            ResourceId             = $_.ResourceId
            SignatureKind          = $_.SignatureKind
            Status                 = $_.Status

            PackageUserInformation = $_.PackageUserInformation -join "`n"
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$Tag = 'AppxProvisionedPackage'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
$AppxProvisionedPackages = Get-AppxProvisionedPackage -Online | Sort-Object -Property DisplayName, Version
if ($OutputAsJson) {
    $AppxProvisionedPackages | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$AppxProvisionedPackages | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            DisplayName      = $_.DisplayName
            Version          = $_.Version

            ArchitectureName = [Windows.System.ProcessorArchitecture].GetEnumName($_.Architecture)

            Architecture     = $_.Architecture
            # Build            = $_.Build
            InstallLocation  = $_.InstallLocation
            # LogLevel         = $_.LogLevel
            # LogPath          = $_.LogPath
            # MajorVersion     = $_.MajorVersion
            # MinorVersion     = $_.MinorVersion
            # Online           = $_.Online
            PackageName      = $_.PackageName
            # Path             = $_.Path
            PublisherId      = $_.PublisherId
            Regions          = $_.Regions
            ResourceId       = $_.ResourceId
            # RestartNeeded    = $_.RestartNeeded
            # Revision         = $_.Revision
            # ScratchDirectory = $_.ScratchDirectory
            # SysDrivePath     = $_.SysDrivePath
            # WinPath          = $_.WinPath
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$Tag = 'WindowsOptionalFeature'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
$AllWindowsOptionalFeatures = Get-WindowsOptionalFeature -Online -FeatureName *
# $EnabledWindowsOptionalFeatures = $AllWindowsOptionalFeatures | Where-Object { $_.State -eq 'Enabled' }
if ($OutputAsJson) {
    $AllWindowsOptionalFeatures | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$AllWindowsOptionalFeatures | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            State       = $_.State
            FeatureName = $_.FeatureName

            # CustomProperties = $_.CustomProperties
            Description = $_.Description
            DisplayName = $_.DisplayName
            # LogLevel         = $_.LogLevel
            # LogPath          = $_.LogPath
            # Online           = $_.Online
            # Path             = $_.Path
            # RestartNeeded    = $_.RestartNeeded
            # RestartRequired  = $_.RestartRequired        
            # ScratchDirectory = $_.ScratchDirectory
            # SysDrivePath     = $_.SysDrivePath
            # WinPath          = $_.WinPath
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$Tag = 'WindowsCapability'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
$AllWindowsCapabilities = Get-WindowsCapability -Online -LimitAccess -Name *
# $InstalledWindowsCapabilities = $AllWindowsCapabilities | Where-Object { $_.State -eq 'Installed' }
if ($OutputAsJson) {
    $AllWindowsCapabilities | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$AllWindowsCapabilities | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            State        = $_.State
            Name         = $_.Name

            Description  = $_.Description
            DisplayName  = $_.DisplayName
            DownloadSize = $_.DownloadSize
            InstallSize  = $_.InstallSize
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$Tag = 'Service'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
$ExcludedProperties = @(
    'CimInstanceProperties',
    'CimSystemProperties',
    'ClassGuid',
    'ConfigFile',
    'DataFile',
    'DefaultDataType',
    'DependentFiles',
    'Description',
    'FilePath',
    'HelpFile',
    'InstallDate',
    'MonitorName',
    'OEMUrl',
    'PDO',
    'ProcessID',
    'PSComputerName',
    'SupportedPlatform',
    'SystemCreationClassName',
    'SystemName'
)
$Services = Get-CimInstance -ClassName CIM_Service | Select-Object -Property * -ExcludeProperty $ExcludedProperties | Sort-Object -Property Name, ServiceType, CimClass
if ($OutputAsJson) {
    $Services | ConvertTo-Json -Depth 1 | Set-Content -Path "${Prefix}${Tag}.json"
}
$Services | ForEach-Object {
    New-Object PSObject -Property ($WhereWhen + [ordered] @{
            CimClass           = $_.CimClass
            ServiceType        = $_.ServiceType
            StartMode          = $_.StartMode
            Name               = $_.Name

            Caption            = $_.Caption
            CompatID           = $_.CompatID
            CreationClassName  = $_.CreationClassName
            DeviceClass        = $_.DeviceClass
            DeviceID           = $_.DeviceID
            DeviceName         = $_.DeviceName
            DevLoader          = $_.DevLoader
            DriverDate         = $_.DriverDate
            DriverName         = $_.DriverName
            DriverProviderName = $_.DriverProviderName
            DriverVersion      = $_.DriverVersion
            FriendlyName       = $_.FriendlyName
            HardWareID         = $_.HardWareID
            InfName            = $_.InfName
            IsSigned           = $_.IsSigned
            Location           = $_.Location
            Manufacturer       = $_.Manufacturer
            Signer             = $_.Signer
            Started            = $_.Started
            Status             = $_.Status
        })
} | Export-Csv -NoTypeInformation -Path "${Prefix}${Tag}.csv"

##########

$Tag = 'RSoP'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
foreach ($ReportExtension in ('xml', 'html')) {
    $GPResultOption = '/' + $ReportExtension[0]
    & gpresult.exe /scope computer $GPResultOption "${Prefix}${Tag} Computer.${ReportExtension}"
    $LocalUsers | ForEach-Object {
        & gpresult.exe /scope user /user $_.Name $GPResultOption "${Prefix}${Tag} User $($_.Name).${ReportExtension}"
    }
}

##########

$Tag = 'AuditPol'
Write-Progress -Activity $ProgressActivity -CurrentOperation $Tag
& auditpol /backup "/file:${Prefix}${Tag}-Computer.csv"
$LocalUsers | ForEach-Object {
    & auditpol /get "/user:$($_.Name)" /category:* /r > "${Prefix}${Tag} User $($_.Name).csv"
}

##########

Write-Progress -Activity $ProgressActivity -Completed
