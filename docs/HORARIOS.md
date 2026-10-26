# Disponibilidade e método para horários de votação

Autor: subagente Astra de revisão. Verificação em 2026-10-26 07:14:17 -03:00. Apenas investigação técnica, sem censo de logs ou estimativas de votos tardios.

## Situação excepcional do segundo turno

A [nota oficial do TSE](https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/esclarecimento-sobre-prorrogacao-da-votacao), publicada em 25/10/2026 às 18h44 e atualizada às 19h02, informa continuidade somente onde a votação ainda não havia encerrado às 17h e retomada de recebimento, totalização e divulgação após 19h. Consultar também o ato judicial integral antes de classificar qualquer ocorrência como descumprimento. A nota, isoladamente, não detalha cada situação operacional.

Assim, os intervalos antes das 17h, entre 17h e 19h e após 19h são categorias descritivas. Estar após 17h não constitui indicador autossuficiente de irregularidade; estar após 19h também exige contexto de fila e atos aplicáveis. Recebimento depois das 19h não indica voto dado depois das 19h.

## Fontes e descoberta de arquivos

A [documentação técnica oficial 2026](https://www.tse.jus.br/eleicoes/informacoes-tecnicas-sobre-a-divulgacao-de-resultados) confirma ambiente oficial, ciclo ele2026, eleição federal 6258 e pleito 3221 para o segundo turno. O serviço admite até 100 requisições por segundo por IP; repetição de erros pode bloquear acesso. Recomenda-se taxa conservadora, cache e retomada.

O [guia de download 2026, versão 1.1 de 19/10](https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/divulgacao-de-resultados/tse-instrucoes-para-download-dos-arquivos-da-divulgacao-2026) descreve descoberta EA11, EA16, EA18, depois arquivo da urna. Nomes e hashes devem ser extraídos dos índices reais, sem varredura de caminhos presumidos.

Verificações reais realizadas nesta sessão:

- [EA11 comum](https://resultados.tse.jus.br/oficial/comum/config/ele-c.json): retornou configuração oficial com data de geração 18/10, contendo pleito 3220 e vínculo da eleição 6257 com segundo turno 6258. A resposta consultada não listava pleito 3221, embora este esteja documentado na página oficial e sua árvore funcione. Não concluir indisponibilidade apenas desse índice.
- [EA16 do DF para pleito 3221](https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/df/df-p003221-cs.json): resposta oficial, cdp=3221 e geração 25/10. Contém município, zonas e seções.
- [EA18 de exemplo, Brasília, zona 0001, seção 0001](https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados/df/97012/0001/0001/p003221-df-m97012-z0001-s0001-aux.json): seção totalizada; lista arquivos de log, assinatura, RDV e BU. Consulta de disponibilidade não valida todos os BUs nacionais.
- [EA20 da mesma zona no segundo turno](https://resultados.tse.jus.br/oficial/ele2026/6258/dados/df/df97012-z0001-c0001-e006258-u.json): resposta oficial, ele=6258, t=2, tpabr=zona. Útil para conferência agregada. Não contém cada seção individual.
- [Catálogo de arquivos transmitidos 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026-arquivos-transmitidos-para-totalizacao), consultado também pela API CKAN package_show: os recursos anunciados eram somente do primeiro turno no momento da consulta.

O [EA16](https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/divulgacao-de-resultados/tse-ea16-arquivo-de-configuracao-de-secoes-eleitorais) distingue seção principal e agregadas. Seus campos da/ha representam geração do auxiliar, não votação. O [EA18](https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/divulgacao-de-resultados/tse-ea18-arquivo-auxiliar-de-secao) fornece hashes, arquivos e situação; dr/hr representam recebimento. Preservar todos os estados e reenvios; não selecionar hash pelo simples ordenamento lexical.

O [EA20](https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/divulgacao-de-resultados/tse-ea20-arquivo-de-resultado-unificado) documenta Brasil, UF, município e zona. Uma coleta por zona reduz requisições, porém não substitui a análise entre seções de um mesmo local. Não foi encontrado nesta investigação um pacote oficial consolidado de seções do segundo turno. A via confirmada é auxiliar e BU por seção principal; a disponibilidade de um recurso não confirma completude nacional.

## Exemplo técnico confirmado em memória

Base da seção: `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados/df/97012/0001/0001/`.

Na resposta auxiliar consultada, o hash foi `436858652d35384167714e6f65684166662b417164726b4759494c333578744b4f577961485153544c70453d`. O arquivo de log anunciado foi `o03221df9701200010001-log.jez`; o BU anunciado foi `o03221df9701200010001-bu.dat`. A URL é base, hash, nome, separados por barra. Essa referência é uma fotografia da consulta, não deve ser fixada como seletor de versão em um coletor.

O log foi baixado e lido em memória, sem gravar dados pessoais ou arquivo bruto no projeto. O pacote era ZIP e continha `logd.dat`, texto separado por tabulações. Colunas observadas: data/hora, nível, identificador do equipamento, aplicação, mensagem e identificador da linha. Foi observada a mensagem de aplicação VOTA `O voto do eleitor foi computado`.

Ponto crítico: o log do pacote do segundo turno contém histórico tanto de 04/10 como de 25/10 e operações de preparação. É obrigatório filtrar a data eleitoral correta e a sessão de aplicação VOTA do turno, sem escolher o dia com mais eventos. O exemplo também ilustra que horário de encerramento e último voto são diferentes. Não se produziu contagem estatística a partir desse exemplo.

## Procedimento proposto para a fase de horários

1. Definir universo das seções principais instaladas e situações aceitas. Preservar turno, pleito, eleição, UF, município, zona, seção, agregações, versão do auxiliar, URL, coleta e hash dos bytes. Inventariar faltantes por UF e situação, sem chamar ausência de arquivo de ausência de voto.
2. Validar o decodificador do BU e dos logs em casos manuais, incluindo substituições e pacotes aninhados. Conferir hashes e assinaturas quando possível, distinguindo igualdade de hash local de autenticação criptográfica pela cadeia oficial.
3. Extrair a sessão VOTA correta no dia oficial: 04/10/2026 ou 25/10/2026. Confirmar a semântica da mensagem de voto computado contra total de votantes do BU. Um evento de conclusão não deve ser confundido com voto para cada cargo nem com voto válido presidencial.
4. Tratar reinícios, troca de equipamento, logs concatenados e sobrepostos, tentativas canceladas, suspensão do eleitor e votação parcial. Deduplicação exige identidade do trecho/evento; somente timestamp é insuficiente, pois eventos legítimos podem coincidir no segundo.
5. Conferir padrão temporal real dos arquivos: relógio local, offset e correções. A amostra DF não resolve a regra nacional. Converter para Brasília apenas com origem de fuso estabelecida; exterior deve ficar separado. Havendo relógio ambíguo, marcar como indeterminado e não imputar silenciosamente.
6. Contar conclusões antes das 17h, no instante 17:00:00, depois das 17h até 19h e depois das 19h, definindo inclusividade de fronteiras. Apresentar também início de habilitação e duração quando corretamente identificáveis, pois conclusão posterior não indica chegada posterior à fila.
7. Comparar total de conclusões com comparecimento/votantes do BU; classificar divergências e deixar casos sem conciliação fora do indicador principal, com cobertura explícita e análise separada. Não ajustar artificialmente contagens para fechar.
8. Agregar somente contagens temporais e proporções, com cobertura por seções e comparecimento. Aplicar revisão independente do parser e conferência dos números antes de qualquer conclusão.

## Limite de interpretação

O log não liga horário a candidato. O [esclarecimento técnico da Justiça Eleitoral](https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2024/codigo-fonte-da-urna-eletronica-nao-revela-voto-do-eleitorado) diferencia log e RDV e afirma preservação do sigilo mesmo quando se conhece o horário. É inválido multiplicar votos tardios pela votação final do candidato e apresentar o produto como contagem observada. Associação entre volume tardio e resultado da seção continua ecológica e sujeita a filas, tamanho, composição e mobilização.

Pendências antes de escala: esquema/decodificador oficial do BU2026; regra temporal nacional e exterior; casos de contingência; inventário de cobertura dos arquivos do segundo turno; conciliação BU/log; auditoria independente dos resultados. Nenhuma rotina de coleta nacional de logs ficou executando por este subagente.

## Coleta agregada implementada em 2026-10-26 07:25:36 -03:00

`scripts/fetch_zonas.py` obtém EA16 de todas as abrangências, inclusive exterior, e baixa EA20 por chave município/zona com até quatro conexões. Cada resposta original fica em `data/raw/api_turno2`, acompanhada de URL, timestamp, hash SHA256 e cabeçalhos HTTP. O script utiliza cache somente após conferir hash e URL; não repete 404, interrompe em bloqueios e aplica espera crescente para erros temporários.

A saída é `data/processed/zonas_turno2.parquet`; seu QA é `reports/qa_zonas_turno2.json`, com comparação das somas contra EA20 nacional e de cada UF. Nenhuma seção foi fabricada. Essa base resolve a etapa agregada do segundo turno, mas não a pergunta sobre votos concluídos em horários específicos. A coluna `bolsonaro` identifica Flavio Bolsonaro no cadastro real de 2026.

O QA preserva totalização, eleitorado total e eleitorado instalado. Conforme o dicionário oficial, comparecimento e abstenção somam o eleitorado instalado, não o total cadastrado quando há seção não instalada. A conciliação utiliza essa distinção sem alterar os dados brutos. Os resultados precisam da auditoria independente antes de publicação.

Estado operacional em 2026-10-26 07:26:47 -03:00: coleta e reprocessamento concluídos, sem processos desta tarefa rodando. O QA registra cobertura completa das chaves descobertas, concordância de chaves EA12/EA16, ausência de falhas de coleta ou de identidades contábeis e conciliação exata com os agregados oficiais. O arquivo está pronto para auditoria independente; esse estado de QA não constitui parecer sobre fraude nem validação das análises estatísticas posteriores.
