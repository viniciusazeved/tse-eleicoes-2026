# Revisão independente dos dois turnos por seção

Revisor: agente GPT-6 Astra independente da implementação e da redação principal. Conferência encerrada em 26/10/2026 às 15:05, horário de Brasília. Snapshot `20261026-144303`.

## Veredicto

Aprovado para promoção e publicação conjunta dos dados, análises e relatório deste snapshot. A aprovação se limita à fidelidade às fontes arquivadas, à contabilidade, aos cálculos e à interpretação observacional descrita. Não é certificação independente da ocorrência material de cada voto nem conclusão sobre fraude.

Resumo da revisão Python após as correções: zero achados críticos pendentes, zero pendências numéricas e uma sugestão de manutenção, centralizar as verificações duplicadas de integração e revalidação. A publicação deve usar os artefatos completos do mesmo snapshot. Esta revisão não confirma o estado de um deploy remoto posterior.

## Fontes e procedimento independente

Foram reabertos os membros nacionais dos dois ZIPs, sem executar a ingestão para obter os números da conferência. A comparação independente usou pandas, PyArrow e DuckDB. As estimativas foram refeitas com médias de grupo ponderadas, `numpy.linalg.lstsq` e covariância agrupada por município, sem chamar o estimador de produção.

| Fonte | Bytes | SHA256 |
|:--|--:|:--|
| Votação nominal, versão 14:43 | 241.891.087 | `c928321f63f2d095706fca73d4607c048d2ada23bda6876455d6911aaf1bc9c1` |
| Detalhe contábil, versão 12:38 | 234.357.769 | `8ef9ce3a85cde260471faf7a83a9b4f5ccf3993fdda942aacaa658574344789c` |

Os hashes foram recalculados na revisão. As fontes versionadas estão em `data/raw/versoes/20261026-144303` e `data/raw/versoes/20261026-123844`. Também foram reabertos o ZIP nominal inicial, o detalhe inicial e os 6.292 JSONs oficiais de município/zona do segundo turno preservados localmente. Nenhuma nova coleta de rede foi realizada nesta rodada.

As 5.731.614 linhas nominais foram comparadas individualmente, incluindo chave completa, número, nome e votos. As 998.496 linhas de detalhe foram comparadas à base integrada, incluindo local de votação. A votação foi somada por seção independentemente e conciliada com válidos, brancos, nulos, Lula, Flávio Bolsonaro e demais candidaturas. Não há duplicatas nominais nem de seção, votos órfãos ou contagens negativas. O primeiro turno nominal foi comparado integralmente ao ZIP inicial, por diferença de multiconjuntos nos dois sentidos, sem divergências.

Os testes de [test_review.py](../tests/test_review.py) executaram com êxito 29 casos em lotes: confronto bruto, preservação nominal, 16 especificações locais, seis outros modelos mostrados no relatório, JSONs de zona, totais e cortes dos dois turnos, pareamento e composição regional. Os destinos são configuráveis por `TSE_REVIEW_DATA_DIR` e `TSE_REVIEW_REPORTS_DIR`; o padrão é a publicação em `data/processed` e `reports`. Os testes que exigem originais são explicitamente ignorados quando esses arquivos locais não estão presentes.

## Integridade e cobertura

Cada turno contém 499.248 seções: 497.897 no Brasil e 1.351 em ZZ. O segundo turno agregado pelas 6.292 chaves UF/município/zona coincide com os JSONs oficiais nas oito métricas de aptos, comparecimento, abstenção, válidos, brancos, nulos e votos dos dois finalistas. O campo `outros` é zero em todas as seções do segundo turno.

No Brasil, aptos = comparecimento + abstenção em todas as seções. No exterior, 41 seções não instaladas por turno, com 423 aptos, têm comparecimento e abstenção publicados como zero. Essas exceções são preservadas. Além delas, uma seção instalada no primeiro turno e duas no segundo têm comparecimento zero. São 42 e 43 seções sem linha nominal, respectivamente, totalizando 85 registros. Isso não autoriza fabricar votos nem abstenções.

| Brasil sem exterior | Primeiro turno | Segundo turno |
|:--|--:|--:|
| Aptos | 157.828.968 | 157.828.819 |
| Comparecimento | 124.934.069 | 127.854.631 |
| Abstenção | 32.894.899 | 29.974.188 |
| Válidos | 118.975.029 | 123.710.622 |
| Lula | 53.722.151 | 64.056.078 |
| Flávio Bolsonaro | 55.960.603 | 59.654.544 |
| Demais candidaturas | 9.292.275 | 0 |

As identidades dos candidatos foram conferidas no campo original: número 13, Luiz Inácio Lula da Silva; número 22, Flavio Nantes Bolsonaro. A abreviação interna `bolsonaro` não corresponde a Jair Bolsonaro neste conjunto.

## Estimativas e denominadores

As correlações nacionais por seção usam comparecimento/aptos e votos da candidatura/válidos. Para Lula, foram reproduzidos Pearson 0,068486308602 e Spearman 0,064700882238 no primeiro turno; Pearson 0,048456350073 e Spearman 0,066468985298 no segundo. A antiga correlação de segundo turno por município/zona, Pearson -0,061026812941, permanece correta para outra unidade de agregação. Não pode substituir o resultado por seção.

Foram conferidos o controle por log(aptos) e seu quadrado, o peso igual por seção ou por válidos, os mínimos de 1 e 100 aptos e a identificação composta do local por UF, município, zona e código local. Os intervalos de 95% usam agrupamento por município, correção finita com os efeitos absorvidos e distribuição t. O fator de apresentação está correto: coeficiente em frações multiplicado por 10 produz pontos percentuais de apoio por dez pontos percentuais de participação.

| Modelo local de Lula, mínimo 1 apto | Coeficiente pp/10 pp | IC95% |
|:--|--:|:--|
| Primeiro turno, peso por seção | -0,4269514035 | -0,5692373439 a -0,2846654631 |
| Primeiro turno, peso por válidos | -0,4548469849 | -0,6074031873 a -0,3022907825 |
| Segundo turno, peso por seção | -0,3112447416 | -0,4804831113 a -0,1420063720 |
| Segundo turno, peso por válidos | -0,3750279097 | -0,5609258389 a -0,1891299804 |

Os modelos locais usam 476.142 e 476.133 seções, respectivamente. A exclusão de locais sem variação é coerente com o estimador. As versões com pelo menos 100 aptos mantêm os sinais. No segundo turno, os resultados dos dois finalistas são complementares, não evidências estatísticas independentes. Intervalos descrevem incerteza de modelo, não erro amostral de um censo nem probabilidade de fraude.

Os cortes nacionais de comparecimento de 90%, 95%, 98% e 100% contêm 8.299, 559, 60 e 15 seções no primeiro turno; 14.841, 639, 66 e 12 no segundo. Foram conferidas as 40 linhas de `cortes_regioes.csv`, incluindo contagens e todas as somas de votos. As contagens coincidem com os dois relatórios territoriais anteriores, calculados exclusivamente com abstenção e localização.

No segundo turno, o corte de pelo menos 95% soma 107.911 válidos, 72.824 votos de Lula e 35.087 de Flávio: 67,48524247% e 32,51475753%. O Nordeste reúne 367 das 639 seções (57,43348983%) e Lula tem 76,44614209% dos válidos desse grupo regional. A parcela territorial usa número de seções; o apoio usa soma dos votos válidos. Nenhum desses percentuais é a média simples das porcentagens das seções.

## Pareamento e atualização dos locais

Todas as 499.248 chaves UF/município/zona/seção aparecem nos dois turnos. No Brasil, 55.406 chaves têm aptos diferentes e 431 têm códigos válidos de local diferentes. As exclusões podem se sobrepor. O recorte principal tem 442.108 seções brasileiras e 992 no exterior, com aptos e local iguais e aptos/válidos positivos nos dois turnos.

No recorte principal brasileiro, a correlação entre mudança de participação e mudança do apoio de Lula é Pearson 0,111439071768 e Spearman 0,106850999550. A média da mudança por seção é +1,70960659 pp de participação e +6,40900332 pp de apoio. As diferenças entre razões agregadas são +1,85697275 pp e +6,60949769 pp. Todas as oito combinações de universo, amostra e candidato do relatório de pareamento foram reproduzidas.

O novo detalhe oficial também atualizou o primeiro turno: 421 códigos locais, 400 nomes e 409 endereços diferem do ZIP inicial. As 421 diferenças de código persistem após conversão a inteiro, portanto não decorrem apenas de zeros à esquerda. Os votos e totais contábeis permaneceram iguais. A mudança de grupos locais altera discretamente o modelo do primeiro turno, antes -0,4550758421 e agora -0,4548469849 pp/10 pp com peso por válidos. Trata-se de mudança na informação cadastral da fonte, não de alteração de votos pelo processamento.

Mesmo com aptos e local iguais, não está demonstrado que as mesmas pessoas votaram. As mudanças de votos também envolvem candidaturas eliminadas e brancos/nulos. O pareamento não identifica fluxos individuais ou a origem dos votos adicionais.

## Revisão do código e da apresentação

Ruff passou em `analyze.py`, `analyze_zones.py`, `ingest.py`, `stage_nominal_update.py`, `app.py` e `test_review.py`. A revisão encontrou e encaminhou duas lacunas do novo aprovador de integração: ausência de bloqueio explícito de duplicatas/órfãos e caracterização insuficiente das exceções; depois, a revalidação precisava comparar também as três parcelas nominais por seção. As correções foram conferidas no código e o QA foi reemitido sem alterar os Parquets.

O painel foi revisado no código quanto a filtros de turno e exterior, nomes, razões de somas, elegibilidade do pareamento, escala percentual regional e rótulos dos modelos nacionais. Os modelos nacionais são explicitamente separados dos filtros locais da interface. Esta etapa não substitui o teste visual do painel publicado.

O [relatório consolidado](../reports/RELATORIO.md) foi confrontado com as tabelas auditadas: contagens, percentuais, arredondamentos, intervalos e comparações entre turnos são consistentes. A interpretação descreve diferenças agregadas e condicionais; não sustenta inferência causal ou acusação. A dimensão de horários continua sem censo nacional nesta entrega e não fornece identificação de candidatura por horário.

Sugestão de manutenção, sem bloqueio deste snapshot: extrair um helper comum para as verificações repetidas de `executar` e `revalidar_snapshot`, evitando que futuras regras de QA sejam aplicadas apenas a um dos caminhos. A gravação de múltiplos artefatos não é uma transação única do sistema operacional; a publicação conjunta deve ocorrer como snapshot completo, após QA.

## Identidade dos artefatos aprovados

| Artefato | SHA256 |
|:--|:--|
| `secoes.parquet` | `a5d0eb692f16e4077cee9317a10df94ef29f2c7ebb7b19f39ec4a898a60b71c2` |
| `votos.parquet` | `99a164aee7884cf69f786be01ee8860d07857841ac1326584c6adad26759ec66` |
| `pareamento_secoes.parquet` | `d2211a8acb987881f779125d245395348af542bc809892b1652c63f56547de48` |

Os dois primeiros hashes foram conferidos novamente após a correção do QA. A aprovação acompanha esses conteúdos e os resultados associados, não qualquer arquivo futuro com o mesmo nome.

Após a promoção local, os três Parquets acima e todos os arquivos de análise em `reports` foram comparados ao staging e são idênticos. Os quatro testes de totais por turno, pareamento e cortes regionais passaram novamente sobre os caminhos de produção. Nenhum processo desta revisão permanece em execução.
