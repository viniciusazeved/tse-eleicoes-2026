# Comparecimento e votação presidencial de 2026

Relatório consolidado dos dois turnos por seção. Fontes oficiais obtidas em 26/10/2026, com preservação dos originais e revisão independente. Projeto independente, identidade neutra. Brasil e exterior são tratados separadamente.

## Resposta à pergunta

Nos dois turnos, os grupos de seções com comparecimento muito alto apresentam maior participação agregada de votos para Lula que o conjunto brasileiro. No segundo turno, Lula tem 51,78% dos válidos no território brasileiro e 67,49% nas seções com abstenção até 5%. O Nordeste reúne 57,43% das seções desse corte. Há, portanto, um padrão descritivo nos grupos extremos e uma concentração territorial que podem ser medidos.

Esse padrão não se traduz em uma relação positiva geral dentro da mesma geografia. A correlação nacional por seção é pequena e o modelo ajustado dentro do mesmo local de votação tem coeficiente negativo nos dois turnos. Esses resultados não identificam votos em nome de ausentes, autoria, causa ou fraude. Também não excluem irregularidade localizada, que exigiria documentação independente.

## Universo e cobertura

A base contém 998.496 registros de seção e turno: 499.248 seções em cada turno, das quais 497.897 no território brasileiro e 1.351 no exterior. A tabela longa preserva 5.731.614 linhas de votação publicadas, incluindo brancos e nulos. Os resultados a seguir usam o Brasil sem exterior, salvo indicação expressa.

Cada linha de seção reúne aptos, comparecimento, abstenção, votos válidos, brancos, nulos e votos por candidatura. Os dados novos foram conciliados com o detalhe contábil dos dois turnos, com todas as seções do primeiro turno anterior e com as 6.292 chaves município/zona oficiais do segundo turno. A camada por zona permanece complementar; os resultados desta versão são efetivamente por seção.

## Seções de baixa abstenção

| Turno | Comparecimento mínimo | Seções | Lula nos válidos | Flávio Bolsonaro nos válidos |
|:--|--:|--:|--:|--:|
| 1º | 90% | 8.299 | 55,63% | 38,04% |
| 1º | 95% | 559 | 61,72% | 31,94% |
| 1º | 98% | 60 | 70,76% | 24,58% |
| 1º | 100% | 15 | 73,53% | 23,43% |
| 2º | 90% | 14.841 | 59,90% | 40,10% |
| 2º | 95% | 639 | 67,49% | 32,51% |
| 2º | 98% | 66 | 81,68% | 18,32% |
| 2º | 100% | 12 | 83,65% | 16,35% |

No conjunto brasileiro do primeiro turno, Lula tem 45,15% dos válidos. Os cortes são inclusivos e cumulativos, portanto não podem ser somados. As taxas da tabela são votos somados divididos pelos válidos somados, não médias simples de percentuais por seção. No primeiro turno há votos de outras candidaturas. Os extremos têm pouco volume: as 12 seções com comparecimento de 100% no segundo turno somam 862 aptos e 844 votos válidos.

## Onde ficam essas seções

Segundo turno, abstenção até 5%, equivalente a comparecimento de pelo menos 95%:

| Região | Seções | % do corte nacional | Lula nos válidos dessas seções | Flávio nos válidos dessas seções |
|:--|--:|--:|--:|--:|
| Norte | 58 | 9,08% | 81,33% | 18,67% |
| Nordeste | 367 | 57,43% | 76,45% | 23,55% |
| Sudeste | 113 | 17,68% | 54,33% | 45,67% |
| Sul | 80 | 12,52% | 29,71% | 70,29% |
| Centro-Oeste | 21 | 3,29% | 62,25% | 37,75% |

A coluna de concentração divide o número de seções da região pelo total de 639 seções do corte. As colunas de votação usam os votos válidos somados dentro do grupo regional. Esses denominadores são diferentes. A tabela não demonstra que a baixa abstenção causou a votação nem compara, sozinha, o grupo extremo com todas as demais seções da mesma região.

No primeiro turno, o Nordeste reúne 294 das 559 seções com abstenção até 5% (52,59%), e Lula tem 69,27% dos válidos nesse grupo regional. No segundo turno, o corte mais restrito, abstenção até 2%, contém 66 seções brasileiras, sendo 47 no Nordeste (71,21% do corte). Todos os cortes e regiões estão em [cortes_regioes.csv](cortes_regioes.csv).

## Associação geral e controles geográficos

A correlação por seção entre comparecimento/aptos e votos de Lula/válidos é:

| Turno | Pearson | Spearman |
|:--|--:|--:|
| 1º | 0,0685 | 0,0647 |
| 2º | 0,0485 | 0,0665 |

Os coeficientes têm magnitude pequena. Para comparar seções dentro da mesma geografia, o modelo ajusta pelo logaritmo do número de aptos e seu quadrado. A tabela usa pesos iguais aos votos válidos e intervalos de 95% com erros agrupados por município. O coeficiente é a mudança associada na fração de votos de Lula, em pontos percentuais, por dez pontos percentuais adicionais de comparecimento.

| Geografia da comparação | 1º turno, pp por 10 pp | IC95% | 2º turno, pp por 10 pp | IC95% |
|:--|--:|:--|--:|:--|
| Nacional, sem efeito fixo geográfico | +1,63 | +0,43 a +2,83 | +1,92 | +0,62 a +3,22 |
| Dentro da mesma UF | -4,75 | -5,33 a -4,18 | -4,34 | -4,97 a -3,70 |
| Dentro do mesmo município | -2,07 | -2,42 a -1,72 | -1,52 | -2,08 a -0,96 |
| Dentro do mesmo local de votação | -0,45 | -0,61 a -0,30 | -0,38 | -0,56 a -0,19 |

O modelo local usa 476.142 seções no primeiro turno e 476.133 no segundo. Locais sem variação de comparecimento não identificam a inclinação. O sinal local permanece negativo com pesos iguais por seção e no recorte de pelo menos 100 aptos. As especificações completas estão em [modelos.csv](modelos.csv).

A inversão entre a associação nacional ajustada e a associação dentro das unidades geográficas evidencia a importância da composição territorial. Os intervalos representam incerteza da especificação do modelo, não erro amostral do censo e não probabilidade de fraude. No segundo turno, as frações dos dois finalistas são complementares; seus resultados não constituem testes independentes.

## Comparação das mesmas seções entre turnos

Todas as 499.248 chaves territoriais encontram correspondência entre os turnos. No Brasil, 55.406 seções mudaram o número de aptos e 431 mudaram o código válido do local; essas contagens podem se sobrepor. O recorte principal contém 442.108 seções brasileiras com aptos e local iguais e denominadores positivos nos dois turnos. No exterior, 992 seções atendem aos mesmos critérios, analisadas separadamente.

Nas 442.108 seções brasileiras do recorte principal, a correlação entre mudança do comparecimento e mudança da participação de Lula nos válidos é 0,1114 (Pearson) e 0,1069 (Spearman). Na amostra de todas as chaves brasileiras elegíveis, Pearson é 0,1091. Essas associações são descritivas, com magnitude pequena.

A média da mudança por seção no recorte principal é de +1,71 pp no comparecimento e +6,41 pp na participação de Lula entre os válidos. A diferença entre razões de totais agregados é outra medida: +1,86 pp e +6,61 pp, respectivamente. As duas medidas não devem ser trocadas entre si. Os resultados dos dois finalistas, do exterior e das duas amostras constam de [pareamento_secoes.csv](pareamento_secoes.csv).

Igualdade de aptos e local não comprova identidade das pessoas que votaram. Ganhos de um finalista incluem possíveis mudanças de preferência, votos dos candidatos eliminados, entrada e saída de comparecentes e mudanças entre válidos, brancos e nulos. Diferenças agregadas não revelam esses fluxos individuais.

## Horários e prorrogação

A [nota oficial de 25/10](https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/esclarecimento-sobre-prorrogacao-da-votacao) informa prorrogação excepcional para seções ainda não encerradas às 17h e retomada da divulgação depois das 19h. Horário de divulgação, encerramento e registro de evento de votação são variáveis diferentes.

Os logs permitem investigar eventos com horário, mas não informam a candidatura escolhida. Não é possível demonstrar que depois das 17h houve somente votos para um candidato cruzando horários com RDV. Um pacote do segundo turno inspecionado também continha histórico do primeiro turno, exigindo filtro da data exata.

Não foi realizado censo nacional dos eventos dos logs. Este relatório não apresenta contagem nacional de votos depois das 17h nem atribuição temporal a candidatos. Semântica, data, fuso, contingências e cobertura precisam ser validados antes dessa extensão. Consulte [HORARIOS.md](../docs/HORARIOS.md).

## Integridade, exceções e rastreabilidade

Os votos do primeiro turno anterior foram preservados. As contas de válidos, brancos e nulos fecham seção a seção nos dois turnos. A tabela longa conserva somente as linhas publicadas; ausências não foram fabricadas como linhas de votação. Na tabela larga, zeros foram admitidos apenas após reconciliação contábil completa.

O detalhe oficial atualizado alterou o código do local de 421 seções do primeiro turno. As diferenças persistem após normalização numérica, portanto não são apenas zeros à esquerda. Isso modifica ligeiramente a composição dos grupos e os coeficientes do modelo local em relação ao relatório inicial, sem alterar os votos. Esta versão usa os metadados de local atualizados nos dois turnos.

Há 41 seções não instaladas no exterior por turno, com 423 aptos e zero comparecimento/abstenção publicados. Além delas, uma seção instalada no primeiro turno e duas no segundo têm comparecimento zero. São 85 registros de seção e turno sem linha nominal. As exceções foram preservadas e não classificadas como irregularidade.

O catálogo do TSE também informa 39 registros de dupla vinculação em transferências temporárias. Esses registros não são os 423 aptos das seções não instaladas. Nenhuma seção foi ajustada por dedução arbitrária. No exterior, a taxa sobre todos os aptos cadastrais pode diferir da taxa sobre o eleitorado instalado.

As versões nominal e contábil foram obtidas com verificação de cache. No detalhe, HEAD chegou a anunciar a versão nova enquanto GET canônico devolveu a anterior. Na coleta nominal, HEAD ainda anunciava a versão antiga, mas o GET parcial com parâmetro de cache identificou a nova. ZIP nominal: SHA256 `c928321f63f2d095706fca73d4607c048d2ada23bda6876455d6911aaf1bc9c1`. ZIP de detalhe: SHA256 `8ef9ce3a85cde260471faf7a83a9b4f5ccf3993fdda942aacaa658574344789c`. URLs, horários, versões e demais hashes constam de [fontes.json](fontes.json) e [QA da integração](qa_integracao_20261026-144303.json).

A revisão independente confrontou fontes, integração, cortes, modelos e pareamento. O [parecer dos dois turnos](../docs/REVISAO_DOIS_TURNOS_SECAO.md) delimita a conferência e documenta diferenças em relação à publicação inicial. As versões antigas permanecem no histórico Git e no arquivo bruto local.

Composição demográfica, mobilização, transporte e características locais continuam sendo possíveis fatores associados. O estudo mede padrões observacionais e não confirma nem exclui voto em nome de ausentes.

## Fontes e reprodução

[Resultados TSE 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026), [documentação técnica](https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados) e [método do estudo](../METODOLOGIA.md).

Os arquivos `resumo.json`, `correlacoes.csv`, `cortes.csv`, `cortes_regioes.csv`, `modelos.csv`, `pareamento_secoes.csv`, `todos_candidatos.csv` e `correlacoes_candidatos.csv` preservam os cálculos desta síntese. Instruções de reprodução e execução do painel estão no [README](../README.md).
