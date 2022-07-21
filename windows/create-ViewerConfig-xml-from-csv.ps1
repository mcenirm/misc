#Requires -Version 5

<#
.SYNOPSIS
    Convert event view table to Event Viewer custom view files
#>

param (
    [Parameter(
        Mandatory = $true,
        Position = 0,
        ParameterSetName = "LiteralPath",
        ValueFromPipelineByPropertyName = $true,
        HelpMessage = "Literal path to one or more CSV files.")]
    [Alias("PSPath")]
    [ValidateNotNullOrEmpty()]
    [string[]]
    $LiteralPath,

    [Parameter(
        Mandatory = $true,
        ParameterSetName = "LiteralPath",
        HelpMessage = "Literal path to output folder.")]
    [ValidateNotNullOrEmpty()]
    [string]
    $OutFolder,

    [Parameter(
        ParameterSetName = "LiteralPath",
        HelpMessage = "Optional prefix for custom view names.")]
    [string]
    $ViewPrefix = $null,

    [string]
    $CategoryHeading = 'Audit Event Category',

    [string]
    $LogHeading = 'Log',

    [string]
    $EventIdHeading = 'Current Windows Event ID'
)


Set-Variable -Option Constant -Name InvalidFileNameCharsRegex `
    -Value ('[{0}]' -f [RegEx]::Escape(([IO.Path]::GetInvalidFileNameChars() -join '')))


# XML template strings
Set-Variable -Option Constant -Name ViewerConfigTemplate -Value @'
<ViewerConfig>
    <QueryConfig>
        <QueryParams>
            <Simple>
                <Channel>PLACEHOLDER</Channel>
                <EventId>PLACEHOLDER</EventId>
                <RelativeTimeInfo>0</RelativeTimeInfo>
                <BySource>False</BySource>
            </Simple>
        </QueryParams>
        <QueryNode>
            <Name>PLACEHOLDER</Name>
            <QueryList>
                <Query Id="0" Path="PLACEHOLDER">
                    <Select Path="PLACEHOLDER">PLACEHOLDER</Select>
                </Query>
            </QueryList>
        </QueryNode>
    </QueryConfig>
</ViewerConfig>
'@
Set-Variable -Option Constant -Name SelectExpressionFormat -Value '*[System[({0})]]'
Set-Variable -Option Constant -Name SelectConjunction -Value ' or '
Set-Variable -Option Constant -Name SelectTermFormat -Value 'EventID={0}'


function New-EventViewerConfigXml {
    [CmdletBinding()]
    [OutputType([xml])]
    param (
        [string]
        $Name,

        [int[]]
        $EventIdList,

        [string]
        $ChannelPath = 'Security'
    )

    $IntegerEventIDList = $EventIDList | ForEach-Object { [int]$_ }
    $SortedEventIDList = $IntegerEventIDList | Sort-Object -Unique

    $SelectTermList = $SortedEventIDList | ForEach-Object { $SelectTermFormat -f $_ }
    $SelectTermText = $SelectTermList -join $SelectConjunction
    $SelectText = $SelectExpressionFormat -f $SelectTermText

    [xml]$x = $ViewerConfigTemplate

    $Simple = $x.ViewerConfig.QueryConfig.QueryParams.Simple
    $Simple.Channel = $ChannelPath
    $Simple.EventId = $SortedEventIDList -join ','

    $QueryNode = $x.ViewerConfig.QueryConfig.QueryNode
    $QueryNode.Name = $Name

    $Query0 = $QueryNode.QueryList.Query
    $Query0.Path = $ChannelPath

    $Select = $Query0.Select
    $Select.Path = $ChannelPath
    $Select.InnerText = $SelectText

    return $x
}


if (-not (Test-Path -PathType Container -LiteralPath $OutFolder)) {
    New-Item -ItemType Directory -Path $OutFolder -Verbose | Out-Null
}
$OutFolder = Resolve-Path -LiteralPath $OutFolder

$Data = Import-Csv -LiteralPath $LiteralPath

$Logs = @{}
$CategoryGroups = @{}
foreach ($EventRecord in $Data) {
    $EventId = $EventRecord.$EventIdHeading -as [int]
    if (-not $EventId) { continue }

    $CategoryNames = $EventRecord.$CategoryHeading -split "`r`n" `
    | ForEach-Object { $_.ToLower() -replace ',', '' } `
    | Where-Object { $_ } `
    | Get-Unique -AsString

    foreach ($CategoryName in $CategoryNames) {
        if (-not $CategoryGroups.ContainsKey($CategoryName)) {
            $CategoryGroups[$CategoryName] = [System.Collections.Generic.List[string]]::new()
        }
        $CategoryGroups[$CategoryName].Add($EventId)
        $Logs[$CategoryName] = $EventRecord.$LogHeading
    }
}

foreach ($CategoryName in $CategoryGroups.Keys) {
    $ViewName = $CategoryName
    if ($ViewPrefix -ne $null) {
        $ViewName = $ViewPrefix + ' ' + $CategoryName
    }
    $CleanedName = $ViewName -replace $InvalidFileNameCharsRegex, '_'

    $OutXMLName = $CleanedName + ".xml"
    $OutXMLFile = Join-Path -Path $OutFolder -ChildPath $OutXMLName

    $EventIdList = $CategoryGroups[$CategoryName]

    $NEVCXArgs = @{
        Name        = $CleanedName
        EventIdList = $EventIdList
    }
    $Log = $Logs[$CategoryName]
    if ($Log -ne $null) {
        $NEVCXArgs['ChannelPath'] = $Log
    }
    $ViewerConfigXml = New-EventViewerConfigXml @NEVCXArgs
    $ViewerConfigXml.Save($OutXMLFile)
}
