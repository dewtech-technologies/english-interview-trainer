<#
    diagnostico_mic.ps1 - Descobre qual microfone captura sua voz e em que nivel.

    Testa TODOS os dispositivos de captura, um por um, com voce falando.
    No fim diz qual usar no gravar.ps1.

    Uso:  powershell -File diagnostico_mic.ps1
#>
$ErrorActionPreference = "Continue"

function Get-Dispositivos {
    $saida = cmd /c "ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2>&1"
    $devs = @()
    foreach ($l in $saida) { if ($l -match '"([^"]+)"\s+\(audio\)') { $devs += $Matches[1] } }
    return $devs
}

function Measure-Nivel($arquivo) {
    $raw = cmd /c "ffmpeg -hide_banner -i ""$arquivo"" -af volumedetect -f null - 2>&1"
    $mean = -99.0; $max = -99.0
    foreach ($l in $raw) {
        if ($l -match "mean_volume:\s*(-?[\d\.]+)") { $mean = [double]$Matches[1] }
        if ($l -match "max_volume:\s*(-?[\d\.]+)")  { $max  = [double]$Matches[1] }
    }
    return @{ mean = $mean; max = $max }
}

$devs = Get-Dispositivos
$tmp = Join-Path $env:TEMP "_micdiag.wav"

Write-Output ""
Write-Output "=============================================================="
Write-Output " DIAGNOSTICO DE MICROFONE"
Write-Output "=============================================================="
Write-Output ""
Write-Output "ANTES DE COMECAR, confira duas coisas fisicas:"
Write-Output ""
Write-Output "  1. A tecla F4 do seu ThinkPad tem um LED laranja."
Write-Output "     Se estiver ACESO, o microfone esta MUDO por hardware."
Write-Output "     Aperte F4 e confirme que o LED apagou."
Write-Output ""
Write-Output "  2. Se for usar a TASCAM US-1x2HR: microfone plugado no INPUT 1,"
Write-Output "     knob de GAIN acima da metade, e +48V ligado se for condensador."
Write-Output ""
Write-Output "Vou testar $($devs.Count) dispositivo(s), 6 segundos cada."
Write-Output "Em cada um, FALE ALTO E CONTINUO. Sugestao: conte 'one two three"
Write-Output "four five six' em voz normal de entrevista."
Write-Output ""
Write-Output "Comecando em 8 segundos. Prepare-se para falar."
foreach ($n in 8, 7, 6, 5, 4, 3, 2, 1) { Write-Output "  $n"; Start-Sleep -Seconds 1 }

$resultados = @()

foreach ($d in $devs) {
    Write-Output ""
    Write-Output "--------------------------------------------------------------"
    Write-Output " $d"
    Write-Output "--------------------------------------------------------------"
    foreach ($n in 3, 2, 1) { Write-Output "  $n..."; Start-Sleep -Seconds 1 }
    Write-Output "  >>> FALE AGORA (6s) <<<"

    cmd /c "ffmpeg -hide_banner -loglevel error -y -f dshow -i ""audio=$d"" -t 6 -ac 1 -ar 16000 -c:a pcm_s16le ""$tmp"" 2>&1" | Out-Null

    if (-not (Test-Path $tmp)) {
        Write-Output "  FALHOU: nao gerou arquivo (dispositivo em uso por outro app?)"
        $resultados += @{ dev = $d; mean = -99; max = -99; nota = "FALHOU" }
        continue
    }

    $n = Measure-Nivel $tmp
    Write-Output ("  mean: {0} dB   max: {1} dB" -f $n.mean, $n.max)

    $nota = ""
    if ($n.max -le -70) {
        $nota = "SILENCIO TOTAL - mudo por hardware/driver"
    } elseif ($n.max -le -35) {
        $nota = "MUITO BAIXO - so ruido ambiente, sua voz nao entrou"
    } elseif ($n.mean -lt -45) {
        $nota = "BAIXO - voz longe ou ganho baixo"
    } elseif ($n.mean -gt -12) {
        $nota = "ALTO - risco de distorcao"
    } else {
        $nota = "BOM - use este"
    }
    Write-Output "  -> $nota"
    $resultados += @{ dev = $d; mean = $n.mean; max = $n.max; nota = $nota }
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}

Write-Output ""
Write-Output "=============================================================="
Write-Output " RESUMO"
Write-Output "=============================================================="
foreach ($r in $resultados) {
    Write-Output ("  {0,-52} mean {1,7} dB  -> {2}" -f $r.dev, $r.mean, $r.nota)
}

$bom = $resultados | Where-Object { $_.nota -eq "BOM - use este" } | Select-Object -First 1
Write-Output ""
if ($bom) {
    Write-Output "USE ESTE:"
    Write-Output ("  powershell -File gravar.ps1 -Tag dia01-baseline -Segundos 400 -Dispositivo ""{0}""" -f $bom.dev)
} else {
    $melhor = $resultados | Sort-Object { -$_.mean } | Select-Object -First 1
    Write-Output "NENHUM dispositivo capturou sua voz em nivel utilizavel."
    Write-Output ("Melhor tentativa: {0} (mean {1} dB)" -f $melhor.dev, $melhor.mean)
    Write-Output ""
    Write-Output "Se TODOS deram silencio total, a causa e global:"
    Write-Output "  - tecla F4 (LED laranja) ainda mudo"
    Write-Output "  - Lenovo Vantage tem um mudo de microfone proprio, separado do Windows"
    Write-Output "  - Som > Gravacao > propriedades do dispositivo > aba Niveis > mudo ou 0%"
    Write-Output ""
    Write-Output "Cole ESTE resumo inteiro no chat."
}
Write-Output ""
