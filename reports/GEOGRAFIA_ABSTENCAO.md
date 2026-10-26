# Localização das seções com baixa abstenção

Recorte: primeiro turno de 2026, território brasileiro, excluído o exterior. Esta tabela usa somente aptos, abstenção e localização da seção. Não contém avaliação de candidaturas.

Fonte: [Detalhe da apuração por seção no portal TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026). Agrupamento territorial conforme as [Grandes Regiões do IBGE](https://educa.ibge.gov.br/jovens/conheca-o-brasil/territorio/19637-divisao-territorial.html).

## Abstenção de até 5%

| Região | Seções neste corte | Parcela das 559 seções brasileiras do corte |
| :-- | --: | --: |
| Norte | 124 | 22,18% |
| Nordeste | 294 | 52,59% |
| Sudeste | 78 | 13,95% |
| Sul | 47 | 8,41% |
| Centro-Oeste | 16 | 2,86% |

No corte de abstenção de até 2%, existem 60 seções brasileiras, das quais 33 estão no Nordeste (55%). Os cortes são inclusivos e cumulativos; não podem ser somados. As porcentagens acima se referem ao conjunto nacional das seções de baixa abstenção, não à população nem ao conjunto de todas as seções de cada região.

A tabela completa em `geografia_comparecimento.csv` inclui também os limites de 10% e zero e informa o denominador de todas as seções de cada região. O script `scripts/geografia_comparecimento.py` usa comparação inteira de abstenção/aptos para evitar arredondamento nos limites. O universo contém 497.897 seções com aptos positivos e balanço comparecimento + abstenção = aptos.

Essas contagens descrevem presença e localização. Não identificam quem compareceu individualmente nem o preenchimento de votos por terceiros.
