#!/usr/bin/env python
"""
analisar_simulacao.py - Analisa uma sessao de simulacao inteira.

    python analisar_simulacao.py audio/sim-0828-1700

Para cada pergunta: ritmo, travadas, TTF e a transcricao do que voce falou.
Sem --ref: e fala espontanea, nao ha texto certo. O que importa aqui e
CONVERSACAO - se voce comecou rapido, se travou, e se a resposta fez sentido.
"""
import glob
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pron_check as pc


def main():
    if len(sys.argv) < 2:
        sys.exit("uso: python analisar_simulacao.py audio/sim-MMDD-HHMM")
    d = sys.argv[1].replace("\\", "/")
    if not os.path.isdir(d):
        sys.exit(f"ERRO: pasta nao encontrada: {d}")

    perg = {}
    pn = os.path.join(d, "perguntas.txt")
    if os.path.exists(pn):
        for l in io.open(pn, encoding="utf-8-sig"):
            l = l.strip()
            if l.startswith("q"):
                perg[l[:3]] = l[4:]

    wavs = sorted(glob.glob(os.path.join(d, "q*.wav")))
    if not wavs:
        sys.exit(f"ERRO: nenhum q*.wav em {d}")

    print(f"\ncarregando whisper 'base'...", flush=True)
    import whisper
    modelo = whisper.load_model("base")

    linha = "=" * 74
    resumo = []
    for w in wavs:
        tag = os.path.basename(w)[:3]
        print(f"\n{linha}\n {tag}  {perg.get(tag, '(pergunta desconhecida)')}\n{linha}")

        dur = pc.audio_duration(w)
        prep = pc.preprocess(w)
        r = modelo.transcribe(prep, language="en", word_timestamps=True,
                              temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
                              condition_on_previous_text=False, fp16=False)
        if prep != w:
            try:
                os.remove(prep)
            except OSError:
                pass

        palavras, halluc = pc.flatten_words(r, dur)
        if not palavras:
            print("  (nenhuma fala detectada - voce ficou em silencio?)")
            resumo.append((tag, 0, 0, 0.0))
            continue
        p = pc.prosody(palavras, dur)

        print(f"\n  VOCE DISSE:\n  {r.get('text','').strip()}\n")
        print(f"  TTF {p['ttf_s']:.1f}s | ritmo {p['wpm']} wpm | "
              f"travadas {p['travadas']} | pausas {p['pausas']} | "
              f"palavras {p['palavras']} | falou {p['tempo_falando_s']:.0f}s de {dur:.0f}s")
        if p["lista_travadas"]:
            for g in p["lista_travadas"]:
                print(f"    travou {g['segundos']:.1f}s em ...{g['depois_de']} [PAUSA] {g['antes_de']}...")
        resumo.append((tag, p["wpm"], p["travadas"], p["ttf_s"]))

    print(f"\n{linha}\n RESUMO DA SESSAO\n{linha}")
    print(f" {'':4} {'ritmo':>6} {'travadas':>9} {'TTF':>6}   pergunta")
    for tag, wpm, tr, ttf in resumo:
        print(f" {tag:4} {wpm:>6} {tr:>9} {ttf:>6.1f}   {perg.get(tag,'')[:44]}")
    validos = [r for r in resumo if r[1] > 0]
    if validos:
        print(f"\n media de ritmo : {sum(r[1] for r in validos)/len(validos):.0f} wpm")
        print(f" total travadas : {sum(r[2] for r in resumo)}")
    print("\n Cole este resumo no chat para eu analisar as respostas.\n")


if __name__ == "__main__":
    main()
