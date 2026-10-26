# Revisão independente de geografia e abstenção

Atualizado em 26/10/2026 08:11:51 -0300. Revisor: agente independente Astra.

Escopo estritamente territorial: primeiro turno de 2026, Presidente, território brasileiro, aptos positivos. Foram lidas apenas as colunas de ano, cargo, turno, UF, município, zona, seção, aptos, comparecimento e abstenção. Não foram lidos ou analisados campos de candidatura nesta revisão.

## Fonte e verificação independente

A fonte foi o membro `detalhe_votacao_secao_2026_BR.csv` do ZIP bruto `data/raw/detalhe_votacao_secao_2026.zip`, SHA256 `11a62c3a604e8b73fc328617b7688d2c635de1c76df02ba63b8f77879512f573`. O ZIP foi relido diretamente, sem importar ou executar o script do principal. Filtros: `ANO_ELEICAO=2026`, `CD_CARGO=1`, `NR_TURNO=1`, UF diferente de ZZ e aptos maiores que zero.

O universo filtrado contém 497.897 seções e 27 UFs. A chave UF, município TSE, zona e seção é única. Comparecimento mais abstenção equivale a aptos em todas as 497.897 seções. Não há abstenção negativa nesse universo. As 27 UFs foram associadas às cinco regiões IBGE, sem UF ausente ou sem classificação.

Os cortes são inclusivos. Para evitar arredondamento, a conferência independente utilizou abstenção multiplicada por 10, 20 ou 50 menor ou igual a aptos, respectivamente para 10%, 5% e 2%; o corte zero exige abstenção igual a zero. Os cortes são cumulativos e não devem ser somados.

## Denominadores

Percentual no corte nacional: número de seções da região que satisfazem o corte dividido pelo número nacional de seções que satisfazem o mesmo corte. Percentual das seções regionais: número de seções da região que satisfazem o corte dividido pelo total de seções da região. Ambos os denominadores contam seções, sem ponderação pelo eleitorado.

## Resultados conferidos

| Abstenção máxima | Região | Seções no corte | Total regional | % do corte nacional | % das seções regionais |
| :-- | :-- | --: | --: | --: | --: |
| 10% | Norte | 1.209 | 43.769 | 14,5680% | 2,76223% |
| 10% | Nordeste | 5.038 | 140.828 | 60,7061% | 3,57741% |
| 10% | Centro-Oeste | 160 | 38.048 | 1,9279% | 0,42052% |
| 10% | Sudeste | 833 | 203.237 | 10,0374% | 0,40987% |
| 10% | Sul | 1.059 | 72.015 | 12,7606% | 1,47053% |
| 5% | Norte | 124 | 43.769 | 22,1825% | 0,28331% |
| 5% | Nordeste | 294 | 140.828 | 52,5939% | 0,20877% |
| 5% | Centro-Oeste | 16 | 38.048 | 2,8623% | 0,04205% |
| 5% | Sudeste | 78 | 203.237 | 13,9535% | 0,03838% |
| 5% | Sul | 47 | 72.015 | 8,4079% | 0,06526% |
| 2% | Norte | 14 | 43.769 | 23,3333% | 0,03199% |
| 2% | Nordeste | 33 | 140.828 | 55,0000% | 0,02343% |
| 2% | Centro-Oeste | 2 | 38.048 | 3,3333% | 0,00526% |
| 2% | Sudeste | 9 | 203.237 | 15,0000% | 0,00443% |
| 2% | Sul | 2 | 72.015 | 3,3333% | 0,00278% |
| 0% | Norte | 5 | 43.769 | 33,3333% | 0,01142% |
| 0% | Nordeste | 6 | 140.828 | 40,0000% | 0,00426% |
| 0% | Centro-Oeste | 0 | 38.048 | 0,0000% | 0,00000% |
| 0% | Sudeste | 4 | 203.237 | 26,6667% | 0,00197% |
| 0% | Sul | 0 | 72.015 | 0,0000% | 0,00000% |

Totais nacionais dos cortes: 8.299 seções com abstenção até 10%; 559 até 5%; 60 até 2%; 15 com abstenção zero. As contagens regionais somam esses totais e os percentuais dentro de cada corte nacional somam 100% antes do arredondamento.

## Confronto com a implementação

`ruff check scripts/geografia_comparecimento.py` passou antes da revisão manual. O script restringe a leitura às oito colunas necessárias, verifica chaves únicas, denominador positivo, balanço do eleitorado e classificação de UF. Os cortes inteiros são equivalentes aos usados na implementação independente. O Parquet de origem contém o recorte presidencial de 2026 já validado na ingestão.

As 20 linhas de `reports/geografia_comparecimento.csv` foram confrontadas com os valores obtidos da releitura do ZIP. Contagens, totais regionais, totais nacionais dos cortes e as duas proporções coincidem. Tolerância numérica absoluta de 1e-12 nas porcentagens. Nenhum arquivo de dados ou script de produção foi alterado pelo revisor.

## Veredicto

Aprovado para apresentação descritiva da distribuição territorial e das taxas de inclusão nos cortes. Não foram encontradas divergências numéricas ou de classificação regional. A distribuição não estabelece causa para a abstenção observada. Valores arredondados são apenas de apresentação; o CSV preserva a precisão dos cálculos.

## Conferência do texto de apresentação

Conferido `reports/GEOGRAFIA_ABSTENCAO.md` em 26/10/2026 08:12:50 -0300. A tabela de até 5% e seus arredondamentos coincidem com a fonte: Norte 124 (22,18%), Nordeste 294 (52,59%), Sudeste 78 (13,95%), Sul 47 (8,41%) e Centro-Oeste 16 (2,86%). A frase de até 2% também confere: 33 das 60 seções estão no Nordeste, equivalentes a 55%. Os denominadores e o caráter cumulativo dos cortes estão explicitados corretamente.
