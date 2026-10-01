#!/usr/bin/env python
"""
amostrar_vozes.py - Gera amostras dos speakers embutidos do XTTS para voce
ESCOLHER DE OUVIDO quais usar no simulador.

Eu nao consigo ouvir audio. Voce escolhe, eu conecto no simular.ps1.

    <clone-voice>\.venv\Scripts\python.exe amostrar_vozes.py
    <clone-voice>\.venv\Scripts\python.exe amostrar_vozes.py --todos   # os 58

Saida: audio/vozes/<nome>.wav
"""
import os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 4))
os.environ.setdefault("COQUI_TOS_AGREED", "1")

RAIZ = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(RAIZ, "audio", "vozes")
MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

# frase de entrevista real: voce julga no contexto de uso
FRASE = ("So, walk me through how you would evaluate the security of an agent "
         "that has access to a terminal. What would you check first?")

# selecao inicial: mistura de genero e origem aparente
CURTA = ["Kumar Dahl", "Royston Min", "Henriette Usha", "Chandra MacFarland",
         "Suad Qasim", "Badr Odhiambo", "Rosemary Okafor", "Ige Behringer",
         "Craig Gutsy", "Damien Black", "Tammie Ema", "Sofia Hellen"]


def main():
    todos = "--todos" in sys.argv
    os.makedirs(SAIDA, exist_ok=True)

    print("Carregando XTTS v2 (uma vez)...", flush=True)
    t0 = time.time()
    from TTS.api import TTS
    tts = TTS(model_name=MODEL, progress_bar=False).to("cpu")
    print(f"  pronto em {time.time()-t0:.0f}s\n", flush=True)

    disponiveis = list(tts.synthesizer.tts_model.speaker_manager.name_to_id.keys())
    alvos = disponiveis if todos else [s for s in CURTA if s in disponiveis]
    faltando = [s for s in CURTA if s not in disponiveis]
    if faltando and not todos:
        print("  (nao encontrados:", ", ".join(faltando), ")\n")

    for i, nome in enumerate(alvos, 1):
        arq = os.path.join(SAIDA, nome.replace(" ", "_") + ".wav")
        if os.path.exists(arq):
            print(f"[{i}/{len(alvos)}] {nome} — ja existe, pulando")
            continue
        t0 = time.time()
        try:
            tts.tts_to_file(text=FRASE, speaker=nome, language="en",
                            file_path=arq, split_sentences=False,
                            temperature=0.3, repetition_penalty=5.0)
            print(f"[{i}/{len(alvos)}] {nome} — {time.time()-t0:.0f}s")
        except Exception as e:
            print(f"[{i}/{len(alvos)}] {nome} — FALHOU: {type(e).__name__}")

    print(f"\nAmostras em: audio/vozes/")
    print("Ouca e me diga quais servem. Sugestao de comando:")
    print("  powershell -Command \"Get-ChildItem audio\vozes\*.wav | ForEach-Object { $_.BaseName; ffplay -nodisp -autoexit -loglevel quiet $_.FullName }\"")


if __name__ == "__main__":
    main()
