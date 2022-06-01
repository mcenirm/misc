#Requires -Version 7.0

[cmdletbinding(DefaultParameterSetName = 'Path')]
param(
    [Parameter(
        ParameterSetName = 'Path',
        Mandatory = $true,
        Position = 0,
        ValueFromPipeline = $true,
        ValueFromPipelineByPropertyName = $true
    )]
    [ValidateNotNullOrEmpty()]
    [SupportsWildcards()]
    [string[]]
    $Path,

    [Parameter(
        ParameterSetName = 'LiteralPath',
        Mandatory = $true,
        ValueFromPipelineByPropertyName = $true
    )]
    [Alias('PSPath')]
    [ValidateNotNullOrEmpty()]
    [string[]]
    $LiteralPath
)

# Set-StrictMode -Version Latest
# $ErrorActionPreference = "Stop"

begin {
    # Add-Type -AssemblyName Microsoft.Office.Interop.Excel
    $e = New-Object -ComObject Excel.Application
}

process {
    $Resolved = switch ($PSCmdlet.ParameterSetName) {
        'Path' { Resolve-Path -Path $Path }
        'LiteralPath' { Resolve-Path -LiteralPath $LiteralPath }
    }
    foreach ($p in $Resolved) {
        # https://excel.officetuts.net/examples/convert-excel-file-xlsx-to-csv-in-powershell
        $b = $e.Workbooks.Open($p.ProviderPath)
        $b.SaveAs($p.ProviderPath + ".xlsx", 51) # [Microsoft.Office.Interop.Excel.XlFileFormat]::xlWorkbookDefault
        $b.Close()
    }

}

end {
    $e.Quit()
}
