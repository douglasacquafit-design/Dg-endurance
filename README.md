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

Abra o arquivo `saida/<data>/painel.html` no navegador. São 6 atletas fictícios, um em cada
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
cp config/atletas.exemplo.yaml config/atletas.yaml   # cadastre os atletas
python -m dgendurance testar-conexao              # confere acesso a cada atleta
```

| Arquivo | O que é |
|---|---|
| `config/atletas.yaml` | Seus atletas: ID do intervals.icu, WhatsApp, nível, prova alvo, folgas, observações |
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

A fase vem das semanas que faltam até a prova alvo: **base** (mais de 16), **construção** (8 a 16),
**pico** (3 a 7), **polimento** (0 a 2). Depois os alertas ajustam a semana:

| Situação na semana analisada | Próxima semana |
|---|---|
| 🔴 Dor/lesão relatada ou fadiga muito alta | Semana de **recuperação** |
| 🔴 Faltou muito ou sumiu | Mesma fase, **-20% de volume** para retomar |
| 🟡 Sinais de fadiga (HRV, sono, cansaço relatado) | Mesma fase, **-15% de volume** |
| A cada 4 semanas (contadas até a prova) | Recuperação programada |
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
| | Treino leve feito forte (RPE ≥ 7), mais de 35% do tempo em Z3 |

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
  demo.py        dados fictícios para testar
  cli.py         comandos
tests/           testes automáticos (python -m pytest)
```
