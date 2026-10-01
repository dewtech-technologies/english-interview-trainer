<#
    gravar.ps1 - Gravador de treino com checagem de nivel.

    Nao depende do microfone do app Claude. Grava direto pelo ffmpeg.

    Uso:
        .\gravar.ps1 -Tag dia01-tellme -Segundos 100
        .\gravar.ps1 -Tag dia01-baseline -Segundos 400 -Ref refs\tell_me.txt
        .\gravar.ps1 -Listar

    Depois de gravar ele ja imprime (e opcionalmente roda) o pron_check.py.
#>
[CmdletBinding()]
param(
    [string]$Tag = "treino",
    [int]$Segundos = 100,
    [string]$Dispositivo = "",
    [string]$Ref = "",
    [switch]$Listar,
    [switch]$Analisar
)

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$audioDir = Join-Path $raiz "audio"
if (-not (Test-Path $audioDir)) { New-Item -ItemType Directory -Force $audioDir | Out-Null }

function Get-Dispositivos {
    # via cmd /c: o ffmpeg escreve em stderr e o PS 5.1 embrulharia isso em
    # NativeCommandError, o que com ErrorActionPreference=Stop mata o script.
    $saida = cmd /c "ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2>&1"
    $devs = @()
    foreach ($l in $saida) {
        if ($l -match '"([^"]+)"\s+\(audio\)') { $devs += $Matches[1] }
    }
    return $devs
}

$devs = Get-Dispositivos

if ($Listar) {
    Write-Output "Dispositivos de captura disponiveis:"
    for ($i = 0; $i -lt $devs.Count; $i++) { Write-Output ("  [{0}] {1}" -f $i, $devs[$i]) }
    exit 0
}

if ($devs.Count -eq 0) { Write-Output "ERRO: nenhum dispositivo de captura encontrado."; exit 1 }

if ([string]::IsNullOrWhiteSpace($Dispositivo)) {
    # prefere o array interno da Intel: nao depende de cabo/ganho da interface
    $pref = $devs | Where-Object { $_ -match 'Intel|Grupo de microfones|Array' } | Select-Object -First 1
    if ($pref) { $Dispositivo = $pref } else { $Dispositivo = $devs[0] }
}

$stamp = Get-Date -Format "MMdd-HHmm"
$saidaWav = Join-Path $audioDir "$Tag-$stamp.wav"

Write-Output ""
Write-Output "Dispositivo : $Dispositivo"
Write-Output "Duracao     : $Segundos s"
Write-Output "Arquivo     : $(Split-Path $saidaWav -Leaf)"
Write-Output ""
Write-Output "Fale a resposta INTEIRA. Se travar, continue e termine."
Write-Output "Nao pare para corrigir. Ctrl+C encerra antes do tempo."
Write-Output ""
foreach ($n in 3, 2, 1) { Write-Output "  $n..."; Start-Sleep -Seconds 1 }
Write-Output "  >>> FALANDO AGORA <<<"
Write-Output ""

# 16kHz mono ja no formato que o whisper quer
cmd /c "ffmpeg -hide_banner -loglevel error -y -f dshow -i ""audio=$Dispositivo"" -t $Segundos -ac 1 -ar 16000 -c:a pcm_s16le ""$saidaWav"" 2>&1" | Out-Null

if (-not (Test-Path $saidaWav)) { Write-Output "ERRO: gravacao falhou."; exit 1 }

Write-Output "Gravado. Checando nivel de audio..."
$volRaw = cmd /c "ffmpeg -hide_banner -i ""$saidaWav"" -af volumedetect -f null - 2>&1"
$vol = $volRaw | Select-String -Pattern "mean_volume|max_volume"
foreach ($v in $vol) { Write-Output ("  " + $v.ToString().Trim()) }

$media = -99.0
foreach ($l in $volRaw) {
    if ($l -match "mean_volume:\s*(-?[\d\.]+)") { $media = [double]$Matches[1] }
}

Write-Output ""
if ($media -lt -45) {
    Write-Output "!!! AUDIO MUITO BAIXO ($media dB). O transcritor vai alucinar."
    Write-Output "    Chegue mais perto do microfone ou suba o ganho, e regrave."
    Write-Output "    NAO use esta gravacao para medir nada."
} elseif ($media -gt -12) {
    Write-Output "!!! AUDIO MUITO ALTO ($media dB) - risco de clipping/distorcao."
    Write-Output "    Afaste-se um pouco e regrave."
} else {
    Write-Output "Nivel OK ($media dB). Gravacao utilizavel."
}

Write-Output ""
$rel = "audio/" + (Split-Path $saidaWav -Leaf)
if ([string]::IsNullOrWhiteSpace($Ref)) {
    $cmd = "python pron_check.py $rel --tag $Tag"
} else {
    $cmd = "python pron_check.py $rel --ref $Ref --tag $Tag"
}
Write-Output "Proximo passo:"
Write-Output "  $cmd"

if ($Analisar -and $media -ge -45) {
    Write-Output ""
    Write-Output "Rodando analise..."
    Invoke-Expression $cmd
}
