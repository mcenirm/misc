#Requires -Version 7.0

[CmdletBinding()]
param (
    [Parameter()]
    [String]
    $Path
)

# Set-StrictMode -Version Latest
# $ErrorActionPreference = "Stop"


begin {
    # Add-Type -AssemblyName Microsoft.Office.Interop.Excel
    $e = New-Object -ComObject Excel.Application
}

process {
    # https://excel.officetuts.net/examples/convert-excel-file-xlsx-to-csv-in-powershell
    $b = $e.Workbooks.Open($Path)
    foreach ($s in $b.Worksheets) {
        $n = $Path + "." + $s.Name + ".csv"
        $s.SaveAs($n, 6) # [Microsoft.Office.Interop.Excel.XlFileFormat]::xlCSV
        Write-Information $n
    }
    $b.Close()
}

end {
    $e.Quit()
}
