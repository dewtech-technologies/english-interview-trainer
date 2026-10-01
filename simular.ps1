<#
    simular.ps1 - Simulacao de entrevista com perguntas ALEATORIAS, so em audio.

    Voce nao ve a pergunta escrita. Ouve, pensa, responde. Como na entrevista.
    Treina as duas coisas que a Giovanna apontou: conversacao e resposta nao
    prevista. E de quebra, compreensao auditiva.

    Uso:
        .\simular.ps1                    3 perguntas, 90s cada
        .\simular.ps1 -N 5               5 perguntas
        .\simular.ps1 -N 5 -Segundos 60  respostas mais curtas (pressao)
        .\simular.ps1 -Categoria historia   so perguntas de historia/STAR
        .\simular.ps1 -Repetir           repete a pergunta uma vez antes de gravar

    Categorias: historia fundo tecnica ia inesperada logistica
#>
param(
    [int]$N = 3,
    [int]$Segundos = 90,
    [string]$Categoria = "",
    [string]$Modo = "",          # rh | tecnica
    [switch]$Followup,           # pergunta de acompanhamento apos cada resposta
    [switch]$Repetir,
    [string]$Dispositivo = ""
)
$ErrorActionPreference = "Continue"
$raiz = $PSScriptRoot
$banco = Join-Path $raiz "perguntas\banco.txt"
if (-not (Test-Path $banco)) { Write-Output "ERRO: banco nao encontrado: $banco"; exit 1 }

# --- perguntas ---
$todas = Get-Content $banco -Encoding UTF8 | Where-Object { $_ -match '\|' -and $_ -notmatch '^\s*#' } |
    ForEach-Object {
        $p = $_ -split '\|', 2
        [pscustomobject]@{ cat = $p[0].Trim(); q = $p[1].Trim() }
    }
# modos: conjuntos de categorias que imitam cada tipo de entrevista
$MODOS = @{
    "rh"      = @("fundo", "logistica", "historia", "inesperada")
    "tecnica" = @("tecnica", "ia", "historia", "inesperada")
}
if ($Modo) {
    $m = $Modo.ToLower()
    if (-not $MODOS.ContainsKey($m)) {
        Write-Output "Modo '$Modo' nao existe. Use: rh | tecnica"; exit 1
    }
    $cats = $MODOS[$m]
    $todas = $todas | Where-Object { $cats -contains $_.cat }
    if ($m -eq "tecnica" -and -not $PSBoundParameters.ContainsKey('Followup')) { $Followup = $true }
}
if ($Categoria) { $todas = $todas | Where-Object { $_.cat -eq $Categoria.ToLower() } }
if (-not $todas) { Write-Output "Nenhuma pergunta para a categoria '$Categoria'."; exit 1 }
$sorteadas = $todas | Get-Random -Count ([Math]::Min($N, $todas.Count))

# --- microfone ---
if (-not $Dispositivo) {
    $saida = cmd /c "ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2>&1"
    $devs = @(); foreach ($l in $saida) { if ($l -match '"([^"]+)"\s+\(audio\)') { $devs += $Matches[1] } }
    $pref = $devs | Where-Object { $_ -match 'US-1x2HR' } | Select-Object -First 1
    $Dispositivo = if ($pref) { $pref } else { $devs[0] }
}

# --- voz do entrevistador (Zira: diferente da sua voz clonada) ---
Add-Type -AssemblyName System.Speech
$voz = New-Object System.Speech.Synthesis.SpeechSynthesizer
$en = $voz.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "en*" } | Select-Object -First 1
if ($en) { $voz.SelectVoice($en.VoiceInfo.Name) }
$voz.Rate = 0

$FOLLOWUPS = @()
$fpath = Join-Path $raiz "perguntasollowups.txt"
if (Test-Path $fpath) {
    $FOLLOWUPS = Get-Content $fpath -Encoding UTF8 | Where-Object { $_.Trim() -and $_ -notmatch '^\s*#' }
}

$stamp = Get-Date -Format "MMdd-HHmm"
$dirSess = Join-Path $raiz "audio\sim-$stamp"
New-Item -ItemType Directory -Force $dirSess | Out-Null
$notas = Join-Path $dirSess "perguntas.txt"

Write-Output ""
Write-Output "=============================================================="
Write-Output " SIMULACAO - $($sorteadas.Count) perguntas, $Segundos s cada"
Write-Output " microfone: $Dispositivo"
Write-Output "=============================================================="
Write-Output ""
Write-Output " REGRAS"
Write-Output "  - voce NAO ve a pergunta escrita"
Write-Output "  - se nao entender, diga em voz alta: Could you repeat that?"
Write-Output "    (a pergunta sera repetida uma vez)"
Write-Output "  - se travar, use o e6: Let me put it another way"
Write-Output "  - NAO pare para corrigir. Termine sempre."
    if ($Followup) { Write-Output "  - havera um FOLLOW-UP apos cada resposta" }
Write-Output ""
foreach ($n in 5,4,3,2,1) { Write-Output "  comecando em $n..."; Start-Sleep -Seconds 1 }

$i = 0
foreach ($item in $sorteadas) {
    $i++
    $arq = Join-Path $dirSess ("q{0:d2}.wav" -f $i)
    Add-Content -Path $notas -Value ("q{0:d2} [{1}] {2}" -f $i, $item.cat, $item.q) -Encoding UTF8

    Write-Output ""
    Write-Output "--------------------------------------------------------------"
    Write-Output " PERGUNTA $i de $($sorteadas.Count)          [ouca com atencao]"
    Write-Output "--------------------------------------------------------------"
    Start-Sleep -Milliseconds 700
    $voz.Speak($item.q)
    if ($Repetir) { Start-Sleep -Milliseconds 900; $voz.Speak($item.q) }

    Write-Output ""
    Write-Output "  >>> RESPONDA AGORA ($Segundos s) <<<"
    cmd /c "ffmpeg -hide_banner -loglevel error -y -f dshow -i ""audio=$Dispositivo"" -t $Segundos -ac 1 -ar 16000 -c:a pcm_s16le ""$arq"" 2>&1" | Out-Null

    $raw = cmd /c "ffmpeg -hide_banner -i ""$arq"" -af volumedetect -f null - 2>&1"
    $mean = -99.0
    foreach ($l in $raw) { if ($l -match "mean_volume:\s*(-?[\d\.]+)") { $mean = [double]$Matches[1] } }
    if ($mean -lt -45) { Write-Output "  !! audio muito baixo ($mean dB) - chegue mais perto do microfone" }
    else { Write-Output "  gravado (nivel $mean dB)" }

    if ($Followup -and $FOLLOWUPS.Count -gt 0) {
        $fu = $FOLLOWUPS | Get-Random
        $arqF = Join-Path $dirSess ("q{0:d2}-followup.wav" -f $i)
        Add-Content -Path $notas -Value ("q{0:d2}-followup  {1}" -f $i, $fu) -Encoding UTF8
        Start-Sleep -Milliseconds 900
        Write-Output ""
        Write-Output "  --- FOLLOW-UP ---"
        $voz.Speak($fu)
        $segF = [Math]::Max([int]($Segundos / 2), 30)
        Write-Output "  >>> RESPONDA ($segF s) <<<"
        cmd /c "ffmpeg -hide_banner -loglevel error -y -f dshow -i ""audio=$Dispositivo"" -t $segF -ac 1 -ar 16000 -c:a pcm_s16le ""$arqF"" 2>&1" | Out-Null
        Write-Output "  gravado"
    }

    if ($i -lt $sorteadas.Count) { Write-Output "  proxima em 3s..."; Start-Sleep -Seconds 3 }
}
$voz.Dispose()

Write-Output ""
Write-Output "=============================================================="
Write-Output " FIM. Sessao: audio\sim-$stamp"
Write-Output "=============================================================="
Write-Output ""
Write-Output "Perguntas que cairam:"
Get-Content $notas -Encoding UTF8 | ForEach-Object { Write-Output "  $_" }
Write-Output ""
Write-Output "Para analisar tudo:"
Write-Output "  python analisar_simulacao.py audio\sim-$stamp"
