# Text-to-speech in PowerShell

Example from [How to set up text-to-speech using PowerShell](https://www.pdq.com/blog/powershell-text-to-speech-examples/)

```powershell
Add-Type -AssemblyName System.speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$tts.Rate = -5  # -10 to 10; -10 is slowest, 10 is fastest
$speak.Speak('Hello...')
```
