#!/usr/bin/env python
"""
gerar_modelos.py - Gera os audios-modelo de shadowing com a SUA voz clonada.

Usa XTTS v2 do projeto clone-voice. Roda 100% local, em CPU.

Por que existe (e nao um loop chamando gerar.py):
    carregar o modelo XTTS leva ~58s e gerar uma frase leva ~16s. Chamar
    gerar.py N vezes paga os 58s N vezes. Aqui o modelo carrega UMA vez
    e todos os refs sao gerados em sequencia.

Validado em 2026-08-06: XTTS com referencia em portugues gerou
"The third threat authentication method reduced authorization risk"
com 100% de acuracia nos modelos base E small do whisper. A voz de
referencia contribui TIMBRE, nao fonologia - o ingles sai correto.

Uso (precisa do python do venv do clone-voice):
    CLONE=/caminho/para/clone-voice
    $CLONE/.venv/Scripts/python.exe gerar_modelos.py                 # todos os refs
    $CLONE/.venv/Scripts/python.exe gerar_modelos.py apresentacao-30 # so um
    $CLONE/.venv/Scripts/python.exe gerar_modelos.py --forcar        # regera tudo
"""

import glob
import re
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 4))
os.environ.setdefault("COQUI_TOS_AGREED", "1")

RAIZ = os.path.dirname(os.path.abspath(__file__))


def _config():
    """
    Caminhos configuraveis, em ordem de precedencia:
      1. variaveis de ambiente CLONE_VOICE_DIR / VOZ_DIR
      2. config.json na raiz do projeto
      3. config.example.json
    Sem caminho absoluto no codigo: o repo roda em qualquer maquina.
    """
    import json
    cfg = {}
    for nome in ("config.json", "config.example.json"):
        caminho = os.path.join(RAIZ, nome)
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8-sig") as f:
                cfg = json.load(f)
            break
    cfg["clone_voice_dir"] = os.environ.get("CLONE_VOICE_DIR", cfg.get("clone_voice_dir", ""))
    cfg["voz_dir"] = os.environ.get("VOZ_DIR", cfg.get("voz_dir", ""))
    return cfg


CFG = _config()
CLONE = os.path.expanduser(CFG.get("clone_voice_dir", ""))
_VOZ = os.path.expanduser(CFG.get("voz_dir") or os.path.join("voices", "nsa_clips12"))
VOZ_DIR = _VOZ if os.path.isabs(_VOZ) else os.path.join(CLONE, _VOZ)
VOZ_FALLBACK = os.path.join(CLONE, "voices", "nsa_clips")
MODEL_NAME = CFG.get("modelo_xtts", "tts_models/multilingual/multi-dataset/xtts_v2")

REFS = os.path.join(RAIZ, "refs")
AUDIO = os.path.join(RAIZ, "audio")


def referencias_de_voz():
    for d in (VOZ_DIR, VOZ_FALLBACK):
        wavs = sorted(glob.glob(os.path.join(d, "*.wav")))
        if wavs:
            return wavs, d
    sys.exit(f"ERRO: nenhum .wav de referencia em {VOZ_DIR} nem {VOZ_FALLBACK}")


def ler_ref(caminho):
    with open(caminho, encoding="utf-8-sig") as f:   # utf-8-sig remove BOM
        return " ".join(f.read().split())


def frases(texto):
    """quebra em frases: geracao curta nao descarrila"""
    partes = re.split(r"(?<=[.!?])\s+", texto)
    return [p.strip() for p in partes if p.strip()]


def duracao(wav):
    import subprocess
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", wav],
            check=True, capture_output=True, text=True).stdout.strip()
        return float(out)
    except Exception:
        return None


def concatenar(wavs, destino, pausa_ms=280):
    """junta os wavs com uma pausa curta entre frases (via ffmpeg)"""
    import subprocess, tempfile
    sil = os.path.join(tempfile.gettempdir(), f"_sil{pausa_ms}.wav")
    if not os.path.exists(sil):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "anullsrc=r=24000:cl=mono",
                        "-t", str(pausa_ms / 1000.0), sil],
                       check=True, capture_output=True)
    lista = os.path.join(tempfile.gettempdir(), "_concat.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for i, w in enumerate(wavs):
            f.write(f"file '{w.replace(os.sep, '/')}'\n")
            if i < len(wavs) - 1:
                f.write(f"file '{sil.replace(os.sep, '/')}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", lista, "-ar", "24000", "-ac", "1",
                    destino], check=True, capture_output=True)


TEMPERATURA = 0.3


def main():
    global TEMPERATURA
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    forcar = "--forcar" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--temp="):
            TEMPERATURA = float(a.split("=", 1)[1])
    print(f"temperatura: {TEMPERATURA}")

    if args:
        alvos = []
        for nome in args:
            p = os.path.join(REFS, nome if nome.endswith(".txt") else nome + ".txt")
            if not os.path.exists(p):
                sys.exit(f"ERRO: ref nao encontrado: {p}")
            alvos.append(p)
    else:
        # ignora refs auxiliares (drills, benchmarks) - so respostas de verdade
        alvos = [p for p in sorted(glob.glob(os.path.join(REFS, "*.txt")))
                 if not os.path.basename(p).startswith(("_", "drill-"))]

    if not alvos:
        sys.exit("Nenhum ref para gerar. Coloque .txt em refs/")

    pendentes = []
    for p in alvos:
        tag = os.path.splitext(os.path.basename(p))[0]
        destino = os.path.join(AUDIO, f"modelo-{tag}.wav")
        if os.path.exists(destino) and not forcar:
            print(f"  ja existe, pulando: modelo-{tag}.wav  (use --forcar para regerar)")
            continue
        pendentes.append((tag, p, destino))

    if not pendentes:
        print("\nNada a fazer.")
        return

    vozes, voz_dir = referencias_de_voz()
    print(f"\nVoz de referencia: {os.path.basename(voz_dir)} ({len(vozes)} clipes)")
    print(f"A gerar: {len(pendentes)} modelo(s)\n")

    print("Carregando XTTS v2 (uma vez so, ~60s em CPU)...")
    t0 = time.time()
    from TTS.api import TTS
    tts = TTS(model_name=MODEL_NAME, progress_bar=False).to("cpu")
    print(f"  modelo pronto em {time.time() - t0:.1f}s\n")

    import tempfile
    WPS = 2.2            # ritmo tipico do XTTS (~130 wpm)
    TOLERANCIA = 1.7     # acima disso a frase divagou
    TENTATIVAS = 3

    os.makedirs(AUDIO, exist_ok=True)
    for i, (tag, ref, destino) in enumerate(pendentes, 1):
        texto = ler_ref(ref)
        fs = frases(texto)
        print(f"[{i}/{len(pendentes)}] {tag}  ({len(texto.split())} palavras, {len(fs)} frases)")
        t0 = time.time()
        parciais, falhou = [], False

        for j, frase in enumerate(fs, 1):
            n_pal = len(frase.split())
            esperado = max(n_pal / WPS, 1.0)
            parcial = os.path.join(tempfile.gettempdir(), f"_x_{tag}_{j:02d}.wav")

            for tentativa in range(1, TENTATIVAS + 1):
                try:
                    tts.tts_to_file(
                        text=frase,
                        speaker_wav=vozes,
                        language="en",
                        file_path=parcial,
                        split_sentences=False,   # a frase JA e a unidade
                        gpt_cond_len=30,
                        gpt_cond_chunk_len=6,
                        max_ref_len=30,
                        sound_norm_refs=True,
                        # 0.3 e nao 0.7: com 0.7 o XTTS alucina fala inventada.
                        # Para LER script fixo nao se quer criatividade.
                        temperature=TEMPERATURA,
                        repetition_penalty=5.0,
                    )
                except Exception as e:
                    print(f"        frase {j}: ERRO {type(e).__name__}: {e}")
                    falhou = True
                    break

                d = duracao(parcial)
                if d is None or d <= esperado * TOLERANCIA:
                    break   # aceita
                print(f"        frase {j}: {d:.1f}s para {n_pal} palavras "
                      f"(esperado ~{esperado:.1f}s) - divagou, tentativa {tentativa}/{TENTATIVAS}")
            else:
                print(f"        frase {j}: nao convergiu em {TENTATIVAS} tentativas, aceitando")

            if falhou:
                break
            parciais.append(parcial)

        if falhou or not parciais:
            print(f"        FALHOU: nenhum audio gerado para {tag}")
            continue

        try:
            concatenar(parciais, destino)
            print(f"        {time.time() - t0:.1f}s -> audio/modelo-{tag}.wav")
        except Exception as e:
            print(f"        FALHOU ao concatenar: {type(e).__name__}: {e}")
        finally:
            for p in parciais:
                try:
                    os.remove(p)
                except OSError:
                    pass

    print("\nPronto. Valide os modelos antes de usar para shadowing:")
    for tag, ref, _ in pendentes:
        rel = os.path.relpath(ref, RAIZ).replace("\\", "/")
        print(f"  python pron_check.py audio/modelo-{tag}.wav --ref {rel}")


if __name__ == "__main__":
    main()
