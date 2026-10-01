# English Interview Trainer

Ferramentas para treinar **inglês falado para entrevista técnica**, com medição
objetiva. Roda **100% local** — nenhum áudio sai da sua máquina.

Não é curso e não ensina gramática. É instrumentação: grava você, mede o que
importa numa entrevista, e aponta onde está o problema.

---

## A ideia em uma frase

Se um transcritor automático não entende o que você falou, um entrevistador sob
carga cognitiva também não vai. Erro de transcrição é sinal **objetivo** de falha
de inteligibilidade, e dá para medir isso todo dia.

---

## O que é medido

| Métrica | Alvo | Por quê |
|---|---|---|
| **Ritmo** | 110–150 wpm | abaixo disso é produção palavra por palavra |
| **Travadas** (pausa > 3s) | até 2 | destrói confiança percebida mais que erro gramatical |
| **TTF** (tempo até a 1ª palavra) | até 3 s | entrevistador tolera resposta simples, não silêncio longo |
| **Acurácia do transcritor** | 92% ou mais | proxy de inteligibilidade |

**Sotaque não é medido e não deve ser treinado.** Acurácia alta *com* sotaque
forte é o resultado desejado — sotaque não reprova, ininteligibilidade reprova.

---

## Passo 1 — Instalar

Precisa de **Python 3.10+**, **ffmpeg** e **ffprobe** no PATH.

```powershell
git clone <url> english-interview-trainer
cd english-interview-trainer

winget install Gyan.FFmpeg
pip install -r requirements.txt

copy config.example.json config.json
powershell -ExecutionPolicy Bypass -File setup.ps1
```

Reabra o terminal depois de instalar o ffmpeg. O `setup.ps1` verifica os seis
pré-requisitos e diz como resolver o que faltar.

---

## Passo 2 — Descobrir qual microfone funciona

Pule este passo e você vai gravar silêncio sem perceber. Acontece.

```powershell
powershell -File diagnostico_mic.ps1
```

Ele testa cada dispositivo com você falando e diz qual usar. Anote o nome — ele
vai no parâmetro `-Dispositivo` dos outros comandos.

---

## Passo 3 — Medir seu ponto de partida

Sem isso, "melhorei" é opinião.

```powershell
powershell -File gravar.ps1 -Tag baseline -Segundos 400 -Dispositivo "SEU MIC"
```

Responda estas quatro em sequência, **sem consultar nada e sem corrigir erro**.
Diga "question one", "question two" e assim por diante antes de cada uma, para
dar para separar na análise:

1. Tell me about yourself.
2. Walk me through your professional experience.
3. Tell me about the most challenging project you have worked on.
4. Why are you looking for a new opportunity?

Depois:

```powershell
python pron_check.py audio\baseline-MMDD-HHMM.wav
```

Anote ritmo e travadas. É o seu marco zero.

---

## Passo 4 — Escrever seus blocos

Um `.txt` por resposta, em `refs/`. O nome do arquivo vira o nome do bloco.

Comece copiando os modelos:

```powershell
copy exemplos\*.txt refs\
```

E **reescreva com o seu conteúdo**. Leia `exemplos/README.md` — as regras de
escrita importam mais que o conteúdo: frases curtas, estruturas que você já
domina, siglas faladas letra por letra escritas por extenso.

---

## Passo 5 — Gerar o áudio-modelo

Duas opções.

### Opção A — voz do Windows, instantânea e robótica

```powershell
powershell -File ouvir.ps1 -Arquivo refs\apresentacao.txt
```

Usa a voz em inglês instalada no Windows. Serve para conferir uma palavra na hora
e para os drills de fonema: `-Drill th`, `er`, `ed`, `tion`, `stress`, `pares`.

Se não houver voz em inglês instalada: **Configurações, Hora e idioma, Idioma,
adicionar English (United States)** marcando a opção de **Fala**.

### Opção B — sua própria voz clonada, melhor para shadowing

Requer XTTS v2 num ambiente separado e cerca de 30 segundos de gravação sua como
referência. Aponte os caminhos em `config.json` e rode:

```powershell
<venv-do-xtts>\Scripts\python.exe -u gerar_modelos.py
```

**Por que vale o trabalho:** ouvir o texto na sua própria voz remove a barreira
"não consigo soar como esse narrador". O alvo passa a ser atingível porque é você.

Medido num caso real: XTTS com voz de referência em português gera inglês com
pronúncia **correta** — a referência contribui timbre, não fonologia.

---

## Passo 6 — Treinar

```powershell
powershell -File praticar.ps1
powershell -File praticar.ps1 apresentacao -Lento -Vezes 5
```

O primeiro comando lista os blocos disponíveis. O `-Lento` toca a 0.75x **sem
alterar o tom da voz**. Use desde o começo: shadowing numa velocidade que você
não alcança treina frustração, não fala.

Fale **junto**, em voz alta. Se a sua voz não está saindo, não é shadowing, é
podcast.

---

## Passo 7 — Medir de novo

```powershell
powershell -File gravar.ps1 -Tag apres -Segundos 120 -Dispositivo "SEU MIC" -Ref refs\apresentacao.txt -Analisar
```

O `-Analisar` já roda a análise e mostra ritmo, travadas e acurácia na hora.

**Meça contra o teto do modelo, não contra 100%.** Rode o `pron_check.py` no
próprio áudio-modelo antes: se ele tira 94%, o seu alvo é 94%. Nomes próprios,
siglas e termos técnicos derrubam a acurácia sem que nada esteja errado.

---

## Passo 8 — Simular o imprevisto

Responder o que você preparou é fácil. O que derruba é o não previsto.

```powershell
powershell -File simular.ps1 -Modo rh -N 4
powershell -File simular.ps1 -Modo tecnica -N 3
```

A pergunta é **sorteada e tocada só em áudio** — você não vê escrito, o que treina
compreensão junto. No modo técnica, dispara um **follow-up** depois de cada
resposta, que é onde resposta decorada desmorona.

São 85 perguntas em `perguntas/banco.txt`, em seis categorias. Adicione as suas.

```powershell
python analisar_simulacao.py audio\sim-MMDD-HHMM
```

---

## Passo 9 — Treinar o ouvido, se esse for o seu gargalo

Entender é um sistema diferente de falar, e falar não treina ouvido.

```powershell
python ditado.py audio\palestra.mp3 --legenda audio\palestra.vtt
```

Toca um trecho, você escreve o que entendeu, e ele marca entre colchetes o que
você perdeu, acumulando as palavras mais perdidas no fim.

**Use `--legenda` sempre que houver legenda oficial.** Sem ela o gabarito vem do
Whisper, que erra justamente no sotaque difícil — e gabarito errado ensina errado.

Fontes: palestras de conferência no YouTube e cursos com transcrição oficial.

```bash
yt-dlp -x --audio-format mp3 --write-sub --sub-lang en "URL"
```

Prefira `--write-sub` (legenda humana) a `--write-auto-sub` (gerada por máquina,
mesmo problema do Whisper).

---

## As ferramentas

| Script | O que faz |
|---|---|
| `pron_check.py` | **o juiz** — ritmo, travadas, TTF, acurácia |
| `gravar.ps1` | grava com checagem de nível, barra gravação fraca |
| `praticar.ps1` | toca os modelos: `-Lento`, `-Texto`, `-Vezes`, `-Tudo` |
| `ouvir.ps1` | voz do Windows: palavra avulsa e drills de fonema |
| `gerar_modelos.py` | gera os modelos com voz clonada (XTTS) |
| `simular.ps1` | entrevista simulada, pergunta aleatória em áudio |
| `analisar_simulacao.py` | analisa a sessão inteira |
| `ditado.py` | treino de ouvido por ditado |
| `diagnostico_mic.ps1` | descobre qual microfone capta |
| `setup.ps1` | verifica os pré-requisitos |
| `amostrar_vozes.py` | amostras das 58 vozes do XTTS, para escolher de ouvido |

---

## Decisões de método que não são óbvias

**Modelo pequeno como juiz.** `--model base`, não `large`. Modelo grande usa prior
de linguagem e *conserta* a sua pronúncia, escondendo o erro. O pequeno transcreve
o que você realmente falou. Para diagnóstico você quer o juiz implacável.

**Teto de referência, não 100%.** Cada modelo é medido pelo mesmo juiz, e o número
dele é o seu alvo.

**Experimento de controle antes de concluir.** Quando o juiz erra uma palavra, gere
o mesmo texto em TTS e passe pelo mesmo juiz. Isso separa "a sua pronúncia falhou"
de "o transcritor não conhece essa palavra".

**Colinha de gatilhos, não roteiro.** Material fechado engessa; palavra-chave solta
deixa você conversar. Para a entrevista, leve bullets, não parágrafos.

---

## Limitações conhecidas

- Acurácia de STT é proxy **grosseiro**: diz "ininteligível", não diz qual fonema
  falhou. A análise fonética depende de alguém lendo as substituições.
- Prosódia e entonação não são medidas, só ritmo e pausas.
- Leitura de ano (`twenty twenty four` contra `2024`) conta como um erro.
- Os `.ps1` são **Windows-only** (dshow e SAPI). O `pron_check.py`, o `ditado.py` e
  o `analisar_simulacao.py` são multiplataforma.
- Nenhum TTS reproduz bem sotaque difícil. Para treinar ouvido, use áudio real.

---

## Estrutura

```
refs/        seus textos-alvo (.txt)    -> versionado
audio/       gravações e modelos        -> NÃO versionado
logs/        pron_log.jsonl             -> versionado, é o seu histórico
perguntas/   banco e follow-ups
exemplos/    modelos para copiar para refs/
docs/        método
```
