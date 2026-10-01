#!/usr/bin/env python
"""
pron_check.py - Analise objetiva de fala em ingles para treino de entrevista.

Roda 100% local (openai-whisper + ffmpeg). Nenhum audio sai da maquina.

Uso:
    # fala espontanea (sem texto de referencia)
    python pron_check.py audio/dia01_tellme.m4a

    # com texto de referencia (detecta erro de pronuncia por palavra)
    python pron_check.py audio/dia01_tellme.m4a --ref refs/tell_me_about_yourself.txt

    # modelo maior (mais tolerante - use para comparar)
    python pron_check.py audio/x.m4a --model small

Por que modelo pequeno: 'base' tem prior de linguagem fraco, entao ele transcreve
o que voce FALOU. 'large' conserta sua pronuncia usando contexto e esconde o erro.
Para diagnostico voce quer o juiz implacavel. Use 'base' como padrao.

Saida: relatorio no terminal + JSON acumulado em logs/pron_log.jsonl

LIMITACAO CONHECIDA: numeros lidos como ano ("twenty twenty four" x "2024")
ainda contam como 1 substituicao. Numeros normais e porcentagens
("seventy-five percent" x "75%") estao normalizados e nao geram erro falso.
"""

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

# --- limiares (ajustaveis) ---------------------------------------------------
PAUSE_MIN = 1.0        # gap entre palavras que ja conta como pausa
STALL_MIN = 3.0        # gap que conta como "travada" (metrica do TRACKING.md)
WPM_TARGET = (110, 150)  # faixa alvo para entrevista; abaixo = travado, acima = corrido
FILLERS = {"uh", "um", "uhm", "ah", "eh", "hmm", "mm", "er", "erm"}

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(ROOT, "logs", "pron_log.jsonl")


# --- normalizacao ------------------------------------------------------------
def norm_word(w):
    """minuscula, sem acento, sem pontuacao - para alinhar transcricao vs referencia"""
    w = unicodedata.normalize("NFKD", w)
    w = "".join(c for c in w if not unicodedata.combining(c))
    w = w.lower()
    w = re.sub(r"[^a-z0-9']", "", w)
    return w


# numeros por extenso -> digito. O whisper escreve "75%" onde voce falou
# "seventy-five percent"; sem isso o diff acusaria erro de pronuncia que nao
# existe - e te mandaria treinar a frase que voce ja fala certo.
_UNI = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19}
_DEZ = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_ESCALA = {"hundred": 100, "thousand": 1000, "million": 1000000}


def pre_tokenize(text):
    """separa hifen (seventy-five -> seventy five) e expande simbolos"""
    text = text.replace("%", " percent ")
    text = text.replace("$", " dollars ")
    text = re.sub(r"[-–—/]", " ", text)
    return text


def collapse_numbers(ws):
    """['seventy','five','percent'] -> ['75','percent']"""
    out, i = [], 0
    while i < len(ws):
        w = ws[i]
        if w in _UNI or w in _DEZ or w in _ESCALA:
            total, atual, consumiu = 0, 0, 0
            while i < len(ws):
                t = ws[i]
                if t in _UNI:
                    atual += _UNI[t]
                elif t in _DEZ:
                    atual += _DEZ[t]
                elif t == "hundred":
                    atual = (atual or 1) * 100
                elif t in _ESCALA:
                    total += (atual or 1) * _ESCALA[t]
                    atual = 0
                elif t == "and" and consumiu:
                    pass  # "one hundred and five"
                else:
                    break
                i += 1
                consumiu += 1
            val = total + atual
            out.append(str(val) if consumiu else w)
            if not consumiu:
                i += 1
        else:
            out.append(w)
            i += 1
    return out


# Contracoes: o STT transcreve o que foi falado ("I'm"), a referencia pode ter a
# forma cheia ("I am"). Sem normalizar isso, fala CORRETA conta como erro - e o
# aluno "corrigiria" para uma forma menos natural. Expande tudo para forma cheia.
_CONTRACOES = {
    "im": "i am", "ive": "i have", "ill": "i will", "id": "i would",
    "youre": "you are", "youve": "you have", "youll": "you will",
    "hes": "he is", "shes": "she is", "its": "it is", "thats": "that is",
    "theres": "there is", "heres": "here is", "whats": "what is",
    "were": "we are", "weve": "we have", "well": "we will",
    "theyre": "they are", "theyve": "they have",
    "dont": "do not", "doesnt": "does not", "didnt": "did not",
    "cant": "can not", "couldnt": "could not", "cannot": "can not",
    "wont": "will not", "wouldnt": "would not", "shouldnt": "should not",
    "isnt": "is not", "arent": "are not", "wasnt": "was not",
    "werent": "were not", "havent": "have not", "hasnt": "has not",
    "hadnt": "had not", "lets": "let us",
}

def expandir_contracoes(ws):
    """
    So expande quando HA apostrofo. E o que desambigua os pares reais:
        it's -> it is    |  its  = possessivo, fica
        we're -> we are  |  were = passado de be, fica
        we'll -> we will |  well = adverbio, fica
        I'd -> I would   |  id   = substantivo, fica
    O whisper sempre escreve a contracao com apostrofo, entao o sinal e confiavel.
    """
    out = []
    for w in ws:
        if "'" in w:
            alvo = _CONTRACOES.get(w.replace("'", ""))
            if alvo:
                out.extend(alvo.split())
                continue
        out.append(w.replace("'", ""))
    return out


def juntar_digitos(ws):
    """
    O whisper quebra numero longo em grupos: 18487680 -> "18 487 680".
    Junta sequencias de tokens puramente numericos num token so, nos DOIS lados,
    senao texto cheio de cifras (roteiro tecnico) reporta erro que nao existe.
    """
    out, i = [], 0
    while i < len(ws):
        if ws[i].isdigit():
            j = i
            while j < len(ws) and ws[j].isdigit():
                j += 1
            out.append("".join(ws[i:j]))
            i = j
        else:
            out.append(ws[i])
            i += 1
    return out


def words_of(text):
    ws = [w for w in (norm_word(t) for t in pre_tokenize(text).split()) if w]
    return juntar_digitos(collapse_numbers(expandir_contracoes(ws)))


# --- transcricao -------------------------------------------------------------
def preprocess(audio):
    """
    Normaliza para 16kHz mono PCM antes do whisper.
    Sem isso, audio fora de 16k faz o decoder abortar no meio e truncar a
    transcricao - o que viraria "travada" falsa no relatorio.
    """
    import subprocess
    import tempfile

    out = os.path.join(tempfile.gettempdir(), "pron_" + str(abs(hash(audio)))[:10] + ".wav")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", audio,
           "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out
    except FileNotFoundError:
        print("  aviso: ffmpeg nao achado, usando audio bruto", flush=True)
        return audio
    except subprocess.CalledProcessError as e:
        print(f"  aviso: ffmpeg falhou ({e.stderr.decode('utf8','ignore')[:120]}), usando audio bruto")
        return audio


def transcribe(audio, model_name):
    import whisper

    if not os.path.exists(audio):
        sys.exit(f"ERRO: audio nao encontrado: {audio}")

    print(f"[1/3] carregando modelo '{model_name}' (CPU)...", flush=True)
    model = whisper.load_model(model_name)

    print(f"[2/3] normalizando audio (16kHz mono)...", flush=True)
    prepped = preprocess(audio)

    print(f"      transcrevendo {os.path.basename(audio)}...", flush=True)
    result = model.transcribe(
        prepped,
        language="en",              # forca ingles: nao deixa cair pra portugues
        task="transcribe",
        word_timestamps=True,
        # fallback de temperatura: se o decode falhar nos thresholds, ele tenta
        # de novo mais quente em vez de desistir e truncar o resto do audio.
        temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
        condition_on_previous_text=False,  # nao usa contexto pra "consertar" voce
        compression_ratio_threshold=2.4,
        logprob_threshold=-1.0,
        no_speech_threshold=0.6,
        fp16=False,
    )
    if prepped != audio:
        try:
            os.remove(prepped)
        except OSError:
            pass
    return result


def audio_duration(path):
    """duracao real via ffprobe - usada pra detectar alucinacao"""
    import subprocess
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            check=True, capture_output=True, text=True).stdout.strip()
        return float(out)
    except Exception:
        return None


def flatten_words(result, dur=None):
    """
    Extrai palavras com timestamp.

    Nao descarta nada em silencio: palavra fora do alfabeto latino ou com
    timestamp depois do fim do audio e ALUCINACAO do whisper, e precisa
    aparecer no relatorio - senao o relatorio esconde a falha do proprio juiz.
    """
    out, halluc = [], []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            raw = w.get("word", "").strip()
            if not raw:
                continue
            item = {
                "raw": raw,
                "norm": norm_word(raw),
                "start": float(w.get("start", 0.0)),
                "end": float(w.get("end", 0.0)),
            }
            fora_do_audio = dur is not None and item["start"] > dur + 0.5
            nao_latino = not item["norm"] and any(ord(c) > 127 for c in raw)
            if fora_do_audio or nao_latino:
                item["motivo"] = "fora do audio" if fora_do_audio else "nao-latino"
                halluc.append(item)
            elif item["norm"]:
                out.append(item)
    return out, halluc


# --- metricas de prosodia (objetivas, sem ML) -------------------------------
def prosody(words, dur=None):
    if not words:
        return {"erro": "nenhuma palavra detectada"}

    ttf = round(words[0]["start"], 2)
    total = round(words[-1]["end"] - words[0]["start"], 2)

    gaps = []
    for a, b in zip(words, words[1:]):
        g = b["start"] - a["end"]
        if g >= PAUSE_MIN:
            gaps.append({
                "depois_de": a["raw"],
                "antes_de": b["raw"],
                "segundos": round(g, 2),
                "em": round(a["end"], 2),
            })

    stalls = [g for g in gaps if g["segundos"] >= STALL_MIN]
    silence = sum(g["segundos"] for g in gaps)
    speaking = max(total - silence, 0.01)
    wpm = round(len(words) / (speaking / 60.0))
    fillers = [w["raw"] for w in words if w["norm"] in FILLERS]

    return {
        "ttf_s": ttf,
        "cobertura_audio_pct": round(100.0 * total / dur, 1) if dur else None,
        "duracao_audio_s": round(dur, 2) if dur else None,
        "duracao_total_s": total,
        "tempo_falando_s": round(speaking, 2),
        "silencio_interno_s": round(silence, 2),
        "palavras": len(words),
        "wpm": wpm,
        "pausas": len(gaps),
        "travadas": len(stalls),
        "lista_pausas": gaps,
        "lista_travadas": stalls,
        "fillers": len(fillers),
        "lista_fillers": fillers,
    }


# --- diff vs referencia (proxy de pronuncia) --------------------------------
def compare(ref_text, hyp_words):
    ref = words_of(ref_text)
    # mesma pipeline nos dois lados: sem isso, "75%" vs "seventy-five percent"
    # viraria erro de pronuncia falso
    hyp = words_of(" ".join(w["raw"] for w in hyp_words))
    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)

    subs, dels, ins, ok = [], [], [], 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            ok += i2 - i1
        elif tag == "replace":
            r, h = ref[i1:i2], hyp[j1:j2]
            for k in range(max(len(r), len(h))):
                subs.append({
                    "esperado": r[k] if k < len(r) else "",
                    "ouvido": h[k] if k < len(h) else "",
                })
        elif tag == "delete":
            dels.extend(ref[i1:i2])
        elif tag == "insert":
            ins.extend(hyp[j1:j2])

    errs = len(subs) + len(dels) + len(ins)
    return {
        "palavras_ref": len(ref),
        "acertos": ok,
        "wer_pct": round(100.0 * errs / max(len(ref), 1), 1),
        "acuracia_pct": round(100.0 * ok / max(len(ref), 1), 1),
        "substituicoes": subs,
        "omitidas": dels,
        "inseridas": ins,
    }


# --- relatorio ---------------------------------------------------------------
def bar(v, good, bad):
    """indicador simples: OK / ATENCAO / RUIM"""
    if (good <= bad and v <= good) or (good > bad and v >= good):
        return "OK"
    if (good <= bad and v <= bad) or (good > bad and v >= bad):
        return "ATENCAO"
    return "RUIM"


def report(audio, model_name, transcript, pro, cmp_, halluc, dur):
    line = "=" * 66
    print(f"\n{line}\nRELATORIO  |  {os.path.basename(audio)}  |  modelo: {model_name}\n{line}")

    print("\n--- TRANSCRICAO (o que o juiz OUVIU, nao o que voce quis dizer) ---")
    print(transcript.strip() or "(vazio)")

    if halluc:
        print(f"\n!!! ALUCINACAO DO TRANSCRITOR: {len(halluc)} palavra(s) descartada(s) !!!")
        for h in halluc[:8]:
            print(f"    {h['start']:>6.1f}s  {h['raw']!r}  ({h['motivo']})")
        print("    Causa provavel: audio muito baixo, muito ruidoso, ou longos")
        print("    trechos de silencio. NAO confie nas metricas abaixo.")
        print("    Acao: regrave mais perto do microfone, sem silencio no inicio/fim.")

    cobertura = pro.get("cobertura_audio_pct")
    if cobertura is not None and cobertura < 70:
        print(f"\n!!! ATENCAO: fala detectada cobre so {cobertura:.0f}% dos {dur:.1f}s de audio.")
        print("    Ou tem muito silencio, ou o transcritor desistiu no meio.")

    print("\n--- METRICAS DO TRACKING.md ---")
    print(f"  TTF (1a palavra)      {pro['ttf_s']:>6.2f} s   [{bar(pro['ttf_s'], 3.0, 6.0)}]  alvo <= 3.0")
    print(f"  Travadas (>{STALL_MIN:.0f}s)       {pro['travadas']:>6}     [{bar(pro['travadas'], 2, 4)}]  alvo <= 2")
    print(f"  Pausas (>{PAUSE_MIN:.0f}s)         {pro['pausas']:>6}")
    print(f"  Fillers (uh/um)       {pro['fillers']:>6}")
    print(f"  Palavras              {pro['palavras']:>6}")
    print(f"  Duracao               {pro['duracao_total_s']:>6.1f} s")
    lo, hi = WPM_TARGET
    wpm_flag = "OK" if lo <= pro["wpm"] <= hi else ("LENTO" if pro["wpm"] < lo else "RAPIDO")
    print(f"  Ritmo                 {pro['wpm']:>6} wpm [{wpm_flag}]  alvo {lo}-{hi}")

    if pro["lista_travadas"]:
        print("\n--- ONDE VOCE TRAVOU (decore o bloco seguinte a estes pontos) ---")
        for g in pro["lista_travadas"]:
            print(f"  {g['em']:>6.1f}s  {g['segundos']:>4.1f}s de silencio   "
                  f"...{g['depois_de']} [PAUSA] {g['antes_de']}...")

    if cmp_:
        print("\n--- PRONUNCIA (proxy: o STT entendeu o que voce falou?) ---")
        print(f"  Acuracia  {cmp_['acuracia_pct']:>5.1f}%   [{bar(cmp_['acuracia_pct'], 92.0, 80.0)}]  alvo >= 92%")
        print(f"  WER       {cmp_['wer_pct']:>5.1f}%")
        if cmp_["substituicoes"]:
            print("\n  PALAVRAS QUE O JUIZ NAO RECONHECEU:")
            print(f"    {'esperado':<22} {'ouviu':<22}")
            for s in cmp_["substituicoes"][:40]:
                print(f"    {s['esperado']:<22} {s['ouvido'] or '(nada)':<22}")
        if cmp_["omitidas"]:
            print(f"\n  ENGOLIDAS (nao saiu som): {' '.join(cmp_['omitidas'][:30])}")
        if cmp_["inseridas"]:
            print(f"  SOM EXTRA (ouviu algo a mais): {' '.join(cmp_['inseridas'][:30])}")

    print(f"\n{line}")
    print("Cole ESTE relatorio inteiro no chat. Eu diagnostico o fonema por tras")
    print("de cada substituicao e devolvo o drill especifico.")
    print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", help="arquivo de audio (m4a, mp3, wav, ogg...)")
    ap.add_argument("--ref", help="txt com o texto que voce TENTOU falar")
    ap.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"],
                    help="base = juiz implacavel (padrao). small = mais tolerante.")
    ap.add_argument("--tag", default="", help="rotulo pro log, ex: dia03-tellme")
    args = ap.parse_args()

    # console do Windows e cp1252 e explode se o whisper alucinar CJK
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    dur = audio_duration(args.audio)
    result = transcribe(args.audio, args.model)
    words, halluc = flatten_words(result, dur)
    pro = prosody(words, dur)
    if "erro" in pro:
        sys.exit("ERRO: nenhuma fala detectada. Confira o microfone / o arquivo.")

    cmp_ = None
    if args.ref:
        if not os.path.exists(args.ref):
            sys.exit(f"ERRO: referencia nao encontrada: {args.ref}")
        with open(args.ref, encoding="utf-8-sig") as f:  # -sig remove BOM
            cmp_ = compare(f.read(), words)

    print("[3/3] calculando metricas...", flush=True)
    report(args.audio, args.model, result.get("text", ""), pro, cmp_, halluc, dur)

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    entry = {
        "quando": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "tag": args.tag or os.path.splitext(os.path.basename(args.audio))[0],
        "audio": os.path.basename(args.audio),
        "modelo": args.model,
        "transcricao": result.get("text", "").strip(),
        "prosodia": {k: v for k, v in pro.items() if not k.startswith("lista_")},
        "pronuncia": {k: v for k, v in (cmp_ or {}).items()
                      if k in ("acuracia_pct", "wer_pct", "palavras_ref")} or None,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"\nlog: {os.path.relpath(LOG_PATH, ROOT)}  (tag: {entry['tag']})")


if __name__ == "__main__":
    main()
