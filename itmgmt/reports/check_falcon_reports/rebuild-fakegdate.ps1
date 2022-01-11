dotnet publish -r win-x64 ; Copy-Item .\bin\Debug\net6.0\win-x64\publish\fakegdate.exe .\gdate.exe ; .\gdate -d yesterday +%d/%b/%Y
