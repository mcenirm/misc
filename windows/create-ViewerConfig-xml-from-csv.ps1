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
    <ResultsConfig>
        <Columns>
            <Column Name="Level" Type="System.String" Path="Event/System/Level" Visible="">136</Column>
            <Column Name="Date and Time" Type="System.DateTime" Path="Event/System/TimeCreated/@SystemTime" Visible="">186</Column>
            <Column Name="Event ID" Type="System.UInt32" Path="Event/System/EventID" Visible="">96</Column>
            <Column Name="Keywords" Type="System.String" Path="Event/System/Keywords" Visible="">70</Column>
            <Column Name="Task Category" Type="System.String" Path="Event/System/Task" Visible="">100</Column>
            <Column Name="User" Type="System.String" Path="Event/System/Security/@UserID" Visible="">50</Column>
            <Column Name="Source" Type="System.String" Path="Event/System/Provider/@Name" Visible="">96</Column>
            <Column Name="Operational Code" Type="System.String" Path="Event/System/Opcode" Visible="">110</Column>
            <Column Name="Log" Type="System.String" Path="Event/System/Channel" Visible="">80</Column>
            <Column Name="Computer" Type="System.String" Path="Event/System/Computer" Visible="">170</Column>
            <Column Name="Process ID" Type="System.UInt32" Path="Event/System/Execution/@ProcessID" Visible="">70</Column>
            <Column Name="Thread ID" Type="System.UInt32" Path="Event/System/Execution/@ThreadID" Visible="">70</Column>
            <Column Name="Processor ID" Type="System.UInt32" Path="Event/System/Execution/@ProcessorID" Visible="">90</Column>
            <Column Name="Session ID" Type="System.UInt32" Path="Event/System/Execution/@SessionID" Visible="">70</Column>
            <Column Name="Kernel Time" Type="System.UInt32" Path="Event/System/Execution/@KernelTime" Visible="">80</Column>
            <Column Name="User Time" Type="System.UInt32" Path="Event/System/Execution/@UserTime" Visible="">70</Column>
            <Column Name="Processor Time" Type="System.UInt32" Path="Event/System/Execution/@ProcessorTime" Visible="">100</Column>
            <Column Name="Correlation Id" Type="System.Guid" Path="Event/System/Correlation/@ActivityID" Visible="">85</Column>
            <Column Name="Relative Correlation Id" Type="System.Guid" Path="Event/System/Correlation/@RelatedActivityID" Visible="">140</Column>
            <Column Name="Event Source Name" Type="System.String" Path="Event/System/Provider/@EventSourceName" Visible="">140</Column>
        </Columns>
    </ResultsConfig>
</ViewerConfig>
'@
Set-Variable -Option Constant -Name SelectExpressionFormat -Value '*[System[({0})]]'
Set-Variable -Option Constant -Name SelectConjunction -Value ' and '
Set-Variable -Option Constant -Name SelectDisjunction -Value ' or '
Set-Variable -Option Constant -Name SelectSingleTermFormat -Value 'EventID={0}'
Set-Variable -Option Constant -Name SelectRangeTermFormat -Value ('(EventID >= {0}', 'EventID <= {1})' -join $SelectConjunction)

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

    # collapse consecutive numbers into ranges
    $IdPairs = [System.Collections.ArrayList]::new()
    foreach ($Id in $SortedEventIDList) {
        if ($IdPairs.Count -eq 0 -or $IdPairs[-1][-1] -ne ($Id - 1) ) {
            [void]$IdPairs.Add(@($Id, $Id))
        }
        else {
            $IdPairs[-1][-1] = $Id
        }
    }

    # form query terms
    $SimpleEventIdList = [string[]]::new($IdPairs.Count)
    $SelectTermList = [string[]]::new($IdPairs.Count)
    for ($i = 0; $i -lt $IdPairs.Count; $i++) {
        [string]$Left = $IdPairs[$i][0]
        [string]$Right = $IdPairs[$i][-1]
        if ($Left -eq $Right) {
            $SimpleEventIdList[$i] = $Left
            $SelectTermList[$i] = $SelectSingleTermFormat -f $Left
        }
        else {
            $SimpleEventIdList[$i] = $Left, $Right -join '-'
            $SelectTermList[$i] = $SelectRangeTermFormat -f $Left, $Right
        }
    }
    $SelectTermText = $SelectTermList -join $SelectDisjunction
    $SelectText = $SelectExpressionFormat -f $SelectTermText

    [xml]$x = $ViewerConfigTemplate

    $Simple = $x.ViewerConfig.QueryConfig.QueryParams.Simple
    $Simple.Channel = $ChannelPath
    $Simple.EventId = $SimpleEventIDList -join ','

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
    | ForEach-Object -MemberName ToLower `
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
    $CleanedName = $ViewName -replace $InvalidFileNameCharsRegex, ' '

    $OutXMLName = $CleanedName + ".xml"
    $OutXMLFile = Join-Path -Path $OutFolder -ChildPath $OutXMLName

    $EventIdList = $CategoryGroups[$CategoryName]

    $NEVCXArgs = @{
        Name        = $CleanedName
        EventIdList = $EventIdList
    }
    $Log = $Logs[$CategoryName]
    if ($null -ne $Log) {
        $NEVCXArgs['ChannelPath'] = $Log
    }
    $ViewerConfigXml = New-EventViewerConfigXml @NEVCXArgs
    $ViewerConfigXml.Save($OutXMLFile)
}
