function dl { & curl.exe -LROJ @args }
function dlo { & curl.exe -LR -o @args }
function delldl { & dl --header 'user-agent: Chrome/1337' @args }
function 7z { & "$env:ProgramFiles\7-Zip\7z.exe" @args }
function wgup { & winget upgrade @args }
function wgdl { & winget download --exact --architecture x64 --id $args[0] }
