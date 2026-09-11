# Consensus Phase Gate Report

Phase: 1
Mode: execute
Gate rule: run the complete set, preserve old-process outputs, and compare phase output against that baseline.

## Summary

- Expected videos: 11
- Discovered videos: 11
- Processed videos: 11
- Complete comparisons: 11
- Full set complete: True
- Baseline hard-limit lines: 23
- Phase hard-limit lines: 0
- Hard-line delta: -23
- Phase gate pass: False

## Gate Checks

- Hard-line gate pass: True
- Slide-count gate pass: True (130 -> 176, raw ratio 1.354, gate ratio 1.135 from 155 comparable baseline slides, allowance 296)
- Line-count gate pass: True (237 -> 338, raw ratio 1.426, gate ratio 1.119 from 302 comparable baseline lines, allowance 664)
- Fast-transition gate pass: True (0 -> 2, phase ratio 1.2%)
- Auxiliary-word gate pass: True (18 -> 0, phase ratio 0.0%)
- Target-line gate pass: False (45 -> 55, phase ratio 16.3%)
- Reference-lyrics gate pass: False (1 reference file(s), min phase similarity 0.7364)

## Gate Failures

- over-target line ratio gate failed: total phase ratio 16.3% is within limit 30.0%; one or more videos may still exceed the per-video limit
- video `SpWZF8jdfCA` over-target line ratio 40.5% exceeds 30.0%
- video `-cFY8RAHkpc` over-target line ratio 30.4% exceeds 30.0%
- reference lyrics gate failed: phase output diverged from one or more expected lyric files
- video `-cFY8RAHkpc` reference lyrics failed: similarity 0.736 below 0.800

## Effort

- Total per-video elapsed: 48m49s
- Average per-video elapsed: 4m26s
- Cache growth: 406.8 MiB
- Phase output size: 71.0 MiB
- Per-source candidate timing is not captured yet; this report measures each video-level phase execution.

## Per Video

| Video | Complete | Elapsed | Baseline hard | Phase hard | Delta hard | Baseline slides | Phase slides | Phase fast | Phase aux | Phase ref sim | Cache delta | Error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `-cFY8RAHkpc` | True | 0m00s | 2 | 0 | -2.0 | 14 | 12 | 0 | 0 | 0.736 | 0 B | - |
| `AlTWVhSsndI` | True | 3m23s | 0 | 0 | 0.0 | 13 | 11 | 0 | 0 | - | 28.4 MiB | - |
| `Ggs2I4OViEY` | True | 4m29s | 0 | 0 | 0.0 | 9 | 9 | 0 | 0 | - | 37.9 MiB | - |
| `J-LrXdce3BQ` | True | 4m23s | 0 | 0 | 0.0 | 15 | 16 | 0 | 0 | - | 37.7 MiB | - |
| `SpWZF8jdfCA` | True | 5m41s | 8 | 0 | -8.0 | 7 | 22 | 1 | 0 | - | 48.5 MiB | - |
| `U4ym16En8xc` | True | 3m25s | 2 | 0 | -2.0 | 13 | 14 | 0 | 0 | - | 28.1 MiB | - |
| `cgNzy67c04E` | True | 3m51s | 0 | 0 | 0.0 | 12 | 12 | 0 | 0 | - | 30.4 MiB | - |
| `iB29MsdK6dE` | True | 5m41s | 2 | 0 | -2.0 | 6 | 16 | 0 | 0 | - | 46.0 MiB | - |
| `mWw_x_B19oo` | True | 5m27s | 3 | 0 | -3.0 | 11 | 31 | 1 | 0 | - | 46.6 MiB | - |
| `pdu52H3o0vk` | True | 5m34s | 2 | 0 | -2.0 | 13 | 13 | 0 | 0 | - | 48.2 MiB | - |
| `txuPSdSn62M` | True | 6m55s | 4 | 0 | -4.0 | 17 | 20 | 0 | 0 | - | 55.1 MiB | - |

## Expected Reference Lyrics By Video (Not Generated)

These lyrics are evaluation-only and were not used to generate any output.

### -cFY8RAHkpc

Title: DVD Adoradores   Deus é Refúgio Congregacional

#### Expected Reference Lyrics (Not Generated)

This text is evaluation-only and was not used to generate the output.

```text
Se estás vivendo em aflição
Se o teu caminho não tem mais luz

E o teu passado te faz sofrer
Lembre: Há um Deus que é solução

Deus traz conforto, Ele traz paz
É o abrigo no temporal

Ele é escudo, é o consolador
Deus é refúgio na provação

Se sentes medo no coração
Se a tristeza te faz chorar

E a tormenta não quer passar
Lembre: Há um Deus que é a solução

Deus traz conforto, Ele traz paz
É o abrigo no temporal

Ele é escudo, é o consolador
Deus é refúgio na provação

Deus traz conforto, Ele traz paz
É o abrigo no temporal

Ele é escudo, é o consolador
Deus é refúgio na provação

Ele é escudo, é o consolador
Deus é refúgio na provação
```


## Output Content By Video

### -cFY8RAHkpc

Title: DVD Adoradores   Deus é Refúgio Congregacional

#### Baseline Best Output

##### Transcription

```text
Seu Teu Caminho Não Tem Mais Luz Não tem mais solução Deus traz conforto, Ele traz paz É o abrigo no temporal Deus tudo é o consolador Deus é recluse na provação Se sentes medo no coração Se a tristeza te faz chorar E a torneita não quer passar Vem, já o Deus, seu solução Deus, o sol, o sol Deus, seu solução Deus traz conforto, Ele traz paz É o abrigo no temporal Deus tudo é o consolador Deus é recluse na provação Deus traz conforto, Ele traz paz É o abrigo no temporal Deus tudo é o consolador Deus é recluse na provação Deus tudo é o consolador Deus é recluse na provação
```

##### Slide Mapping

```text
Seu Teu Caminho
Não Tem Mais Luz

Não tem mais solução

Deus traz conforto,
Ele traz paz

É o abrigo no temporal
Deus tudo é o consolador

Deus é recluse na provação

Se sentes medo no coração
Se a tristeza te faz chorar

E a torneita não quer passar

Vem, já o Deus, seu solução Deus, o sol, o sol
Deus, seu solução Deus traz conforto, Ele traz paz

É o abrigo no temporal
Deus tudo é o consolador

Deus é recluse na provação

Deus traz conforto,
Ele traz paz

É o abrigo no temporal
Deus tudo é o consolador

Deus é recluse na provação
Deus tudo é o consolador

Deus é recluse na provação
```

#### Phase Output

##### Transcription

```text
[Som de sirene] Você está vivendo em africão, se o teu caminho não tem mais luz, teu passado te faz sofrer, lembra o Deus, é solução. Deus traz conforto, Ele traz paz, é o abrigo no temporal, Ele é estudo, é o consolador, Deus é refúgio na provação. Se sentes medo no coração, se a tristeza te faz chorar, e a tormenta não quer passar, lembra o Deus, é solução. Deus traz conforto, Ele traz paz, é o abrigo no temporal, Ele é estudo, é o consolador, Deus é refúgio na provação. [Som de sirene] Deus traz conforto, Ele traz paz, é o abrigo no temporal, Ele é estudo, é o consolador, Deus é refúgio na provação.
```

##### Slide Mapping

```text
[Som de sirene] Você
está vivendo em africão,

se o teu caminho não tem mais luz,
teu passado te faz sofrer,

lembra o Deus, é solução.

Deus traz conforto, Ele traz paz,
é o abrigo no temporal,

Ele é estudo, é o consolador,
Deus é refúgio na provação.

Se sentes medo no coração,
se a tristeza te faz chorar,

e a tormenta não quer passar,
lembra o Deus, é solução.

Deus traz conforto, Ele traz paz,
é o abrigo no temporal,

Ele é estudo, é o consolador,
Deus é refúgio na provação.

[Som de sirene]
Deus traz conforto,

Ele traz paz, é
o abrigo no temporal,

Ele é estudo, é o consolador,
Deus é refúgio na provação.
(2x)
```

### AlTWVhSsndI

Title: Novo Hinário Adventista • Hino 24 • Rei dos Reis • (Lyrics)

#### Baseline Best Output

##### Transcription

```text
Rei dos Reis, Deus cria todo o céu Honra e glória ao Deus infinito em poder Terra e céu, canta e altra de Deus Deus criador, Deus redentor Deus Rei dos Reis Adorai, glorificai o nome de Cristo Exaltai, magnificai Jesus o Senhor Terra e céu, canta e louvou a Deus Ele morreu, Ele venceu, Rei dos Reis Adorai, glorificai o nome de Cristo Exaltai, magnificai Jesus o Senhor Terra e céu, canta e louvou a Deus Ele morreu, Ele venceu, Rei dos Reis
```

##### Slide Mapping

```text
Rei dos Reis,
Deus cria todo o céu

Honra e glória ao
Deus infinito em poder

Terra e céu,
canta e altra de Deus

Deus criador, Deus redentor

Deus Rei dos Reis

Adorai,
glorificai o nome de Cristo

Exaltai,
magnificai Jesus o Senhor

Terra e céu,
canta e louvou a Deus

Ele morreu, Ele venceu,
Rei dos Reis

Adorai,
glorificai o nome de Cristo

Exaltai,
magnificai Jesus o Senhor

Terra e céu,
canta e louvou a Deus

Ele morreu, Ele venceu,
Rei dos Reis
```

#### Phase Output

##### Transcription

```text
Jeitos Neis, Deus criador do céu, honra e glória ao Deus infinito em poder. Terra e céu, canta-i ao Grande Rei, Deus criador, Deus redentor, Deus Rei dos reis. Adorai, glorificai o nome de Cristo, exaltai, magnificai Jesus o Senhor. Terra e céu, canta-i ao Vó, Deus, Ele morreu, Ele venceu, é Rei dos reis. Adorai, glorificai o nome de Cristo, exaltai, magnificai Jesus o Senhor. Terra e céu, canta-i ao Vó, Deus, Ele morreu, Ele venceu, é Rei dos reis.
```

##### Slide Mapping

```text
Jeitos Neis, Deus
criador do céu,

honra e glória ao Deus
infinito em poder.

Terra e céu, canta-i
ao Grande Rei,

Deus criador, Deus redentor,
Deus Rei dos reis.

Adorai, glorificai
o nome de Cristo,

exaltai, magnificai
Jesus o Senhor.

Terra e céu, canta-i ao Vó,
Deus, Ele morreu, Ele venceu,

é Rei dos reis. Adorai,
glorificai o nome de Cristo,

exaltai, magnificai
Jesus o Senhor.

Terra e céu, canta-i ao Vó,
Deus, Ele morreu, Ele

venceu, é Rei dos reis.
```

### Ggs2I4OViEY

Title: 12 - Escuta Meu Clamor - Adoradores

#### Baseline Best Output

##### Transcription

```text
? Eu oro pela Tura ? ? Eu peço por perdão ? ? E por sabedoria ? ? Nas minhas decisões ? ? Que eu possa ter mais coro e al ? ? Ter mais motivos pra novar ? ? Que eu seja o lixo bem no céu ? ? Escuta meu amor ? ? Eu oro por famílias ? ? Que lutam pra vencer ? ? Eu oro para que o pão ? ? Não falte pra ninguém ? ? Que eu possa ter mais coro e al ? ? Ter mais motivos pra novar ? ? Que eu seja o lixo bem no céu ? ? Escuta meu amor ? ? Escuta meu amor ?
```

##### Slide Mapping

```text
? Eu oro pela Tura ?
? Eu peço por perdão ?

? E por sabedoria ? ?
Nas minhas decisões ?

? Que eu possa ter mais coro e al
? ? Ter mais motivos pra novar ?

? Que eu seja o lixo bem
no céu ? ? Escuta meu amor ?

? Eu oro por famílias ?
? Que lutam pra vencer ?

? Eu oro para que o pão ?
? Não falte pra ninguém ?

? Que eu possa ter mais coro e al
? ? Ter mais motivos pra novar ?

? Que eu seja o lixo bem
no céu ? ? Escuta meu amor ?

? Escuta meu amor ?
```

#### Phase Output

##### Transcription

```text
Eu oro pela cura, eu peço por terão e por sabedoria nas minhas decisões que eu possa ter mais fornirão ter mais motivos pra louvar que eu seja um instrumento seu escuta-me, meu amor Eu oro por famílias que lutam pra vencer eu oro para que o pão não falte pra ninguém que eu possa ter mais concluião ter mais motivos pra louvar que eu seja um instrumento seu escuta-me, meu amor escuta-me, meu amor
```

##### Slide Mapping

```text
Eu oro pela cura, eu peço
por terão e por sabedoria

nas minhas decisões que eu
possa ter mais fornirão ter

mais motivos pra louvar
que eu seja um instrumento

seu escuta-me, meu amor Eu
oro por famílias que lutam

pra vencer eu oro para
que o pão não falte pra

ninguém que eu possa ter
mais concluião ter mais

motivos pra louvar que eu
seja um instrumento seu

escuta-me, meu
amor escuta-me,

meu amor
```

### J-LrXdce3BQ

Title: Novo Hinário Adventista • Hino 151 • Amor Glorioso • (Lyrics)

#### Baseline Best Output

##### Transcription

```text
Buscou-me com ternura Jesus, o bom pastor Achou-me na miséria, salvou-me com amor Nos céus, os anjos em canção Mostraram Sua aprovação Oh que amor glorioso, preço tão grandioso Que Jesus por mim na cruz pagou Graças sem igual me rescatou Fenido, abandonado, Jesus me socorreu E secretou-me a gente de agora em diante a Israel Tão bem me avó, jamais ouvi Prazer maior jamais senti Oh que amor glorioso, preço tão grandioso Que Jesus por mim na cruz pagou Graças sem igual me rescatou Enquanto as horas passam, eu vivo em doce paz E aguardo meu bom mestre que tão feliz me faz A mim Jesus virá buscar, e tão com Ele lemorar Oh que amor glorioso, preço tão grandioso Que Jesus por mim na cruz pagou Graças sem igual me rescatou
```

##### Slide Mapping

```text
Buscou-me com ternura Jesus,
o bom pastor

Achou-me na miséria,
salvou-me com amor

Nos céus, os anjos em canção
Mostraram Sua aprovação

Oh que amor glorioso,
preço tão grandioso

Que Jesus por mim na cruz pagou
Graças sem igual me rescatou

Fenido, abandonado,
Jesus me socorreu

E secretou-me a gente
de agora em diante a Israel

Tão bem me avó, jamais ouvi
Prazer maior jamais senti

Oh que amor glorioso,
preço tão grandioso

Que Jesus por mim na cruz pagou
Graças sem igual me rescatou

Enquanto as horas passam,
eu vivo em doce paz

E aguardo meu bom mestre
que tão feliz me faz

A mim Jesus virá buscar,
e tão com Ele lemorar

Oh que amor glorioso,
preço tão grandioso

Que Jesus por mim na cruz pagou
Graças sem igual me rescatou
```

#### Phase Output

##### Transcription

```text
Abertura Buscou-me com ternura Jesus, o bom pastor Achou-me na miséria, salvou-me com amor Nos céus, anjos em canção Mostraram sua aprovação Ó que amor glorioso, preço tão grandioso Que Jesus por mim na cruz pagou Graça sem igual me resgatou Ferido, abandonado, Jesus me socorreu E segredou-me a gente, de agora em diante és meu Tão meiga voz jamais ouvi, prazer maior jamais senti Ó que amor glorioso, preço tão grandioso Que Jesus por mim na cruz pagou Graça sem igual me resgatou Enquanto as horas passam, eu vivo em doce paz E aguardo o meu bom mestre, que tão feliz me faz A mim Jesus virá buscar, então com ele irei morar Ó que amor glorioso, preço tão grandioso Que Jesus por mim na cruz pagou Graça sem igual me resgatou E aí
```

##### Slide Mapping

```text
Abertura Buscou-me
com ternura Jesus,

o bom pastor Achou-me na miséria,
salvou-me com amor Nos céus,

anjos em canção Mostraram sua
aprovação Ó que amor glorioso,

preço tão grandioso
Que Jesus por mim na cruz

pagou Graça sem igual
me resgatou Ferido,

abandonado, Jesus me socorreu
E segredou-me a gente,

de agora em diante és meu
Tão meiga voz jamais ouvi,

prazer maior jamais senti
Ó que amor glorioso,

preço tão grandioso
Que Jesus por mim na cruz

pagou Graça sem igual me resgatou
Enquanto as horas passam,

eu vivo em doce paz
E aguardo o meu bom mestre,

que tão feliz me faz
A mim Jesus virá buscar,

então com ele irei morar
Ó que amor glorioso,

preço tão grandioso
Que Jesus por mim na cruz

pagou Graça sem
igual me resgatou

E aí
```

### SpWZF8jdfCA

Title: FIEL A TODA PROVA ｜ CD JOVEM ｜ MENOS UM

#### Baseline Best Output

##### Transcription

```text
Paro pra pensar Nos desafios deste meu viver Paro pra ouvir O que a voz de Deus quer me dizer São tantas as pressões E tenho que enfrentar Mas bem acima delas Sei que está meu Pai Quero ser fiel a toda prova Fiel em qualquer tempo, qualquer hora Quero ser fiel no que é pouco Para ser fiel no que é muito Quero ser fiel a toda prova Não por uma mera obrigação Mas em resposta ao amor tão grande Que um dia iludou O meu coração Posso triunfar Conheço alguém que já venceu por mim Posso me apegar A forte mão de um Deus tão grande assim Em meio à provação Começo a louvar Em seu poder do alto Vem me alcançar Quero ser fiel a toda prova Fiel em qualquer tempo, qualquer hora Quero ser fiel no que é pouco Para ser fiel no que é muito Quero ser fiel no que é muito Quero ser fiel no que é muito Quero ser fiel a toda prova Não por uma mera obrigação Mas em resposta ao amor tão grande Que um dia iludou O meu coração Deus poderoso Deus poderoso Pai tão grandioso Envie em meu auxílio Seu anjo mais poderoso Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova
```

##### Slide Mapping

```text
Paro pra pensar

Nos desafios deste meu viver Paro pra ouvir O que
a voz de Deus quer me dizer São tantas as pressões

E tenho que enfrentar Mas bem acima delas Sei que está meu Pai Quero ser fiel a toda prova Fiel em qualquer tempo, qualquer hora Quero ser fiel no que é pouco Para
ser fiel no que é muito Quero ser fiel a toda prova Não por uma mera obrigação Mas em resposta ao amor tão grande Que um dia iludou O meu coração Posso triunfar

Conheço alguém que já venceu por mim Posso me apegar A forte mão de um Deus tão grande assim Em meio à provação Começo a louvar Em seu poder do alto Vem me alcançar Quero ser fiel a toda prova Fiel em qualquer tempo, qualquer hora Quero ser
fiel no que é pouco Para ser fiel no que é muito Quero ser fiel no que é muito Quero ser fiel no que é muito Quero ser fiel a toda prova Não por uma mera obrigação Mas em resposta ao amor tão grande Que um dia iludou O meu coração Deus poderoso

Deus poderoso Pai tão grandioso Envie em meu auxílio Seu anjo mais poderoso Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero
ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova Quero ser fiel a toda prova

Quero ser fiel a toda prova
Quero ser fiel a toda prova
(11x)

Quero ser fiel a toda prova
```

#### Phase Output

##### Transcription

```text
Paro pra pensar nos desafios deste meu viver Paro pra ouvir o que a voz de Deus quer me dizer São tantas expressões que tenho que enfrentar Mas bem acima delas sei que está meu Pai Quero ser fiel a toda prova Fiel em qualquer tempo, qualquer hora Quero ser fiel no que é pouco Mara ser fiel no que é muito Quero ser fiel a toda prova Não por uma mera obrigação Mas em resposta ao amor tão grande Que um dia inundou o meu coração Posso triunfar Conheço alguém que já venceu por mim Posso me apegar A forte mão de um Deus tão grande assim Em meio à provação Começo a louvar Que seu poder do alto Tem me alcançar Quero ser fiel a toda prova Fiel em qualquer tempo, qualquer hora Quero ser fiel no que é pouco Mara ser fiel no que é muito Quero ser fiel a toda prova Não por uma mera obrigação Mas em resposta ao amor tão grande Que um dia inundou o meu coração Deus poderoso Pai tão grandioso Enfie em meu alcinho Seu anjo mais poderoso Quero ser fiel a toda prova Não por uma mera obrigação Mas em resposta ao amor tão grande Ao amor tão grande Ao amor tão grande Que um dia inundou o meu coração Que um dia inundou o meu coração
```

##### Slide Mapping

```text
Paro pra pensar nos desafios
deste meu viver Paro pra

ouvir o que a voz de Deus
quer me dizer São tantas

expressões que tenho
que enfrentar

Mas bem acima delas sei
que está meu Pai Quero ser

fiel a toda prova Fiel
em qualquer tempo,

qualquer hora Quero ser fiel no
que é pouco Mara ser fiel no que é

muito Quero ser fiel a toda prova
Não por uma mera obrigação Mas

em resposta ao amor tão grande
Que um dia inundou o meu coração

Posso triunfar Conheço alguém que
já venceu por mim Posso me apegar

A forte mão de um Deus tão grande
assim Em meio à provação Começo

a louvar

Que seu poder do alto Tem
me alcançar Quero ser fiel

a toda prova Fiel
em qualquer tempo,

qualquer hora Quero ser fiel no
que é pouco Mara ser fiel no que é

muito Quero ser fiel a toda prova
Não por uma mera obrigação Mas

em resposta ao amor tão grande
Que um dia inundou o meu coração

Deus poderoso Pai tão
grandioso Enfie em meu

alcinho Seu anjo mais poderoso
Quero ser fiel a toda prova

Não por uma mera obrigação
Mas em resposta ao amor tão

grande Ao amor tão grande Ao
amor tão grande Que um dia

inundou o meu coração

Que um dia inundou
o meu coração
```

### U4ym16En8xc

Title: Novo Hinário Adventista • Hino 441 • Vencendo Vem Jesus • (Lyrics)

#### Baseline Best Output

##### Transcription

```text
Música A sua vinda mais se mostra cada vez Vencendo vem Jesus Glória, glória, aleluia Glória, glória, aleluia Glória, glória, aleluia Vencendo vem Jesus O clarim que chama os frentes A batalha já soou Cristo à frente do seu povo Um monte e dois já conquistou O inimigo e a gente ameceu O mal manifestou Vencendo vem Jesus Glória, glória, aleluia Glória, glória, aleluia Vencendo vem Jesus E por fim, entronizado As nações a deslumar Todos grandes e pequenos O juizão de encarar E os remidos triunfantes É o amor de cantar Vencido vem Jesus Glória, glória, glória, aleluia Glória, glória, aleluia Glória, glória, aleluia Glória, glória, aleluia Vencido vem Jesus Jesus Jesus Jesus
```

##### Slide Mapping

```text
Música

A sua vinda mais se mostra
cada vez Vencendo vem Jesus
Glória, glória, aleluia

Glória, glória, aleluia

Glória, glória, aleluia Vencendo vem Jesus O clarim que chama os frentes A batalha já soou Cristo à frente do seu povo
Um monte e dois já conquistou O inimigo e a gente ameceu O mal manifestou Vencendo vem Jesus Glória, glória, aleluia

Glória, glória, aleluia
(2x)

Vencendo vem Jesus
E por fim, entronizado

As nações a deslumar
Todos grandes e pequenos

O juizão de encarar
E os remidos triunfantes

É o amor de cantar
Vencido vem Jesus

Glória, glória, glória, aleluia
Glória, glória, aleluia

Glória, glória, aleluia
Glória, glória, aleluia

Vencido vem Jesus
Jesus

Jesus Jesus
```

#### Phase Output

##### Transcription

```text
Já refúja glória eterna de Jesus, o Rei dos Vens Prévios reinos deste mundo ouvirão as suas leis Os sinais da sua vinda a paz se mostram cada vez Vencendo vem Jesus Glória, glória, Alemúria Vencendo vem Jesus O Carim que chama aos frentes, a batalha já soou Cristo à frente do seu povo, um monte e dois já conquistou O inimigo imediato é seu, o amor que casnou Vencendo vem Jesus Glória, glória, Alemúria Glória, glória, Alemúria Vencendo vem Jesus E por fim, entronizado, as nações a desjugar Todos grandes e pequenos os juizam de encarar E os remilhos triunfantes em coragem cantar Vencendo vem Jesus Glória, glória, Alemúria Vencido vem Jesus
```

##### Slide Mapping

```text
Já refúja glória
eterna de Jesus,

o Rei dos Vens Prévios
reinos deste mundo ouvirão

as suas leis Os sinais da sua
vinda a paz se mostram cada vez

Vencendo vem Jesus Glória,

glória, Alemúria Vencendo
vem Jesus O Carim que chama

aos frentes, a batalha já soou
Cristo à frente do seu povo,

um monte e dois já conquistou
O inimigo imediato é seu,

o amor que casnou
Vencendo vem Jesus Glória,

glória, Alemúria
Glória, glória,

Alemúria Vencendo
vem Jesus E por fim,

entronizado, as nações
a desjugar Todos grandes e

pequenos os juizam
de encarar E os remilhos

triunfantes em coragem
cantar Vencendo vem Jesus

Glória, glória, Alemúria
Vencido vem Jesus
```

### cgNzy67c04E

Title: Novo Hinário Adventista • Hino 273 • A Escola Sabatina • (Lyrics)

#### Baseline Best Output

##### Transcription

```text
Em Teu nome começamos esta escola, oh Senhor. Convergô-nos, te obamos, sejas o nosso diretor. Cada sábado nós vimos a Tua escola, oh Jesus. Venha, oh mestre, insuí-nos, no caminho perdimos. Desta escola nos ensina em Tua santa lei viver. E nos manda que sejamos sempre fiéis até morrer. Cada sábado nós vimos a Tua escola, oh Jesus. Venha, oh mestre, insuí-nos, no caminho Teu de luz. Vencem, oh venha, ensiná-nos, Teus preceitos bem cumpri. Desde o oído esperamos da presença que senti. Cada sábado nós vimos a Tua escola, oh Jesus. Venha, oh mestre, insuí-nos, no caminho Teu de luz.
```

##### Slide Mapping

```text
Em Teu nome começamos esta escola,
oh Senhor.

Convergô-nos, te obamos,
sejas o nosso diretor.

Cada sábado nós vimos
a Tua escola, oh Jesus.

Venha, oh mestre, insuí-nos,
no caminho perdimos.

Desta escola nos ensina
em Tua santa lei viver.

E nos manda que sejamos
sempre fiéis até morrer.

Cada sábado nós vimos
a Tua escola, oh Jesus.

Venha, oh mestre, insuí-nos,
no caminho Teu de luz.

Vencem, oh venha, ensiná-nos,
Teus preceitos bem cumpri.

Desde o oído esperamos
da presença que senti.

Cada sábado nós vimos
a Tua escola, oh Jesus.

Venha, oh mestre, insuí-nos,
no caminho Teu de luz.
```

#### Phase Output

##### Transcription

```text
Em Teu nome começamos esta escola, ó Senhor. Com fervor nós Te rogamos, sejas o nosso diretor. Cada sábado nós vimos a Tua escola, ó Jesus. Venha, ó Mestre, e instruí-nos no caminho Teu de luz. Desta escola nos ensina em Tua santa lei viver. E nos manda que sejamos sempre fiéis até morrer. Cada sábado nós vimos a Tua escola, ó Jesus. Venha, ó Mestre, e instruí-nos no caminho Teu de luz. Venha, Senhor, venha ensinar-nos Teus preceitos bem cumprir. Teus hermídos, esperamos Tua presença que sentir. Cada sábado nós vimos a Tua escola, ó Jesus. Venha, ó Mestre, e instruí-nos no caminho Teu de luz.
```

##### Slide Mapping

```text
Em Teu nome começamos esta escola,
ó Senhor.

Com fervor nós Te rogamos,
sejas o nosso diretor.

Cada sábado nós vimos
a Tua escola, ó Jesus.

Venha, ó Mestre, e instruí-nos
no caminho Teu de luz.

Desta escola nos ensina
em Tua santa lei viver.

E nos manda que sejamos
sempre fiéis até morrer.

Cada sábado nós vimos
a Tua escola, ó Jesus.

Venha, ó Mestre, e instruí-nos
no caminho Teu de luz.

Venha, Senhor, venha ensinar-nos
Teus preceitos bem cumprir.

Teus hermídos, esperamos
Tua presença que sentir.

Cada sábado nós vimos
a Tua escola, ó Jesus.

Venha, ó Mestre, e instruí-nos
no caminho Teu de luz.
```

### iB29MsdK6dE

Title: ADORÁ-LO  - ADORADORES 2

#### Baseline Best Output

##### Transcription

```text
A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL A CIDADE NO BRASIL
```

##### Slide Mapping

```text
A CIDADE NO BRASIL
(3x)

A CIDADE NO BRASIL A CIDADE NO BRASIL
A CIDADE NO BRASIL A CIDADE NO BRASIL

A CIDADE NO BRASIL
(9x)

A CIDADE NO BRASIL
A CIDADE NO BRASIL

A CIDADE NO BRASIL
(4x)

A CIDADE NO BRASIL
A CIDADE NO BRASIL
(11x)
```

#### Phase Output

##### Transcription

```text
Apenas uma vez que você está com a minha ajuda, você vai se sentir mais feliz. Você vai se sentir mais feliz. Você vai se sentir mais feliz. Você vai se sentir mais feliz. Você vai se sentir mais feliz. Você vai se sentir mais feliz. Em Teus átrios, Senhor, Eu Te exaltarei. Aleluia, Aleluia, Aleluia, Aleluia, Andorado eu vou, oh Deus de Israel, Majestoso Tu és, na Terra e no Céu, Eu constrado estarei, o estrado dos Teus pés, Em Teus átrios, Senhor, Eu Te exaltarei. Aleluia, Aleluia, Aleluia, Aleluia, Andorado eu vou, oh Deus de Israel, Majestoso Tu és, na Terra e no Céu, Eu constrado estarei, o estrado dos Teus pés, Em Teus átrios, Senhor, Eu Te exaltarei.
```

##### Slide Mapping

```text
Apenas uma vez que você
está com a minha ajuda,

você vai se sentir mais feliz.
Você vai se sentir mais feliz.

Você vai se
sentir mais feliz.
(5x)

Você vai se sentir mais feliz.
Você vai se sentir mais feliz.

Você vai se
sentir mais feliz.
(5x)

Em Teus átrios, Senhor,
Eu Te exaltarei.

Aleluia, Aleluia,
Aleluia, Aleluia,
(2x)

Andorado eu vou,
oh Deus de Israel,

Majestoso Tu és,
na Terra e no Céu,

Eu constrado estarei,
o estrado dos Teus pés,

Em Teus átrios, Senhor,
Eu Te exaltarei.

Aleluia, Aleluia,
Aleluia, Aleluia,
(2x)

Andorado eu vou, oh Deus
de Israel, Majestoso Tu és,

na Terra e no Céu,
Eu constrado estarei,

o estrado dos Teus pés,
Em Teus átrios, Senhor, Eu

Te exaltarei.
```

### mWw_x_B19oo

Title: ADORADORES 4 - MEU PASTOR ｜ @WeslleyFonseca e @MelissaBarcelosoficial

#### Baseline Best Output

##### Transcription

```text
Então, ele disse que nesse mundo teríamos problemas e aflições, mas ele prometeu que estaria sempre do nosso lado. Vamos cantar juntos? O Liceu Andar! O Passor Levas As Ovelhas Em Segurança! Vamos cantar sobre isso novamente? O Liceu Andar! O Passor Levas As Ovelhas Em Segurança! E em pastos verdes vou descansar de a jornada ótima O meu pastor me leva a lugarizado de água limpa pra beber E em pastos verdes vou descansar de a jornada ótima Declare! Com Ele! Com Ele! O Liceu Andar!
```

##### Slide Mapping

```text
Então, ele disse que nesse mundo teríamos problemas e aflições, mas
ele prometeu que estaria sempre do nosso lado. Vamos cantar juntos?

O Liceu Andar!

O Passor Levas As Ovelhas Em Segurança!
Vamos cantar sobre isso novamente?

O Liceu Andar!
(2x)

O Passor Levas
As Ovelhas Em Segurança!

E em pastos verdes vou
descansar de a jornada ótima

O meu pastor me leva a lugarizado
de água limpa pra beber

E em pastos verdes vou
descansar de a jornada ótima

Declare!
Com Ele!

Com Ele!

O Liceu Andar!
```

#### Phase Output

##### Transcription

```text
Então, ele disse que nesse mundo teríamos problemas e aflições, mas ele prometeu que estaria sempre do nosso lado. Vamos cantar juntos? Contigo eu andei em segurança De mim afastas todo o mal Eu sou ovelha que precisa Do cuidado do pastor E se eu andar? E se eu andar pelo vale da sombra da morte Pelo vale da sombra da morte Eu mal algo temerei Pois sei que onde quer que eu for Tua bondade me seguirá Onde for tua bondade me seguirá Se desvenção me secarás Meu pastor me leva a lugares altos De água limpa pra beber E em pastos verdes vou descansar Que a jornada continua com ele O pastor leva as ovelhas em segurança Vamos cantar sobre isso novamente? Contigo eu ando em segurança De mim afastas todo o mal Eu sou ovelha que precisa Do cuidado do pastor E se eu andar? E se eu andar pelo vale da sombra da morte Pelo vale da sombra da morte Eu mal algo temerei Pois sei que onde quer que eu for Tua bondade me seguirá Onde for tua bondade me seguirá Se desvenção me secarás Meu pastor me leva a lugares altos De água limpa pra beber E em pastos verdes vou descansar Que a jornada continua E se eu andar? E se eu andar pelo vale da sombra da morte Pelo vale da sombra da morte Eu mal algo temerei Pois sei que onde quer que eu for Tua bondade me seguirá Onde for tua bondade me seguirá Se desvenção me secarás Meu pastor me leva a lugares altos De água limpa pra beber E em pastos verdes vou descansar Que a jornada continua Meu pastor me leva a lugares altos De água limpa pra beber De água limpa pra beber E em pastos verdes vou descansar Que a jornada continua Com ele Com ele
```

##### Slide Mapping

```text
Então, ele disse que nesse mundo
teríamos problemas e aflições,

mas ele prometeu que estaria
sempre do nosso lado.

Vamos cantar juntos?

Contigo eu andei
em segurança De mim afastas

todo o mal Eu sou ovelha
que precisa Do cuidado

do pastor E se eu andar?

E se eu andar pelo vale
da sombra da morte Pelo vale

da sombra da morte Eu mal
algo temerei Pois sei que

onde quer que eu for Tua
bondade me seguirá Onde for

tua bondade me seguirá Se
desvenção me secarás Meu

pastor me leva a lugares
altos De água limpa pra

beber E em pastos verdes
vou descansar Que a jornada

continua com ele O pastor
leva as ovelhas em segurança

Vamos cantar sobre
isso novamente?

Contigo eu ando em segurança
De mim afastas todo o mal Eu

sou ovelha que precisa Do cuidado
do pastor E se eu andar?

E se eu andar pelo vale da sombra
da morte Pelo vale da sombra da

morte Eu mal algo temerei
Pois sei que onde quer que

eu for Tua bondade me
seguirá Onde for tua bondade

me seguirá Se desvenção me
secarás Meu pastor me leva

a lugares altos De água
limpa pra beber E em pastos

verdes vou descansar Que a jornada
continua E se eu andar?

E se eu andar pelo vale
da sombra da morte Pelo vale

da sombra da morte Eu mal
algo temerei Pois sei que

onde quer que eu for Tua
bondade me seguirá Onde for

tua bondade me seguirá Se
desvenção me secarás Meu pastor me

leva a lugares altos De água
limpa pra beber E em pastos

verdes vou descansar
Que a jornada continua Meu

pastor me leva a lugares altos De
água limpa pra beber De água limpa

pra beber E em pastos verdes
vou descansar Que a jornada

continua Com ele Com ele
```

### pdu52H3o0vk

Title: ADORADORES 3 - MEDLEY (AO VIVO EM RECIFE)

#### Baseline Best Output

##### Transcription

```text
Agora chegou a hora de nós cantarmos alguns trechos de hinos clássicos. Eles fazem tão bem ao nosso coração. O Salvador confiante sou em teu amor. O Salvador, lhe achei guante. Mais perto quero estar, meu Deus, é Ti. Linda que seja a dor que me una a Ti. Deus meu constante orar, mais perto quero estar. Meu Deus, é Ti. Sim, quero a Cristo, vem junto estar. Ter la malen, consegui la portar. Hola eterno, lar de esplendor. La estarei junto ao meu Salvador. La cantarei todo o Seu grande amor. Amém.
```

##### Slide Mapping

```text
Agora chegou a hora de nós cantarmos alguns trechos
de hinos clássicos. Eles fazem tão bem ao nosso coração.

O Salvador confiante
sou em teu amor.

O Salvador,
lhe achei guante.

Mais perto quero estar,
meu Deus, é Ti.

Linda que seja a dor
que me una a Ti.

Deus meu constante orar,
mais perto quero estar.

Meu Deus, é Ti.

Sim, quero a Cristo,
vem junto estar.

Ter la malen,
consegui la portar.

Hola eterno,
lar de esplendor.

La estarei junto
ao meu Salvador.

La cantarei todo
o Seu grande amor.

Amém.
```

#### Phase Output

##### Transcription

```text
Agora chegou a hora de nós cantarmos alguns trechos de inos clássicos. Eles fazem tão bem ao nosso coração. O Salvador, confiante sou em teu amor. O Salvador, me a chegou a ti. Mais perto quero estar, meu Deus, é Ti. E ainda que seja dor, que me una a Ti. Tens meu constante orar, mais perto quero estar. Meu Deus, é Ti. Sim, quero a Cristo bem junto estar. Ter la malen, conseguir aportar. Olá, eterno, lar de esplendor. Lá estarei, junto ao meu Salvador. Lá cantarei todo o Seu grande amor. Amém.
```

##### Slide Mapping

```text
Agora chegou a hora de nós
cantarmos alguns trechos de

inos clássicos. Eles fazem
tão bem ao nosso coração.

O Salvador, confiante
sou em teu amor.

O Salvador, me
a chegou a ti.

Mais perto quero
estar, meu Deus,

é Ti. E ainda que seja dor,
que me una a Ti.

Tens meu constante orar,
mais perto quero estar.

Meu Deus, é Ti.

Sim, quero a Cristo
bem junto estar.

Ter la malen,
conseguir aportar.

Olá, eterno, lar
de esplendor.

Lá estarei, junto
ao meu Salvador.

Lá cantarei todo o Seu
grande amor. Amém.
```

### txuPSdSn62M

Title: ADORADORES 5 - USA-ME (LETRA)

#### Baseline Best Output

##### Transcription

```text
? Eu entrego em Tuas mãos as conquistas ? ? Eu entrego em Tuas mãos os fracassos ? ? Eu entrego em Tuas mãos os meus sonhos ? ? Me entrego em Tuas mãos por inteiro ? ? Pusa-me ? ? Pra Tua glória ? ? Faz em mim ? ? Tua obra ? ? Pois minha vida é tudo que tenho ? ? Me entrego em Tuas mãos por inteiro ? ? Eu entrego em Tuas mãos o meu choro ? ? Eu entrego em Tuas mãos o meu riso ? ? Eu entrego em Tuas mãos minha caçal ? ? Me entrego em Tuas mãos por inteiro ? ? Pusa-me ? ? Pra Tua glória ? ? Faz em mim ? ? Tua obra ? ? Pois minha vida é tudo que tenho ? ? Me entrego em Tuas mãos por inteiro ? ? Sobra em mim Espírito Santo ? ? Trazendo o frescor da Tua glória ? ? E convencendo a ser instrumento ? ? Pra Te honrar ? ? Pra Te honrar ? ? Sobra em mim Espírito Santo ? ? Trazendo o frescor da Tua glória ? ? E convencendo a ser instrumento ? ? Pra Te honrar ? ? Pra Te honrar ? ? Pusa-me ? ? Pra Tua glória ? ? Faz em mim ? ? Faz em mim ? ? Tua obra ? ? Pois minha vida é tudo que tenho ? ? Me entrego em Tuas mãos por inteiro ? ? Pois minha vida é tudo que tenho ? ? Me entrego em Tuas mãos por inteiro ?
```

##### Slide Mapping

```text
? Eu entrego em Tuas mãos as conquistas ?
? Eu entrego em Tuas mãos os fracassos ?

? Eu entrego em Tuas mãos os meus
sonhos ? ? Me entrego em Tuas mãos
por inteiro ?

? Pusa-me ? ?
Pra Tua glória ?

? Faz em mim ? ? Tua obra ? ?
Pois minha vida é tudo que tenho ?

? Me entrego em Tuas
mãos por inteiro ?

? Eu entrego em Tuas mãos o meu choro ? ? Eu entrego em Tuas mãos o meu riso ?
? Eu entrego em Tuas mãos minha caçal ? ? Me entrego em Tuas mãos por inteiro ?

? Pusa-me ? ?
Pra Tua glória ?

? Faz em mim ? ? Tua obra ? ?
Pois minha vida é tudo que tenho ?

? Me entrego em Tuas mãos
por inteiro ? ? Sobra em mim
Espírito Santo ?

? Trazendo o frescor da Tua
glória ? ? E convencendo a
ser instrumento ?

? Pra Te honrar ? ? Pra Te honrar
? ? Sobra em mim Espírito Santo ?

? Trazendo o frescor da Tua
glória ? ? E convencendo a
ser instrumento ?

? Pra Te honrar ? ? Pra
Te honrar ? ? Pusa-me ?

? Pra Tua glória ? ? Faz
em mim ? ? Faz em mim ?

? Tua obra ? ? Pois minha
vida é tudo que tenho ?

? Me entrego em Tuas mãos por
inteiro ? ? Pois minha vida é tudo
que tenho ?

? Me entrego em Tuas
mãos por inteiro ?
```

#### Phase Output

##### Transcription

```text
Eu entrego em tuas mãos as com que estás Eu entrego em tuas mãos os fracassos Eu entrego em tuas mãos os meus sonhos Me entrego em tuas mãos por inteiros Usa-me pra tua glória Faz em mim tua obra Pois minha vida é tudo que tenho Me entrego em tuas mãos por inteiro Eu entrego em tuas mãos o meu choro Eu entrego em tuas mãos o meu riso Eu entrego em tuas mãos minha casa Me entrego em tuas mãos por inteiro Usa-me pra tua glória Faz em mim tua obra Pois minha vida é tudo que tenho Me entrego em tuas mãos por inteiro Só pra em mim, Espírito Santo, trazendo o frescor da tua glória Me convencendo a ser instrumento pra te honrar, pra te honrar Só pra em mim, Espírito Santo, trazendo o frescor da tua glória Me convencendo a ser instrumento pra te honrar, pra te honrar Pra tua glória Faz em mim tua obra Pois minha vida é tudo que tenho Me entrego em tuas mãos por inteiro Pois minha vida é tudo que tenho Me entrego em tuas mãos por inteiro Só pra em mim, Espírito Santo, trazendo o frescor da tua glória
```

##### Slide Mapping

```text
Eu entrego em tuas mãos
as com que estás Eu entrego

em tuas mãos os fracassos Eu
entrego em tuas mãos os meus

sonhos Me entrego em tuas
mãos por inteiros Usa-me pra

tua glória Faz em mim tua
obra Pois minha vida é tudo

que tenho Me entrego
em tuas mãos por inteiro

Eu entrego em tuas mãos
o meu choro Eu entrego

em tuas mãos o meu riso Eu
entrego em tuas mãos minha

casa Me entrego em tuas mãos
por inteiro Usa-me pra tua

glória Faz em mim tua obra
Pois minha vida é tudo

que tenho Me entrego em tuas
mãos por inteiro Só pra em mim,

Espírito Santo, trazendo
o frescor da tua glória Me

convencendo a ser
instrumento pra te honrar,

pra te honrar Só pra em mim,

Espírito Santo, trazendo
o frescor da tua glória Me

convencendo a ser
instrumento pra te honrar,

pra te honrar Pra tua glória
Faz em mim tua obra Pois

minha vida é tudo que tenho
Me entrego em tuas mãos por

inteiro Pois minha vida é
tudo que tenho Me entrego

em tuas mãos por inteiro

Só pra em mim, Espírito Santo,
trazendo o frescor da tua glória
```


## Artifact Layout

- `baseline-old-process/<video_id>/`: copied old-process `.slja` candidates and `best.slja`.
- `phase-output/<video_id>/best-consensus.slja`: phase output for that video.
- `phase-output/<video_id>/consensus-report.md`: phrase-level source decisions and low-confidence snippets.
- `phase-output/<video_id>/comparison.json` and `.md`: detailed metric comparison.
