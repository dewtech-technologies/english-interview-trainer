<#
    setup.ps1 - Prepara uma maquina nova para rodar o treino.

    Uso:  powershell -ExecutionPolicy Bypass -File setup.ps1
#>
$ErrorActionPreference = "Continue"
$raiz = $PSScriptRoot
$falhas = @()

function Verifica($nome, $teste, $comoInstalar) {
    Write-Output ""
    Write-Output "[*] $nome"
    $ok = & $teste
    if ($ok) { Write-Output "    OK" }
    else {
        Write-Output "    FALTANDO"
        Write-Output "    -> $comoInstalar"
        $script:falhas += $nome
    }
}

Write-Output "=============================================="
Write-Output " SETUP - treino de ingles para entrevista"
Write-Output "=============================================="

Verifica "Python 3.10+" {
    try { $v = (python -c "import sys;print(sys.version_info[:2]>=(3,10))" 2>$null); $v -eq "True" }
    catch { $false }
} "instale Python 3.11: winget install Python.Python.3.11"

Verifica "ffmpeg + ffprobe" {
    (Get-Command ffmpeg -EA SilentlyContinue) -and (Get-Command ffprobe -EA SilentlyContinue)
} "winget install Gyan.FFmpeg   (depois reabra o terminal)"

Verifica "openai-whisper + torch" {
    try { (python -c "import whisper,torch;print('ok')" 2>$null) -eq "ok" } catch { $false }
} "pip install -r requirements.txt   (torch ~200MB, demora)"

Verifica "voz TTS em ingles (Microsoft Zira)" {
    Add-Type -AssemblyName System.Speech
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $tem = @($s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "en*" }).Count -gt 0
    $s.Dispose(); $tem
} "Configuracoes > Hora e idioma > Idioma > adicionar Ingles (EUA) com Fala"

Verifica "microfone" {
    $saida = cmd /c "ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2>&1"
    ($saida | Where-Object { $_ -match '\(audio\)' }).Count -gt 0
} "conecte um microfone; depois rode: powershell -File diagnostico_mic.ps1"

Verifica "config.json" {
    Test-Path (Join-Path $raiz "config.json")
} "copie config.example.json para config.json e ajuste os caminhos"

Write-Output ""
Write-Output "=============================================="
if ($falhas.Count -eq 0) {
    Write-Output " TUDO PRONTO"
    Write-Output ""
    Write-Output " Comece por:"
    Write-Output "   powershell -File diagnostico_mic.ps1"
    Write-Output "   powershell -File ouvir.ps1 -Arquivo refs\apresentacao-30.txt"
} else {
    Write-Output " PENDENTE: $($falhas -join ', ')"
    Write-Output " Resolva os itens acima e rode de novo."
}
Write-Output "=============================================="
Write-Output ""
Write-Output "Opcional (voz clonada, muito melhor para shadowing):"
Write-Output "  precisa do projeto clone-voice com coqui-tts. Veja README.md"
