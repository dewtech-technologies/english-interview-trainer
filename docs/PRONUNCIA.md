# Como sua pronúncia vai ser avaliada

## O limite, dito primeiro

**Eu não escuto áudio.** Não tenho entrada de áudio nesta sessão. Se você me mandar um `.mp3`, eu não ouço nada. Qualquer promessa de "manda o áudio que eu avalio o sotaque" seria mentira.

O que existe é um esquema de 3 camadas em que **a máquina ouve e eu diagnostico**. Cada camada tem um limite diferente, declarado.

---

## Camada 1 — Juiz objetivo: o transcritor (`pron_check.py`)

**Princípio:** se um STT não entende o que você falou, um humano sob carga cognitiva de entrevista também não vai entender. Erro de transcrição é sinal objetivo de falha de inteligibilidade.

Roda **100% local** (openai-whisper + ffmpeg, já instalados na sua máquina). Nenhum áudio sai do computador.

```bash
python pron_check.py audio/dia03_tellme.m4a --ref refs/tell_me_about_yourself.txt --model base
```

O que ele mede, tudo objetivo:

| Métrica | Como | Por que importa |
|---|---|---|
| **TTF** | timestamp da 1ª palavra | entrevistador tolera resposta simples, não tolera 8s de silêncio |
| **Travadas** | gaps > 3s entre palavras | destrói confiança percebida mais que erro gramatical |
| **WPM** | palavras / tempo falando | < 110 = travado, > 150 = corrido e ininteligível |
| **Acurácia STT** | diff palavra a palavra vs referência | **este é o número de pronúncia** |
| **Palavras não reconhecidas** | tabela `esperado` × `ouvido` | mostra *quais* palavras falharam |
| **Fillers** | contagem de uh/um | |

### Por que `--model base` e não `large`

Contraintuitivo e importante: **modelo grande é péssimo para diagnóstico.** O `large` tem prior de linguagem tão forte que ele *conserta* sua pronúncia usando contexto — você fala errado e ele transcreve certo, escondendo o erro. O `base` transcreve o que você realmente falou.

Use `base` para diagnosticar. Use `small` só para comparar: se `base` erra e `small` acerta, a palavra está no limite — inteligível com contexto, falha sem contexto.

### Guardas contra falso diagnóstico

O harness foi testado e tinha 2 bugs, ambos corrigidos:

- **Alucinação do transcritor.** O Whisper inventa texto em áudio ruim (no meu teste, gerou caracteres chineses e timestamps além do fim do áudio). Se isso ocorrer, o relatório grita `!!! ALUCINACAO !!!` e diz para não confiar nas métricas. Antes da correção, as palavras alucinadas eram descartadas em silêncio e o relatório parecia válido — o pior tipo de bug numa ferramenta de medição.
- **Cobertura baixa.** Se a fala detectada cobre < 70% do áudio, ele avisa. Isso separa "você travou muito" de "o transcritor desistiu".

### O que a Camada 1 NÃO mede

- **Sotaque.** Acurácia alta com sotaque forte é o resultado desejado. Sotaque não reprova em entrevista; ininteligibilidade reprova.
- **Entonação e naturalidade.** STT ignora prosódia.
- **Se um humano acharia agradável.** Fora de escopo, e fora do escopo do plano.

Alvo: **acurácia ≥ 92%** com `base`. Chegando lá, pare de trabalhar pronúncia.

---

## Camada 2 — Eu diagnostico o fonema

Você cola o relatório inteiro no chat. Para cada linha `esperado → ouviu`, eu identifico **qual som** falhou e devolvo o drill.

Isso funciona bem porque interferência português-BR → inglês é altamente sistemática. Exemplo real do meu teste de validação: o transcritor ouviu **"PRTOP"** onde o áudio dizia **"peer-to-peer"** — colapso da vogal longa + queda do /r/ final. Diagnóstico específico, drill específico.

O que eu já sei que vai aparecer no seu caso, antes de você gravar:

| Som | Erro típico BR | Suas palavras de risco |
|---|---|---|
| `/θ/` (th) | vira /t/ ou /f/ | th**r**eat, th**i**rd, au**th**entication, me**th**od |
| `-ed` final | vira /ɛd/ audível | reduc**ed**, implement**ed**, remediat**ed** |
| `/ɪ/` vs `/iː/` | ambos viram /i/ | l**i**ve/leave, **i**t/eat, r**i**sk |
| `/h/` inicial | desaparece | **h**ave, **h**ow, **h**andle |
| `-tion` | vira "-ção" | authoriza**tion**, implementa**tion**, valida**tion** |
| Vogal epentética | "i" extra depois de consoante | *stat**i**ck*, *bug**i***, *cod**i*** |
| `/r/` final | vira R português | secu**r**e, se**r**ve**r**, laye**r** |
| Sílaba tônica | deslocada | **de**velop**ment**, **au**tho**ri**zation, **vul**nerability |

Essas 8 linhas cobrem a grande maioria do que vai reprovar suas palavras. Note que quase todas caem em vocabulário de segurança — ou seja, exatamente nas palavras que você mais vai falar.

---

## Camada 3 — Shadowing com a SUA própria voz (XTTS v2)

Se voce tiver XTTS v2 instalado e cerca de 30 segundos de gravacao da sua propria voz como referencia, da para fazer algo que material didatico comum nao oferece: **gerar o texto da sua apresentacao, em ingles, na sua propria voz.**

Por que isso não é gimmick:

1. Some a barreira "não consigo soar como esse narrador americano" — é você, então o alvo é atingível.
2. XTTS aplica fonemas ingleses do modelo mantendo seu timbre. Você ouve sua voz com a pronúncia corrigida.
3. Repetição sob demanda de **qualquer** frase técnica sua. Nenhum áudio comercial tem "broken object-level authorization" para shadowing.

```powershell
cd <pasta-do-clone-voice>
.\.venv\Scripts\Activate.ps1
python gerar.py "I have experience in software development using Node.js, Python, Java, and Rust."
```

Confirme em `gerar.py` que o idioma está em `en` (o projeto foi feito para narração em PT).

### Medido em um caso real

Eu havia escrito que XTTS com referência em português carregaria sotaque
brasileiro e não serviria como modelo de fonema. **Testei e é falso.**

| Áudio | `base` | `small` |
|---|---|---|
| XTTS voz clonada, frase `The third threat authentication method reduced authorization risk` | **100%** | **100%** |

O XTTS aplica a fonologia inglesa do próprio modelo. A voz de referência
contribui **timbre**, não pronúncia. Na frase que quebrou 4 de 4 tentativas do
do aluno, a voz clonada dele acertou tudo.

### Os dois oráculos, e quando usar cada um

| | `ouvir.ps1` (Zira) | `gerar_modelos.py` (XTTS) |
|---|---|---|
| Voz | robótica, SAPI 2013 | natural, **a sua** |
| Custo | instantâneo | ~60s de carga + ~2,6s por palavra |
| Acurácia STT no texto de 30s | 98,4% | 95,2% |
| Usar para | conferir 1 palavra na hora, drills | **shadowing** de respostas |

A Zira pontua 3 pontos mais alto no STT, e isso **não** decide. Os dois passam
folgado do alvo de 92%, e para shadowing o que importa é prosódia humana —
imitar ritmo robótico ensina ritmo robótico. Use XTTS para as respostas e Zira
para consulta rápida.

**Atenção ao teto:** o teto de referência dos modelos XTTS é ~95%, não 100%.
Meça-se contra ele, não contra 100%.

---

## O loop completo, na prática

```
1. .\gravar.ps1 -Tag dia03-tellme -Segundos 100 -Ref refs\tell_me.txt
   (ou grave no celular e jogue o arquivo em audio/)
2. python pron_check.py audio/<arquivo>.wav --ref refs/pergunta.txt
3. Colar o relatório inteiro no chat
4. Eu devolvo:  fonema culpado · versão corrigida no seu nível · o follow-up que te pegaria
5. Regravar SÓ as palavras que falharam (não a resposta inteira)
6. Anotar no TRACKING.md
```

Passo 5 é onde a maioria erra: regravar a resposta inteira gasta 90s para treinar 4 palavras ruins. Regrave as 4 palavras, 20 vezes.

---

## Regra de prioridade

Pronúncia é a **última** das 6 prioridades do plano original, e continua sendo. Ela entra aqui só porque agora existe uma forma de medir sem me autoenganar.

Se estiver com pouco tempo: acurácia STT ≥ 88% já é suficiente para uma entrevista. Ir de 88% para 95% custa mais tempo do que fechar o Gate 4 (recuperação), e vale muito menos.
