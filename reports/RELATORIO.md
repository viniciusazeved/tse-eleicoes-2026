# Comparecimento e votação presidencial de 2026

Relatório inicial. Fontes coletadas em 26/10/2026, com conferência independente dos dados e cálculos. Projeto independente, identidade neutra.

## Resposta à pergunta

No primeiro turno, as seções de comparecimento muito alto apresentam maior participação agregada de votos para Lula. Entretanto, a relação nacional é fraca e muda de sinal depois de comparar seções dentro da mesma geografia. Isso não sustenta interpretar alta participação, isoladamente, como evidência de voto em nome de ausentes.

O segundo turno já foi analisado no nível município/zona. Nesse nível, a associação entre comparecimento e participação de Lula nos votos válidos é fraca e negativa. O arquivo nacional do segundo turno por seção ainda não estava disponível na coleta. Portanto, o teste específico entre seções do mesmo local no segundo turno permanece pendente. Resultados por zona não substituem esse teste.

## Primeiro turno por seção

O banco preserva 499.248 registros de seção: 497.897 no Brasil e 1.351 no exterior. Os modelos principais excluem o exterior. Cada linha possui aptos, comparecimento, abstenção, votos válidos, brancos, nulos e votos por candidatura. A tabela longa preserva os registros publicados pelo TSE.

No Brasil, a correlação de Pearson entre comparecimento e fração dos votos válidos de Lula é 0,0685; Spearman é 0,0647. As duas são correlações fracas.

| Comparecimento mínimo | Seções no Brasil | Lula nos votos válidos | Flávio nos votos válidos |
|:--|--:|--:|--:|
| 90% | 8.299 | 55,63% | 38,04% |
| 95% | 559 | 61,72% | 31,94% |
| 98% | 60 | 70,76% | 24,58% |
| 100% | 15 | 73,53% | 23,43% |

Os cortes são cumulativos e não podem ser somados. As taxas são votos somados divididos por votos válidos somados, não médias simples de percentuais. Restam votos dos demais candidatos. Seções pequenas e a composição territorial influenciam esses grupos.

O modelo ajusta pelo logaritmo do número de aptos e seu quadrado. A tabela abaixo usa ponderação pelos votos válidos e intervalos agrupados por município. O coeficiente é a mudança associada na participação de Lula, em pontos percentuais, para dez pontos percentuais a mais de comparecimento.

| Comparação | Associação em pp por 10 pp | Intervalo de 95% |
|:--|--:|:--|
| Nacional, sem efeito fixo geográfico | +1,63 | +0,43 a +2,83 |
| Dentro da mesma UF | -4,75 | -5,33 a -4,18 |
| Dentro do mesmo município | -2,07 | -2,42 a -1,72 |
| Dentro do mesmo local de votação | -0,46 | -0,61 a -0,30 |

A análise dentro do local utiliza 476.122 seções, em 72.353 locais e 5.570 municípios. Locais sem variação de comparecimento não identificam a associação. A versão sem ponderação também é negativa: -0,43 pp por 10 pp. As versões com pelo menos 100 aptos estão em `modelos.csv`.

Os intervalos representam incerteza do modelo. Não representam erro amostral do censo observado nem probabilidade de fraude. A inversão entre resultados nacionais e internos à geografia mostra que a composição territorial importa.

## Segundo turno por município/zona

Foram coletadas 6.292 chaves oficiais município/zona, incluindo 186 no exterior. Todas as chaves do primeiro turno agregado encontraram correspondência. A soma das respostas foi conciliada exatamente com os resultados oficiais do Brasil e de cada UF.

Nas 6.106 chaves brasileiras, a correlação de Pearson entre comparecimento e participação de Lula nos votos válidos é -0,0610; Spearman é -0,0382. Para Flávio, os sinais são opostos, porque as frações dos dois finalistas somam 100% dos válidos.

Somente 1.878 dessas chaves brasileiras mantêm o mesmo número de aptos nos dois turnos. Nesse subconjunto, a correlação entre mudança do comparecimento e mudança do apoio a Lula é 0,0262. Igualdade de aptos não comprova identidade dos eleitores. O subconjunto também pode ter composição diferente do restante do país.

O aumento da votação de um finalista não pode ser atribuído diretamente aos eleitores adicionais: também há transferência dos votos dos candidatos eliminados, mudanças entre votos válidos, brancos e nulos, além de entrada e saída de eleitores. As diferenças agregadas não revelam esses fluxos individuais.

## Horários e prorrogação

A nota oficial de 25/10 confirma prorrogação excepcional para locais cuja votação ainda não havia sido encerrada às 17h. O recebimento dos boletins e a divulgação foram retomados depois das 19h. Portanto, horário de divulgação não é horário do voto.

Os logs permitem investigar eventos com horário, mas não informam a candidatura escolhida. Não é possível demonstrar que “depois das 17h só houve votos no Lula” cruzando horário com RDV. Um pacote de log do segundo turno foi inspecionado tecnicamente e também continha histórico do primeiro turno, o que exige filtro exato da data.

Ainda não foi realizado o censo nacional dos eventos dos logs. Não há, neste relatório, contagem nacional de votos depois das 17h, nem atribuição desses votos a candidatos. O procedimento necessário está documentado em `docs/HORARIOS.md`.

## Integridade, exceções e limites

A revisão releu os ZIPs do primeiro turno e conciliou os campos e os votos de todas as seções com a base processada. Não foram encontradas duplicatas nem divergências de votação. Há 41 seções não instaladas no exterior, com 423 aptos e zero comparecimento/abstenção publicados, além de uma seção instalada sem comparecimento. São exceções documentadas, não classificadas como irregularidade.

O TSE também informa 39 registros de dupla vinculação em transferências temporárias. Eles não são os mesmos 423 registros das seções não instaladas. Os arquivos são preservados sem deduções arbitrárias. A taxa sobre todos os aptos cadastrais pode diferir da taxa oficial sobre o eleitorado instalado no exterior; as análises principais separam esse universo.

Composição demográfica, mobilização, transporte e características locais continuam sendo explicações possíveis mesmo após controles geográficos. Esta análise não confirma nem exclui voto em nome de ausentes. Ela mede associações e aponta quais perguntas ainda dependem de dados e documentação.

## Próximas etapas

Obter o pacote oficial do segundo turno por seção quando publicado, reconciliar com os totais já coletados e repetir as análises dentro dos mesmos locais, com auditoria do pareamento. Em seguida, avaliar coleta temporal por logs com validação de eventos, fuso, contingências e cobertura antes de qualquer resultado nacional.

## Fontes e arquivos de conferência

- [Resultados TSE 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026).
- [Documentação técnica dos resultados](https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados).
- [Nota do TSE sobre a prorrogação](https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/esclarecimento-sobre-prorrogacao-da-votacao).
- `fontes.json`, `qa_zonas_turno2.json`, `resumo.json`, `resumo_zonas2.json`, `cortes.csv`, `correlacoes.csv` e `modelos.csv` preservam os insumos desta síntese.
