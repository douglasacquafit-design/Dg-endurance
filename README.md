# DG Endurance: assistente semanal do treinador

Automatiza a rotina semanal de uma assessoria de triatlo com 40 a 80 atletas,
para os fins de semana voltarem a ser da família.

| Antes (manual) | Agora |
|---|---|
| Abrir treino por treino de cada atleta | Painel único com todos, **ordenado por quem precisa de atenção** |
| Escrever 60+ mensagens de feedback | Rascunhos prontos **no seu estilo**: você revisa e toca em "Abrir no WhatsApp" |
| Montar a planilha de cada atleta | Semana seguinte montada pela **sua metodologia** (biblioteca de treinos) e enviada ao Garmin/Zwift |
| Descobrir lesão/fadiga tarde demais | **Alertas automáticos**: dor relatada, fadiga alta, carga subindo rápido, HRV caindo, sono ruim, treinos perdidos |

## Como funciona

```
Garmin / Zwift / Rouvy / Strava ──► intervals.icu ──► [DG Endurance] ──► Painel semanal
          ▲                         (central de dados,                    • alertas 🔴🟡🟢
          │                          gratuito, API aberta)                • mensagem WhatsApp (IA)
          │                                                               • comentários dos treinos
          └──────── treinos estruturados ◄──── semana seguinte ◄───────────• próxima semana pronta
```

**Rotina sugerida (cerca de 1h na segunda-feira, em vez do fim de semana inteiro):**

1. **Segunda, 5h40 (automático):** o sistema analisa a semana que terminou e gera o painel.
2. **Segunda de manhã:** você abre o painel e começa pelos 🔴. Para cada atleta:
   lê os alertas, ajusta a mensagem se quiser e toca em **Abrir no WhatsApp** → enviar.
   Os 🟢 levam uns 30 segundos cada.
3. **Até quarta:** confere a próxima semana de cada atleta (já montada) e envia ao intervals.icu,
   que sincroniza com o Garmin e o Zwift.
4. **Fim de semana:** livre. 🏖️

> A semana prescrita é a **seguinte** à atual (configurável em `semanas_a_frente`), para você ter
> a semana toda para revisar sem correria.

## Primeiros passos

### 1. Veja funcionando com atletas fictícios (sem conectar nada)

```bash
pip install -r requirements.txt
python -m dgendurance semana --demo --sem-ia
```

Abra o arquivo `saida/demo-<data>/painel.html` no navegador. São 6 atletas fictícios, um em cada
situação típica: semana perfeita, excesso de carga, faltas, dor relatada, fadiga e sumiço.

### 2. Monte a central no intervals.icu (uma vez)

1. Crie sua conta de treinador em [intervals.icu](https://intervals.icu) (gratuito).
2. Cada atleta cria uma conta, conecta **Garmin**, **Strava**, **Zwift** e/ou **Rouvy**
   (Settings → Connections) e **compartilha a conta com você** (Settings → Coach).
3. Peça para os atletas ativarem no Garmin a sincronização de **HRV, sono e FC de repouso**
   (vai para o "wellness" do intervals.icu e alimenta os alertas de fadiga).
4. Gere sua chave: Settings → Developer Settings → API Key.

O TrainingPeaks pode continuar sendo usado pelos atletas que preferirem, mas ele não tem API
aberta. Os comentários de treino do painel têm um botão **Copiar** para colar lá.

### 3. Configure

```bash
cp .env.example .env                              # cole as chaves
python -m dgendurance importar-atletas config/atletas_modelo.xlsx   # cadastro pela planilha
python -m dgendurance testar-conexao              # confere acesso a cada atleta
```

**Cadastro pela planilha:** abra `config/atletas_modelo.xlsx` no Excel ou Google Sheets
(a aba "Como preencher" explica cada coluna), preencha uma linha por atleta, salve e importe.
Também aceita `.csv` (separado por `;` ou `,`). Acentos, telefone com parênteses, datas
`dd/mm/aaaa` e "avançado" com ç são aceitos. Linhas com erro são apontadas e nada é gravado
até corrigir.

| Arquivo | O que é |
|---|---|
| `config/atletas_modelo.xlsx` | Planilha de cadastro dos atletas (gera o `config/atletas.yaml`) |
| `config/atletas.yaml` | Seus atletas: ID do intervals.icu, WhatsApp, nível, ciclo, prova alvo, folgas, observações |
| `config/estilo_feedback.md` | **Seu jeito de escrever.** Cole mensagens reais suas: a IA imita |
| `config/config.yaml` | Limites dos alertas (TSB, rampa, HRV, sono, palavras de dor...) |
| `biblioteca/treinos.yaml` | Sua biblioteca de treinos estruturados (pedal, corrida, natação, força) |
| `biblioteca/semanas.yaml` | Modelo de semana por fase (base, construção, pico, polimento, recuperação) |

### 4. Uso semanal

```bash
python -m dgendurance semana                      # analisa, gera feedbacks e o painel
python -m dgendurance enviar-treinos --pasta saida/2026-11-09             # simulação
python -m dgendurance enviar-treinos --pasta saida/2026-11-09 --confirmar # envia de verdade
python -m dgendurance comentar --pasta saida/2026-11-09 --confirmar       # comentários no intervals.icu
```

Opções úteis: `--atleta Ana` (só um atleta), `--sem-ia` (sem custo), `--data 2026-11-17`.

Nada é enviado aos atletas sem você mandar: as mensagens saem pelo **seu** WhatsApp,
e os treinos só vão ao calendário com `--confirmar`.

## Como a próxima semana é decidida

**Metodologia: polarizada (80/20), 7 dias com dobras.** Cerca de 80% das sessões são leves (Z1-Z2)
e o restante é forte de verdade (VO2, subidas, tiros curtos), quase sem Z3:

| Fase | Semanas até a prova | Treinos fortes na semana | Exemplos |
|---|---|---|---|
| Base | mais de 16 | 2 | VO2 curto no pedal, subidas na corrida |
| Construção | 8 a 16 | 3 | VO2 longo, tiros curtos, natação velocidade, brick |
| Pico | 3 a 7 | 3 | Limiar e ritmo de prova (específico) |
| Polimento | 0 a 2 | ativações curtas | |

Uma semana de avançado para 70.3 fica entre 11 e 12,5h. Para quem treina menos, use `dias_folga` e
`nivel`/`volume` no cadastro.

**Ciclo por atleta:** cada atleta tem o seu (`3:1`, `2:1` ou `livre`), contado de trás para frente a
partir da prova, para a semana leve cair no lugar certo. Sem ciclo no cadastro, vale o
`ciclo_padrao` do `config/config.yaml`.

Depois os alertas ajustam a semana:

| Situação na semana analisada | Próxima semana |
|---|---|
| 🔴 Dor/lesão relatada ou fadiga muito alta | Semana de **recuperação** |
| 🔴 Faltou muito ou sumiu | Mesma fase, **-20% de volume** para retomar |
| 🟡 Sinais de fadiga (HRV, sono, cansaço relatado) | Mesma fase, **-15% de volume** |
| Semana leve do ciclo do atleta (3:1, 2:1...) | Recuperação programada |
| Tudo certo | Fase normal |

O volume ainda é multiplicado pelo nível do atleta, pela distância da prova e pelo `volume`
individual. Os treinos de dias de folga vão para o próximo dia livre.

**Importante:** isso é um ponto de partida para você revisar, não um substituto do seu olho
de treinador. Ajuste os modelos em `biblioteca/` para refletir a sua metodologia.

## Alertas

| 🔴 Atenção já | 🟡 Acompanhar |
|---|---|
| Forma (TSB) ≤ -30 | TSB entre -20 e -30 |
| CTL subiu ≥ 8 na semana | CTL subiu ≥ 5 |
| Cumpriu menos de 50% | Cumpriu menos de 75% |
| 4+ dias sem treinar | HRV 12% abaixo da média de 4 semanas |
| Palavras de dor/lesão no comentário do atleta | Sono < 6h, relato de cansaço/doença, sensação ruim |
| | Treino leve feito forte (RPE ≥ 7) |
| | Fora do 80/20: menos de 75% do tempo em Z1-Z2, ou mais de 15% em Z3 (base/construção) |

Todos os limites são editáveis em `config/config.yaml`.

## IA e custos

Os rascunhos usam a API do Claude (Anthropic), lendo o resumo da semana e seu `estilo_feedback.md`.

- Custo estimado: **cerca de US$ 0,05 a 0,10 por atleta por semana** (80 atletas ≈ US$ 4 a 8/semana,
  ou seja, uns R$ 100 a 200 por mês).
- Sem chave, ou com `--sem-ia`, o sistema usa um modelo de texto simples (sem custo).
- A IA nunca dá diagnóstico: se o atleta relata dor, a mensagem acolhe e pede detalhes.

## Automação no GitHub (opcional)

O arquivo `.github/workflows/semanal.yml` roda toda segunda às 5h41 e deixa o painel para
download em **Actions → Revisão semanal → Artifacts**. Para usar:

1. **Deixe o repositório PRIVADO** (Settings → General → Danger Zone). O painel contém dados de
   saúde e telefones dos atletas, e a automação não roda em repositório público.
2. Em Settings → Secrets and variables → Actions, crie:
   `INTERVALS_API_KEY`, `ANTHROPIC_API_KEY` e `ATLETAS_YAML` (conteúdo do seu `atletas.yaml`).
3. Para enviar os treinos depois de revisar: Actions → Revisão semanal → Run workflow → marque
   "Enviar a próxima semana".

## Piloto com outros treinadores

O sistema atende você e outros treinadores ao mesmo tempo. Cada um tem a própria pasta em
`treinadores/` com atletas, chave do intervals.icu, estilo de feedback e, se quiser, biblioteca de
treinos própria. Essas pastas nunca vão para o GitHub, e a chave de um treinador nunca é usada
para os atletas de outro.

```bash
python -m dgendurance novo-treinador "Marcos Silva" --equipe "MS Triathlon"
python -m dgendurance semana --demo --treinador marcos-silva   # demonstração com a marca dele
python -m dgendurance semana --todos                           # segunda-feira: todos de uma vez
python -m dgendurance treinadores                              # visão geral do piloto
```

O passo a passo completo (convite, entrada, rotina, o que medir e termo de participação)
está em **[PILOTO.md](PILOTO.md)**.

## Para reduzir o "responder atletas" do dia a dia

Ferramenta nenhuma resolve isso sozinha. Estas práticas combinam com o sistema:

- **Check-in pelo próprio relógio/app:** peça para os atletas registrarem sensação e RPE e
  escreverem um comentário em cada treino (no Garmin/Strava/intervals.icu). O sistema lê esses
  comentários e já gera o alerta. Muita mensagem solta no WhatsApp deixa de ser necessária.
- **Horário de atendimento:** combine que mensagens são respondidas em 1 ou 2 janelas por dia,
  e que no fim de semana só urgência (dor/lesão).
- **Mensagem semanal previsível:** quando o atleta sabe que recebe análise toda segunda,
  ele para de perguntar "e aí, como foi minha semana?".

## Estrutura do código

```
dgendurance/
  intervals.py   cliente da API do intervals.icu
  analise.py     métricas da semana e alertas
  prescricao.py  monta a próxima semana a partir da biblioteca
  feedback.py    rascunhos com IA (Claude) ou modelo de texto
  relatorio.py   painel HTML
  importar.py    importa atletas da planilha
  treinadores.py cadastro de treinadores do piloto
  demo.py        dados fictícios para testar
  cli.py         comandos
tests/           testes automáticos (python -m pytest)
```
