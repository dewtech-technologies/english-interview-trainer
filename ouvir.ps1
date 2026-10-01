<#
    ouvir.ps1 - Oraculo de pronuncia. Fala qualquer texto em ingles nativo.

    Usa a voz Microsoft Zira Desktop (en-US), instalada, offline, gratuita.
    Validada em 2026-08-05: gerou "The third threat authentication method
    reduced authorization risk" e o pron_check.py transcreveu com 100% de
    acuracia. Ou seja: e um modelo confiavel para imitar.

    Uso:
        .\ouvir.ps1 "the third threat"
        .\ouvir.ps1 "authorization" -Lento
        .\ouvir.ps1 "the third threat authentication method" -Palavra
        .\ouvir.ps1 "This method reduced token consumption" -Salvar shadow-01
        .\ouvir.ps1 -Drill th

    Parametros:
        -Lento     fala devagar (bom para aprender o fonema)
        -Palavra   fala palavra por palavra, cada uma 2x, com pausa
        -Repetir N repete o texto inteiro N vezes
        -Salvar    salva em audio/modelo-<tag>.wav para shadowing
        -Drill     drills prontos: th, ed, tion, stress
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Texto = "",
    [string]$Arquivo = "",
    [switch]$Lento,
    [switch]$Palavra,
    [int]$Repetir = 1,
    [string]$Salvar = "",
    [string]$Drill = ""
)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$VOZ = "Microsoft Zira Desktop"

$DRILLS = @{
    "th"     = @(
        "thin", "think", "thing", "third", "three", "threat", "thread", "through",
        "method", "author", "authorize", "authentication", "authorization",
        "the third threat", "threat modeling", "multi-factor authentication",
        "broken object level authorization"
    )
    "ed"     = @(
        "reduced", "implemented", "identified", "scanned", "fixed", "mapped",
        "reviewed", "prioritized", "validated", "remediated",
        "This method reduced token consumption by seventy-five percent"
    )
    "er"     = @(
        "bird", "word", "her", "first", "work", "world",
        "third", "thirty", "thirteen",
        "author", "authored", "server", "layer", "secure",
        "her third word", "the author of the third report"
    )
    "tion"   = @(
        "authentication", "authorization", "implementation", "validation",
        "configuration", "remediation", "integration", "application"
    )
    "stress" = @(
        "deVELopment", "vulneraBILity", "authoriZAtion", "impleMENtation",
        "SEcurity", "arCHItecture", "conFIguration", "priORitize"
    )
    "pares"  = @(
        "think sink", "thin fin", "three free", "thread tread",
        "math mat", "author otter"
    )
}

Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer

$temVoz = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -eq $VOZ }
if (-not $temVoz) {
    Write-Output "ERRO: voz '$VOZ' nao encontrada."
    Write-Output "Vozes em ingles disponiveis:"
    $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "en*" } |
        ForEach-Object { Write-Output ("  " + $_.VoiceInfo.Name) }
    $s.Dispose(); exit 1
}
$s.SelectVoice($VOZ)

# Rate: 0 = normal (~140 wpm), -3 = bem devagar para aprender o fonema
if ($Lento) { $s.Rate = -3 } else { $s.Rate = 0 }

# ---------- modo drill ----------
if (-not [string]::IsNullOrWhiteSpace($Drill)) {
    $k = $Drill.ToLower()
    if (-not $DRILLS.ContainsKey($k)) {
        Write-Output "Drill '$Drill' nao existe. Disponiveis: $($DRILLS.Keys -join ', ')"
        $s.Dispose(); exit 1
    }
    Write-Output ""
    Write-Output "DRILL: $k   (repita em voz alta DEPOIS de cada item)"
    if ($k -eq "th") {
        Write-Output "Mao na garganta: NAO deve vibrar. Lingua entre os dentes, sopro sem voz."
    }
    if ($k -eq "er") {
        Write-Output "NAO e o R brasileiro e NAO e vogal+R. E um som unico:"
        Write-Output "lingua no meio da boca, sem tocar nada, labios relaxados."
        Write-Output "Segure longo antes de soltar a consoante: 'errrrr' -> 'bird'."
    }
    Write-Output ""
    $s.Rate = -2
    foreach ($item in $DRILLS[$k]) {
        Write-Output "  $item"
        $s.Speak($item)
        Start-Sleep -Milliseconds 1400   # espaco para voce repetir
        $s.Speak($item)
        Start-Sleep -Milliseconds 1600
    }
    Write-Output ""
    Write-Output "Agora grave voce falando os mesmos itens:"
    Write-Output "  powershell -File gravar.ps1 -Tag drill-$k -Segundos 90"
    $s.Dispose(); exit 0
}

# texto vindo de arquivo: resposta longa nao cabe em linha de comando
if (-not [string]::IsNullOrWhiteSpace($Arquivo)) {
    if (-not (Test-Path $Arquivo)) {
        Write-Output "ERRO: arquivo nao encontrado: $Arquivo"; $s.Dispose(); exit 1
    }
    # remove BOM (Set-Content -Encoding utf8 do PS 5.1 grava com BOM)
    # Trim com array de char: remove BOM + espacos. (.Replace([char],'') falha
    # no PS 5.1 - ele escolhe a sobrecarga de char e '' nao e um char valido.)
    $lixo = @([char]0xFEFF, ' ', "`t", "`r", "`n")
    $Texto = (Get-Content $Arquivo -Raw -Encoding UTF8).Trim($lixo)
    # NAO preenche $Salvar aqui: -Arquivo deve TOCAR por padrao.
    # Salvar so acontece se o usuario passar -Salvar explicitamente.
}

if ([string]::IsNullOrWhiteSpace($Texto)) {
    Write-Output "Uso: .\ouvir.ps1 ""texto em ingles"" [-Lento] [-Palavra] [-Salvar tag]"
    Write-Output "     .\ouvir.ps1 -Arquivo refs\sast-dast-sca.txt"
    Write-Output "     .\ouvir.ps1 -Drill th|er|ed|tion|stress|pares"
    $s.Dispose(); exit 1
}

# ---------- salvar para shadowing ----------
if (-not [string]::IsNullOrWhiteSpace($Salvar)) {
    $audioDir = Join-Path $raiz "audio"
    if (-not (Test-Path $audioDir)) { New-Item -ItemType Directory -Force $audioDir | Out-Null }
    $refDir = Join-Path $raiz "refs"
    if (-not (Test-Path $refDir)) { New-Item -ItemType Directory -Force $refDir | Out-Null }

    $wav = Join-Path $audioDir "modelo-$Salvar.wav"
    $txt = Join-Path $refDir "$Salvar.txt"
    $s.SetOutputToWaveFile($wav)
    $s.Speak($Texto)
    $s.SetOutputToDefaultAudioDevice()
    Set-Content -Path $txt -Value $Texto -Encoding utf8

    # toca em voz alta tambem: o script chama "ouvir", entao sempre soa
    Write-Output "tocando..."
    $s.Speak($Texto)

    Write-Output "modelo : audio/modelo-$Salvar.wav"
    Write-Output "ref    : refs/$Salvar.txt"
    Write-Output ""
    Write-Output "Shadowing: ouca o modelo, fale junto, depois grave voce:"
    Write-Output "  powershell -File gravar.ps1 -Tag $Salvar -Segundos 60 -Ref refs\$Salvar.txt -Analisar"
    Write-Output ""
    Write-Output "Compare seu numero com o do modelo (o modelo tira ~100%):"
    Write-Output "  python pron_check.py audio/modelo-$Salvar.wav --ref refs/$Salvar.txt"
    $s.Dispose(); exit 0
}

# ---------- palavra por palavra ----------
if ($Palavra) {
    Write-Output ""
    Write-Output "Palavra por palavra. Repita DEPOIS de cada uma."
    Write-Output ""
    $s.Rate = -3
    foreach ($p in ($Texto -split '\s+' | Where-Object { $_ })) {
        Write-Output "  $p"
        $s.Speak($p)
        Start-Sleep -Milliseconds 1200
        $s.Speak($p)
        Start-Sleep -Milliseconds 1400
    }
    Write-Output ""
    Write-Output "Agora a frase inteira, em velocidade normal:"
    $s.Rate = 0
    Start-Sleep -Milliseconds 500
    $s.Speak($Texto)
    $s.Dispose(); exit 0
}

# ---------- fala simples ----------
for ($i = 1; $i -le $Repetir; $i++) {
    if ($Repetir -gt 1) { Write-Output "  ($i/$Repetir) $Texto" } else { Write-Output "  $Texto" }
    $s.Speak($Texto)
    if ($i -lt $Repetir) { Start-Sleep -Milliseconds 900 }
}
$s.Dispose()
