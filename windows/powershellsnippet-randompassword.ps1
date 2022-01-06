$CharacterClasses = @{
    P = '!@#$%^&*()_-+=[{]};:<>|./?'
    N = '0123456789'
    L = 'ABCDEGHJKLMNPQRTVWXYZabcdeghijkmnpqrvwxyz'
}
$Pattern = 'P' * 2 + 'N' * 2 + 'L' * 12
$Random = New-Object byte[]($Pattern.Length);
(New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($Random)
$i = 0
$Password = -join ($Pattern.ToCharArray() | ForEach-Object { [string]$_ } | ForEach-Object {
    $CharacterClasses[$_].Chars(($Random[$i++] % $CharacterClasses[$_].Length))
})
# TODO ConvertTo-SecureString -AsPlainText -Force
