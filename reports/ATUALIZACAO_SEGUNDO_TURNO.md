# Comparecimento do segundo turno por seção

A atualização do arquivo de detalhe por seção foi obtida em 26/10/2026. A nova fonte contém os dois turnos de 2026, com 499.248 seções em cada turno, incluindo 1.351 no exterior. Na consulta das 12h45, horário de Brasília, a resposta consultada para o arquivo nominal ainda apresentava os metadados da versão anterior. Não foi obtida uma nova versão nominal nesta atualização.

Esta atualização trata exclusivamente da disponibilidade, da integridade contábil e da distribuição territorial da abstenção. As tabelas de votação do painel permanecem na versão anteriormente conferida. Não houve combinação de votos antigos com comparecimento novo.

## Abstenção no segundo turno

Recorte: 497.897 seções em território brasileiro. As porcentagens indicam a parcela do conjunto nacional de seções que satisfaz cada corte, sem ponderação pelo tamanho do eleitorado.

| Região | Seções com abstenção até 5% | % desse corte nacional | Seções com abstenção até 2% | % desse corte nacional |
| :-- | --: | --: | --: | --: |
| Norte | 58 | 9,08% | 6 | 9,09% |
| Nordeste | 367 | 57,43% | 47 | 71,21% |
| Sudeste | 113 | 17,68% | 6 | 9,09% |
| Sul | 80 | 12,52% | 3 | 4,55% |
| Centro-Oeste | 21 | 3,29% | 4 | 6,06% |
| Brasil sem exterior | 639 | 100% | 66 | 100% |

Os cortes são inclusivos e cumulativos, portanto não podem ser somados. Esses percentuais não são taxas de abstenção da população regional. As contagens completas, incluindo os cortes de 10% e zero, estão em [geografia_comparecimento_turno2.csv](geografia_comparecimento_turno2.csv). Localização e comparecimento não identificam a escolha individual de voto nem quem registrou cada voto.

## Conferência da base

As chaves de seção são únicas. Os totais do segundo turno por município/zona coincidem com as 6.292 chaves da referência oficial já arquivada nos seis campos de aptos, comparecimento, abstenção, válidos, brancos e nulos. O primeiro turno dessa nova fonte coincide com a base previamente validada nos mesmos campos.

O balanço comparecimento mais abstenção equivale a aptos em todas as seções brasileiras. No exterior, permanecem 41 seções não instaladas por turno, com 423 aptos e zero comparecimento e abstenção publicados. A exceção foi preservada. Não foram fabricadas ausências para fechar o cadastro.

O resultado foi conferido por revisor independente diretamente no ZIP, sem reutilizar o cálculo do importador. Consulte o [parecer da atualização](../docs/REVISAO_DETALHES_ATUALIZACAO.md) e o [QA estrutural](qa_detalhes_20261026-123844.json).

## Origem e rastreabilidade

Fonte: [Portal de Dados Abertos do TSE, resultados de 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026), recurso de detalhe da apuração por seção. A resposta nova foi obtida na [URL oficial com parâmetro de verificação de cache](https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip?verificacao=20261026T153535).

SHA256 do ZIP: `8ef9ce3a85cde260471faf7a83a9b4f5ccf3993fdda942aacaa658574344789c`. Tamanho: 234.357.769 bytes. O CSV informa geração em 26/10/2026 às 09:49:06. O servidor informou última modificação às 15:35:35 UTC. O download finalizado foi registrado às 12:44:34, horário de Brasília.

Durante a coleta, a consulta HEAD anunciou a versão nova, mas o primeiro GET devolveu integralmente a versão antiga. A igualdade de hash com o arquivo anterior confirmou essa ocorrência. Um GET parcial com parâmetro de verificação devolveu os cabeçalhos novos, permitindo obter e conferir o novo ZIP. As duas respostas e o manifesto foram preservados localmente em `data/raw/versoes/20261026-123844`. O catálogo ainda conservava a data de atualização anterior; sua data isolada não foi usada como prova de ausência de arquivo novo.

O Parquet intermediário está em `data/interim/20261026-123844/detalhes_presidente.parquet`. A nova tabela não foi promovida à base de votos do painel. A próxima etapa depende do arquivo nominal atualizado, seguido de conciliação e revisão antes de publicar uma base completa.
