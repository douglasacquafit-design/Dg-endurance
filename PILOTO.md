# Piloto DG Endurance com outros treinadores

**Objetivo:** em 4 semanas, descobrir com 3 a 5 treinadores amigos se o sistema economiza tempo
de verdade, o que falta e quanto eles pagariam, **antes** de investir em um app.

**Formato:** você opera o sistema para eles ("serviço feito à mão"). Toda segunda você roda
um comando e manda o painel de cada um. Eles não instalam nada.

---

## 1. Convite: mostre a demonstração com a marca dele

```bash
python -m dgendurance novo-treinador "Marcos Silva" --equipe "MS Triathlon"
python -m dgendurance semana --demo --treinador marcos-silva
```

Mande para ele o arquivo `saida/marcos-silva/demo-<data>/painel.html`: 6 atletas fictícios
com o nome da equipe dele. Abre no celular. Explique que é um exemplo e que com os atletas
dele os dados serão reais.

Sugestão de mensagem:

> Fala, Marcos! Montei um sistema que analisa a semana de todos os meus atletas, me avisa
> quem precisa de atenção (dor, fadiga, faltas), escreve um rascunho do feedback no meu estilo
> e já monta a semana seguinte. Tirou meu fim de semana de planilha. Estou abrindo um piloto
> gratuito de 4 semanas com alguns amigos treinadores. Te mandei um exemplo com a sua equipe.
> Topa testar?

---

## 2. Entrada do treinador (cerca de 1 hora, uma vez)

Envie esta lista para ele:

> **Para começar o piloto:**
> 1. Crie sua conta de treinador no **intervals.icu** (gratuito).
> 2. Peça para cada atleta: criar conta no intervals.icu, conectar Garmin/Strava/Zwift/Rouvy
>    (Settings → Connections) e **compartilhar com você** (Settings → Coach).
>    Para os alertas de fadiga, peça também para ativarem no Garmin a sincronização de HRV e sono.
> 3. Preencha a planilha de atletas que te mandei (a aba "Como preencher" explica tudo).
> 4. Me mande **3 a 5 mensagens reais** de feedback que você já mandou para atletas.
>    É isso que faz os rascunhos saírem no seu jeito.
> 5. No intervals.icu: Settings → Developer Settings → **API Key**. Me envie essa chave
>    **em mensagem privada** (nunca em grupo).
> 6. Assine o termo de participação (abaixo).

Do seu lado:

```bash
python -m dgendurance importar-atletas planilha-do-marcos.xlsx --treinador marcos-silva
# cole a chave dele em treinadores/marcos-silva/segredos.env
# cole as mensagens dele em treinadores/marcos-silva/estilo_feedback.md
python -m dgendurance testar-conexao --treinador marcos-silva
```

Se ele tiver metodologia diferente da sua, crie `treinadores/marcos-silva/biblioteca/` com os
treinos e semanas dele (copie os seus de `biblioteca/` e adapte). Se não, ele usa os seus.

---

## 3. Sua rotina toda segunda

```bash
python -m dgendurance semana --todos      # você + todos os treinadores do piloto
python -m dgendurance treinadores         # visão geral: atletas e chaves de cada um
```

O comando gera um painel por treinador em `saida/<treinador>/<data>/painel.html`. Mande cada
painel para o respectivo treinador no privado. Os treinos só vão para o calendário dos atletas
quando **o treinador aprovar**:

```bash
python -m dgendurance enviar-treinos --pasta saida/marcos-silva/<data> --confirmar
```

O sistema usa a chave do intervals.icu gravada na pasta do treinador. É impossível enviar
treinos de um treinador com a chave de outro.

---

## 4. O que medir (responda numa planilha toda semana)

| Pergunta para o treinador | Por quê |
|---|---|
| Quanto tempo você gastou com análise e feedback esta semana? E antes do piloto? | **A métrica principal:** tempo economizado |
| Quantas mensagens você mandou sem editar, com pouca edição ou reescrevendo tudo? | Mostra se a IA está no estilo dele |
| Algum alerta foi útil (pegou algo que você não teria visto)? Algum foi bobagem? | Calibra os limites |
| Usou a prescrição como veio, ajustou ou ignorou? | Diz se a biblioteca serve para outros métodos |
| O que mais te irritou esta semana? | Lista de melhorias |

**No fim das 4 semanas:**
1. Se o piloto acabasse hoje, o quanto você sentiria falta? (nada / um pouco / muito)
2. Quanto pagaria por mês? Por atleta ou valor fixo?
3. O que precisa ter para você pagar?
4. Indicaria para outro treinador? Para quem?

**Sinal verde para construir o app:** pelo menos metade dos treinadores diz que sentiria
**muita** falta, economiza 3h ou mais por semana e topa pagar um valor que cubra a IA e o
servidor. Os custos de referência estão no README: cerca de R$ 2 a 3 por atleta por mês de IA,
mais o servidor do app.

---

## 5. Termo de participação no piloto (modelo)

> **Atenção:** é um modelo simples para o piloto gratuito, **não é aconselhamento jurídico**.
> Os dados envolvem saúde (FC, HRV, sono, relatos de dor), que a LGPD trata como dado pessoal
> sensível. Antes de cobrar ou abrir para mais gente, revise com um advogado.

> **Termo de participação: piloto DG Endurance**
>
> Eu, [NOME DO TREINADOR], treinador responsável pela equipe [EQUIPE], participo do piloto
> gratuito do sistema DG Endurance, operado por [SEU NOME], de [DATA] a [DATA].
>
> 1. **Finalidade:** os dados de treino dos meus atletas (atividades, carga, FC, HRV, sono e
>    comentários) serão usados **apenas** para gerar meu painel semanal, rascunhos de feedback
>    e sugestões de treino para mim.
> 2. **Consentimento dos atletas:** declaro que informei meus atletas e obtive a concordância
>    deles para o uso de seus dados neste piloto, incluindo o processamento por serviço de IA
>    (Anthropic) para gerar os rascunhos.
> 3. **Sigilo:** [SEU NOME] não compartilhará os dados com terceiros nem com outros treinadores,
>    e não os usará para outra finalidade.
> 4. **Decisão do treinador:** os rascunhos e sugestões são apoio. Toda mensagem e todo treino
>    enviado aos atletas é revisado e decidido por mim.
> 5. **Encerramento:** ao fim do piloto, ou quando eu pedir, minha chave de acesso e os dados dos
>    meus atletas serão apagados em até 7 dias. Posso revogar a chave a qualquer momento no
>    intervals.icu.
>
> Data: ___ / ___ / ______  Assinatura: ______________________

Para apagar os dados de um treinador:

```bash
rm -rf treinadores/marcos-silva saida/marcos-silva
```

Depois, peça para ele gerar uma nova chave no intervals.icu. Isso invalida a anterior.
