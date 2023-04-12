# TODO cleanup and turn into a function, maybe?

# In the current directory, find files that have modification
# times (".LastWriteTime") in the future, and then reset them
# to the most recent but still "in the past" modification
# time from the other files in the directory.

Get-ChildItem -Recurse -File | ForEach-Object -Begin {
    $now = Get-Date
    $maxpast = $false
    [System.Collections.ArrayList]$tofix = @()
} -End {
    $tofix | ForEach-Object -Process {
        $oldt = $_.LastWriteTime
        $_.LastWriteTime = $maxpast
        Write-Output $_, $oldt
    }
} -Process {
    $t = $_.LastWriteTime
    if ($now -gt $t) {
        if ( (-not $maxpast) -or ($t -gt $maxpast) ) {
            $maxpast = $t
        }
    }
    else {
        $tofix.Add($_)
    }
}
