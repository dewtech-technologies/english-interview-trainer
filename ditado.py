#!/usr/bin/env python
"""
ditado.py - Treino de ouvido por ditado. Voce ouve, escreve, compara.

Feito para sotaque que voce NAO decodifica (indiano, no seu caso).
Falar nao treina isso. Escrever o que ouviu, sim: expoe exatamente quais
palavras seu ouvido nao esta separando.

    python ditado.py audio/palestra.mp3              # sessao interativa
    python ditado.py audio/palestra.mp3 --listar     # so lista os trechos
    python ditado.py audio/palestra.mp3 --de 10      # comeca no trecho 10
    python ditado.py audio/palestra.mp3 --modelo small

Durante a sessao:
    ENTER vazio  -> repete o trecho
    "-"          -> repete a 0.75x (mais lento)
    "--"         -> repete a 0.6x
    "?"          -> desiste e mostra a resposta
    "sair"       -> encerra e salva

Transcricao de referencia fica em cache: <audio>.ditado.json
"""
import argparse
import difflib
import io
import json
import os
import re
import subprocess
import sys


def falar(msg=""):
    print(msg, flush=True)


def ler_legenda(caminho):
    """
    Le .srt ou .vtt como GABARITO.

    Por que isso existe: o whisper e menos preciso justamente no sotaque que
    voce quer treinar. Usar a transcricao dele como gabarito pode te corrigir
    para o lado errado. Legenda oficial (LinkedIn Learning, YouTube com legenda
    humana) e gabarito confiavel.
    """
    txt = io.open(caminho, encoding="utf-8-sig").read()
    tempo = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
        r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})")

    def seg(h, m, s_, ms):
        return int(h) * 3600 + int(m) * 60 + int(s_) + int(ms.ljust(3, "0")) / 1000.0

    out, atual = [], None
    for linha in txt.split("\n"):
        l = linha.strip()
        m = tempo.search(l)
        if m:
            if atual and atual["txt"].strip():
                out.append(atual)
            atual = {"i": len(out), "ini": seg(*m.groups()[:4]),
                     "fim": seg(*m.groups()[4:]), "txt": ""}
            continue
        if atual is None:
            continue
        if not l or l.isdigit() or l.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            continue
        l = re.sub(r"<[^>]+>", "", l)
        l = re.sub(r"^-\s*", "", l)
        atual["txt"] = (atual["txt"] + " " + l).strip()
    if atual and atual["txt"].strip():
        out.append(atual)

    # junta legendas muito curtas: trecho de 1s nao treina nada
    juntos, buf = [], None
    for s_ in out:
        if buf is None:
            buf = dict(s_)
        elif buf["fim"] - buf["ini"] < 4.0 and len(buf["txt"].split()) < 12:
            buf["fim"] = s_["fim"]
            buf["txt"] = buf["txt"] + " " + s_["txt"]
        else:
            juntos.append(buf)
            buf = dict(s_)
    if buf:
        juntos.append(buf)
    for i, s_ in enumerate(juntos):
        s_["i"] = i
    return juntos



def transcrever(audio, modelo):
    cache = audio + ".ditado.json"
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)

    falar(f"[1/2] transcrevendo com '{modelo}' (so na primeira vez)...")
    import whisper
    m = whisper.load_model(modelo)
    r = m.transcribe(audio, language="en", word_timestamps=True,
                     temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
                     condition_on_previous_text=False, fp16=False)
    segs = [{"i": i, "ini": float(s["start"]), "fim": float(s["end"]),
             "txt": s["text"].strip()}
            for i, s in enumerate(r.get("segments", [])) if s["text"].strip()]
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(segs, f, ensure_ascii=False, indent=1)
    falar(f"      {len(segs)} trechos, cache em {os.path.basename(cache)}")
    return segs


def tocar(audio, ini, fim, vel=1.0):
    dur = max(fim - ini, 0.4)
    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
           "-ss", f"{ini:.2f}", "-t", f"{dur:.2f}"]
    if vel != 1.0:
        cmd += ["-af", f"atempo={vel}"]
    cmd.append(audio)
    subprocess.run(cmd)


def palavras(t):
    return [w for w in re.sub(r"[^a-z0-9' ]", " ", t.lower()).split() if w]


def comparar(esperado, ouvido):
    a, b = palavras(esperado), palavras(ouvido)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    marcado, perdidas, acertos = [], [], 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            marcado += a[i1:i2]
            acertos += i2 - i1
        elif tag in ("replace", "delete"):
            for w in a[i1:i2]:
                marcado.append(f"[{w}]")
                perdidas.append(w)
    pct = 100.0 * acertos / max(len(a), 1)
    return pct, " ".join(marcado), perdidas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--legenda", help=".srt ou .vtt como gabarito (preferivel: o whisper erra justamente no sotaque que voce treina)")
    ap.add_argument("--modelo", default="small",
                    help="small e o minimo para sotaque dificil (base erra demais)")
    ap.add_argument("--de", type=int, default=1, help="comecar no trecho N")
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if not os.path.exists(a.audio):
        sys.exit(f"ERRO: nao encontrado: {a.audio}")

    if a.legenda:
        if not os.path.exists(a.legenda):
            sys.exit(f"ERRO: legenda nao encontrada: {a.legenda}")
        segs = ler_legenda(a.legenda)
        falar(f"gabarito: {os.path.basename(a.legenda)} ({len(segs)} trechos)")
    else:
        falar("AVISO: sem --legenda, o gabarito vem do whisper, que erra em")
        falar("       sotaque dificil. Prefira legenda oficial quando houver.")
        segs = transcrever(a.audio, a.modelo)
    if not segs:
        sys.exit("ERRO: nenhum trecho detectado.")

    if a.listar:
        for s in segs:
            falar(f"  {s['i']+1:3}  {s['ini']:6.1f}s  {s['txt'][:88]}")
        falar(f"\n  {len(segs)} trechos")
        return

    linha = "=" * 70
    falar(f"\n{linha}\n DITADO — {os.path.basename(a.audio)}\n{linha}")
    falar("  ENTER = repetir   '-' = 0.75x   '--' = 0.6x   '?' = revelar   'sair'")
    falar(f"{linha}")

    dificeis, notas = [], []
    for s in segs[a.de - 1:]:
        n = s["i"] + 1
        falar(f"\n--- trecho {n}/{len(segs)}  ({s['ini']:.0f}s) ---")
        tocar(a.audio, s["ini"], s["fim"])
        while True:
            try:
                r = input("  > ").strip()
            except EOFError:
                r = "sair"
            if r == "":
                tocar(a.audio, s["ini"], s["fim"]); continue
            if r == "-":
                tocar(a.audio, s["ini"], s["fim"], 0.75); continue
            if r == "--":
                tocar(a.audio, s["ini"], s["fim"], 0.6); continue
            if r == "?":
                falar(f"  resposta: {s['txt']}")
                dificeis.append({"n": n, "txt": s["txt"], "pct": 0.0})
                break
            if r.lower() in ("sair", "quit", "exit"):
                segs = segs[:1]
                r = None
                break
            pct, marcado, perdidas = comparar(s["txt"], r)
            notas.append(pct)
            falar(f"  {pct:.0f}%  {marcado}")
            if perdidas:
                falar(f"  perdeu: {' '.join(perdidas)}")
                dificeis.append({"n": n, "txt": s["txt"], "pct": pct,
                                 "perdidas": perdidas})
            break
        if r is None:
            break

    falar(f"\n{linha}\n RESUMO\n{linha}")
    if notas:
        falar(f"  trechos feitos : {len(notas)}")
        falar(f"  media          : {sum(notas)/len(notas):.0f}%")
    if dificeis:
        todas = [w for d in dificeis for w in d.get("perdidas", [])]
        from collections import Counter
        top = Counter(todas).most_common(15)
        falar(f"\n  PALAVRAS QUE VOCE MAIS PERDEU:")
        for w, c in top:
            falar(f"    {c}x  {w}")
        rel = a.audio + ".dificeis.json"
        with open(rel, "w", encoding="utf-8") as f:
            json.dump(dificeis, f, ensure_ascii=False, indent=1)
        falar(f"\n  detalhes em {os.path.basename(rel)}")
    falar("")


if __name__ == "__main__":
    main()
