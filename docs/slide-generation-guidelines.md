# Diretrizes de Geracao de Slides LouvorJA

Objetivo: gerar slides que a congregacao consiga cantar sem se perder, com texto
legivel e transicoes perceptiveis para o operador.

## Formato Base

- Cada slide de letra deve ter no maximo 2 linhas principais.
- Usar 1 linha quando o trecho for curto e musicalmente completo.
- Usar 2 linhas quando frases sequenciais cabem juntas e isso evita uma troca
  de slide desnecessaria.
- Nao gerar 3 linhas principais.

Valores iniciais:

```python
target_max_chars_per_line = 28
hard_max_chars_per_line = 34
max_lines_per_slide = 2
min_slide_duration = 4.0
min_transition_gap = 3.0
phrase_pause_seconds = 0.60
```

`target_max_chars_per_line` vem do `sample.slja`: a maior linha observada ali
tem 27 caracteres. `hard_max_chars_per_line` e a tolerancia para evitar uma
troca de slide ruim.

## Quebra de Linha

Preferir quebras:

- depois de pontuacao;
- entre frases musicais;
- depois de uma pausa vocal/musical;
- entre duas ideias completas.

Evitar quebrar:

- no meio de uma expressao;
- entre preposicao e complemento: `de honra`, `em mim`;
- entre artigo/pronome e substantivo: `o noivo`, `Tua presenca`;
- entre negacao/verbo auxiliar e verbo: `nao devemos`, `vai chegar`;
- depois de palavra fraca: `de`, `do`, `da`, `em`, `que`, `e`, `o`, `a`,
  `um`, `uma`, `nao`.

## Quebra de Slide

Um slide nao deve terminar no meio de uma frase musical.

Preferir terminar slide quando houver:

- fim de frase;
- pontuacao;
- pausa perceptivel;
- mudanca de secao;
- fim de uma ideia cantavel.

Evitar criar slide novo se:

- ele ficaria so com uma linha muito curta;
- a transicao aconteceria rapido demais;
- a congregacao provavelmente nao perceberia a troca;
- o operador poderia avancar um slide a mais por engano.

## Tempo Minimo

Usar tempo como criterio, nao so tamanho do texto.

Regras:

- Se dois trechos cabem em 2 linhas, devem ficar juntos.
- Se separar criaria uma troca em menos de `min_transition_gap`, tentar manter
  junto.
- Se manter junto passa um pouco de 28 caracteres, aceitar ate
  `hard_max_chars_per_line`.
- So criar novo slide curto quando houver pausa musical clara.

## Texto Auxiliar

`letra_aux` pode ser usado para texto auxiliar curto ou para marcador de
repeticao `(Nx)`.

Usar `letra_aux` apenas quando:

- for necessario evitar uma troca ruim;
- a informacao for curta;
- o texto principal ja esta no limite de 2 linhas;
- a linha auxiliar nao substitui letra essencial demais ate validarmos a
  aparencia no LouvorJA;
- o planejador detectou `N` slides consecutivos com exatamente as mesmas
  linhas principais e pode substitui-los por um unico slide com `(Nx)`.

Nao usar `letra_aux` para:

- inventar repeticoes que nao foram detectadas nos timestamps;
- esconder letra principal que precisa ser cantada com clareza;
- compactar repeticoes nao consecutivas em outro ponto da musica, porque elas
  precisam do proprio timestamp.

## Repeticoes

Se uma frase se repete e pode permanecer no mesmo slide:

- manter o mesmo slide;
- nao gerar `(Nx)`;
- nao gerar slide duplicado se isso causar troca desnecessaria.

Se a repeticao geraria slides consecutivos identicos:

- colapsar em um unico slide;
- preservar o `start` da primeira ocorrencia;
- preservar o `end` da ultima ocorrencia;
- inserir `letra_aux=(Nx)`, com `N` calculado pela quantidade real de
  ocorrencias consecutivas: `(2x)`, `(3x)`, `(4x)`, `(5x)` etc.

Se a repeticao ocorre em outro ponto da musica, mas nao de forma consecutiva:

- gerar novo slide com timestamp proprio;
- priorizar sincronizacao acima de compactacao.

## Algoritmo Recomendado

1. Agrupar palavras em frases musicais usando pontuacao, pausas entre palavras,
   quebras ja inferidas pelo Titan e timestamps.
2. Para cada grupo candidato, tentar montar 1 linha, 2 linhas balanceadas e
   2 linhas com tolerancia ate 34 caracteres.
3. Pontuar candidatos:
   - penalizar linha longa;
   - penalizar quebra em palavra fraca;
   - penalizar slide curto demais;
   - penalizar troca rapida;
   - bonificar pausa, pontuacao e fim de frase.
4. Escolher o agrupamento com menor penalidade.
5. Colapsar slides consecutivos identicos e contar repeticoes para `(Nx)`.
6. Usar `letra_aux` so como fallback controlado ou marcador `(Nx)`.
7. Nunca criar slides com mais de 2 linhas principais.

## Slides Reais de Validacao

Slides reais enviados pelo usuario podem ser usados como corpus de validacao
local, mas nao devem ser salvos no Git sem pedido explicito.

Use uma pasta ignorada, por exemplo:

```text
local_samples/
```

Os testes versionados devem conter casos sinteticos derivados das regras, nao
copias integrais de arquivos reais enviados para validacao manual.
