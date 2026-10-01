<#
    praticar.ps1 - Toca os audios-modelo para shadowing.

    Descobre os blocos sozinho: cada refs\<nome>.txt com um audio\modelo-<nome>.wav
    correspondente vira um bloco. Nao ha lista fixa.

    .\praticar.ps1                   lista os blocos disponiveis
    .\praticar.ps1 abertura          toca
    .\praticar.ps1 abertura -Vezes 5 toca 5x, com pausa para falar junto
    .\praticar.ps1 abertura -Lento   0.75x - da para acompanhar falando junto
    .\praticar.ps1 abertura -Texto   mostra o texto na tela
    .\praticar.ps1 -Tudo             toca todos em ordem alfabetica

    Nome parcial funciona: ".\praticar.ps1 aber" acha "abertura".
#>
param(
    [Parameter(Position = 0)][string]$Bloco = "",
    [int]$Vezes = 1,
    [switch]$Tudo,
    [switch]$Texto,
    [switch]$Lento,          # 0.75x
    [switch]$MuitoLento,     # 0.6x
    [double]$Velocidade = 0  # ex: -Velocidade 0.85
)
$raiz = $PSScriptRoot

# atempo do ffmpeg muda a velocidade SEM mudar o tom de voz
if ($Velocidade -le 0) {
    if ($MuitoLento) { $Velocidade = 0.6 }
    elseif ($Lento)  { $Velocidade = 0.75 }
    else             { $Velocidade = 1.0 }
}

function Get-Blocos {
    $out = @()
    Get-ChildItem (Join-Path $raiz "refs\*.txt") -EA SilentlyContinue | Sort-Object Name | ForEach-Object {
        $nome = $_.BaseName
        $wav = Join-Path $raiz "audio\modelo-$nome.wav"
        $pal = (Get-Content $_.FullName -Raw -EA SilentlyContinue) -split '\s+' | Where-Object { $_ }
        $out += [pscustomobject]@{
            nome = $nome
            txt  = $_.FullName
            wav  = $wav
            temAudio = Test-Path $wav
            palavras = $pal.Count
        }
    }
    return $out
}

function Toca($b) {
    Write-Output ""
    Write-Output "============================================================"
    Write-Output " $($b.nome)   ($($b.palavras) palavras)"
    if ($Velocidade -ne 1.0) { Write-Output " velocidade: $Velocidade x" }
    Write-Output "============================================================"

    if ($Texto -and (Test-Path $b.txt)) {
        Write-Output ""
        Get-Content $b.txt -Encoding UTF8 | ForEach-Object { Write-Output "  $_" }
        Write-Output ""
    }
    if (-not $b.temAudio) {
        Write-Output "  (sem audio - gere com gerar_modelos.py $($b.nome))"
        return
    }
    for ($i = 1; $i -le $Vezes; $i++) {
        if ($Vezes -gt 1) { Write-Output "  --- passada $i de $Vezes --- FALE JUNTO ---" }
        if ($Velocidade -eq 1.0) {
            & ffplay -nodisp -autoexit -loglevel quiet $b.wav
        } else {
            & ffplay -nodisp -autoexit -loglevel quiet -af "atempo=$Velocidade" $b.wav
        }
        if ($i -lt $Vezes) { Start-Sleep -Seconds 2 }
    }
}

$blocos = Get-Blocos
if (-not $blocos) {
    Write-Output ""
    Write-Output "Nenhum bloco em refs\. Crie um .txt com o texto que voce quer treinar:"
    Write-Output "  refs\abertura.txt"
    Write-Output "Depois gere o audio (veja README.md > Passo 5)."
    exit 0
}

if ($Tudo) { foreach ($b in $blocos) { Toca $b }; exit 0 }

if ([string]::IsNullOrWhiteSpace($Bloco)) {
    Write-Output ""
    Write-Output "BLOCOS DISPONIVEIS"
    Write-Output "-----------------------------------------------------------"
    foreach ($b in $blocos) {
        $m = if ($b.temAudio) { "  " } else { "!!" }
        Write-Output ("$m {0,-32} {1,4} palavras" -f $b.nome, $b.palavras)
    }
    Write-Output ""
    Write-Output "  !! = sem audio gerado"
    Write-Output ""
    Write-Output "  .\praticar.ps1 <bloco> -Lento -Vezes 5    <- shadowing"
    Write-Output "  .\praticar.ps1 <bloco> -Texto             <- com o texto na tela"
    exit 0
}

$achados = @($blocos | Where-Object { $_.nome -eq $Bloco })
if (-not $achados) { $achados = @($blocos | Where-Object { $_.nome -like "*$Bloco*" }) }
if (-not $achados) {
    Write-Output "Bloco '$Bloco' nao encontrado. Rode .\praticar.ps1 sem argumento para ver a lista."
    exit 1
}
if ($achados.Count -gt 1) {
    Write-Output "'$Bloco' casa com mais de um bloco:"
    $achados | ForEach-Object { Write-Output "  $($_.nome)" }
    exit 1
}
Toca $achados[0]
