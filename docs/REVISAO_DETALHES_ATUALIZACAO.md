# Revisão independente da atualização do detalhe por seção

Atualizado em 26/10/2026 12:51:27 -0300. Agente revisor: Astra independente. Escopo: disponibilidade, integridade, contabilidade e distribuição territorial da abstenção. O revisor escreveu somente este parecer.

## Veredicto

Aprovado para arquivamento da versão `20261026-123844`, conservação do staging separado e apresentação do relatório territorial de abstenção do segundo turno. A aprovação não promove esta base ao painel de votação. O detalhe contábil novo não foi combinado com arquivos nominais antigos.

Não foram encontrados problemas pendentes que invalidem a integridade, os balanços ou os resultados territoriais deste snapshot. O problema de truncamento de frações na normalização foi corrigido e verificado antes deste parecer final.

## Fonte e rastreabilidade

- Fonte: `data/raw/versoes/20261026-123844/detalhe_votacao_secao_2026.zip`.
- Tamanho conferido: 234.357.769 bytes.
- SHA256 calculado independentemente: `8ef9ce3a85cde260471faf7a83a9b4f5ccf3993fdda942aacaa658574344789c`.
- Membro nacional relido: `detalhe_votacao_secao_2026_BR.csv`.
- Geração interna: 26/10/2026 às 09:49:06, conforme os campos da fonte, sem inferir fuso não documentado nesses campos.
- Eleições verificadas: 6257 no turno 1 e 6258 no turno 2; ano 2026, cargo 1/Presidente, tipo 2/Eleição Ordinária.

O manifesto ao lado do ZIP registra coleta em 26/10/2026 às 12:44:34 -03:00, URL canônica, URL com parâmetro de verificação, ETag `df80409-65ec014ca87c2` e Last-Modified `Mon, 26 Oct 2026 15:35:35 GMT`. O tamanho e o hash do arquivo recebido coincidem com o manifesto. O histórico de divergência entre HEAD e o primeiro GET foi informado pelo coletor e preservado no manifesto; este revisor não repetiu as requisições HTTP. A resposta antiga está preservada como `resposta_cache_antiga.zip` e o arquivo original de produção também foi preservado.

## Método independente

O revisor leu diretamente o CSV nacional dentro do ZIP usando seleção explícita de colunas. Foram acessados metadados da eleição, chaves territoriais, local, situações de seção e contagens de aptos, comparecimento, abstenção, válidos, brancos, nulos e anulados apurados em separado. O campo `QT_VOTOS_NOMINAIS` foi utilizado somente como total agregado de votos válidos. Não foram acessados identificação, número ou votação de qualquer candidatura. Não foram executados `analyze.py` nem `analyze_zones.py`.

Antes da conversão, os campos numéricos brutos auditados foram conferidos quanto ao formato inteiro. A chave normalizada foi turno, UF, código TSE de município, zona e seção. A conferência não importou nem executou o normalizador de produção para construir a base independente.

## Cobertura e balanços

| Turno | Território brasileiro | Exterior | Total | UFs, incluindo ZZ |
| :-- | --: | --: | --: | --: |
| 1 | 497.897 | 1.351 | 499.248 | 28 |
| 2 | 497.897 | 1.351 | 499.248 | 28 |

Existem 998.496 linhas no membro nacional, sem chave duplicada. As seis métricas contábeis são não negativas e comparecimento é menor ou igual a aptos em todas as linhas. Comparecimento equivale a válidos mais brancos mais nulos em todas as linhas. A soma de anulados apurados em separado é zero.

Comparecimento mais abstenção equivale a aptos em todas as seções brasileiras dos dois turnos. As únicas exceções são 41 seções não instaladas no exterior por turno, com 423 aptos e zero comparecimento, abstenção, válidos, brancos e nulos. Isso explica as 82 divergências cadastrais registradas no QA; nenhum valor foi alterado para fechar artificialmente o balanço.

| Turno/universo | Aptos | Comparecimento | Abstenção | Válidos | Brancos | Nulos |
| :-- | --: | --: | --: | --: | --: | --: |
| 1/Brasil | 157.828.968 | 124.934.069 | 32.894.899 | 118.975.029 | 2.294.982 | 3.664.058 |
| 1/Exterior | 916.534 | 341.766 | 574.345 | 331.005 | 5.816 | 4.945 |
| 2/Brasil | 157.828.819 | 127.854.631 | 29.974.188 | 123.710.622 | 1.425.821 | 2.718.188 |
| 2/Exterior | 916.683 | 381.443 | 534.817 | 371.651 | 4.675 | 5.117 |

## Reconciliações completas

As seis métricas do segundo turno, agregadas independentemente por UF, município e zona, coincidem integralmente com `data/processed/zonas_turno2.parquet` nas 6.292 chaves. Não há chaves exclusivas de uma fonte nem divergência em qualquer métrica.

As seis métricas do primeiro turno coincidem integralmente, seção a seção, com as 499.248 linhas já publicadas em `data/processed/secoes.parquet`. Foram lidas desse arquivo apenas as chaves e as seis métricas contábeis.

As 998.496 linhas do staging `data/interim/20261026-123844/detalhes_presidente.parquet` foram confrontadas integralmente com o ZIP, incluindo chave, seis métricas, código do local e situações instalada/anulada. Não houve divergência. SHA256 do staging auditado: `c0abc97bf0d38a9417abc9dcc02e3aef3289b68ed62f0e7091a6eecea82b6a97`.

O relatório `reports/qa_detalhes_20261026-123844.json` coincide com a conferência independente em contagens, totais por turno, ausência de duplicações e resultados das duas reconciliações. O indicador `promovido` está falso.

## Revisão Python

Ruff passou em `scripts/inspect_details_update.py` antes da inspeção manual e novamente após a correção. Ruff também passou na versão parametrizada de `scripts/geografia_comparecimento.py`.

O normalizador inicial convertia `12.9` em `12`, problema reproduzido em uma execução isolada da função. A versão corrigida usa `normalizar_inteiro_estrito`, rejeitando valores fracionários, ausentes e não finitos. A conferência pontual independente confirmou rejeição de `12.9`, `nan`, `inf`, `-inf`, vazio e `None`, tanto para métricas quanto para códigos; `0012`, `12.0` e `12` são aceitos como o mesmo inteiro. Nenhum valor fracionário ocorreu nos campos brutos deste snapshot.

O inspetor é uma ferramenta de diagnóstico e arquivamento, não um autorizador automático de publicação. Sua saída registra as divergências e mantém o staging separado. A decisão deste parecer se apoia na reconciliação completa, e não apenas no código de saída do processo.

## Distribuição territorial da abstenção no segundo turno

O recorte é turno 2, território brasileiro, excluído ZZ e aptos maiores que zero. São 497.897 seções. Os cortes são inclusivos e foram calculados diretamente na fonte com comparação inteira: abstenção vezes 100 menor ou igual a aptos vezes o limite percentual. Os cortes de 10%, 5%, 2% e zero são cumulativos e não podem ser somados.

Percentual do corte nacional significa seções da região dentro do corte divididas por todas as seções brasileiras do mesmo corte. Percentual regional significa seções da região dentro do corte divididas por todas as seções daquela região. Nenhuma das duas medidas é ponderada pelo eleitorado.

| Abstenção máxima | Região | Seções no corte | Total regional | % do corte nacional | % das seções regionais |
| :-- | :-- | --: | --: | --: | --: |
| 10% | Norte | 686 | 43.769 | 4,6223% | 1,56732% |
| 10% | Nordeste | 10.191 | 140.828 | 68,6679% | 7,23649% |
| 10% | Sudeste | 1.582 | 203.237 | 10,6597% | 0,77840% |
| 10% | Sul | 2.159 | 72.015 | 14,5475% | 2,99799% |
| 10% | Centro-Oeste | 223 | 38.048 | 1,5026% | 0,58610% |
| 5% | Norte | 58 | 43.769 | 9,0767% | 0,13251% |
| 5% | Nordeste | 367 | 140.828 | 57,4335% | 0,26060% |
| 5% | Sudeste | 113 | 203.237 | 17,6839% | 0,05560% |
| 5% | Sul | 80 | 72.015 | 12,5196% | 0,11109% |
| 5% | Centro-Oeste | 21 | 38.048 | 3,2864% | 0,05519% |
| 2% | Norte | 6 | 43.769 | 9,0909% | 0,01371% |
| 2% | Nordeste | 47 | 140.828 | 71,2121% | 0,03337% |
| 2% | Sudeste | 6 | 203.237 | 9,0909% | 0,00295% |
| 2% | Sul | 3 | 72.015 | 4,5455% | 0,00417% |
| 2% | Centro-Oeste | 4 | 38.048 | 6,0606% | 0,01051% |
| 0% | Norte | 2 | 43.769 | 16,6667% | 0,00457% |
| 0% | Nordeste | 7 | 140.828 | 58,3333% | 0,00497% |
| 0% | Sudeste | 2 | 203.237 | 16,6667% | 0,00098% |
| 0% | Sul | 0 | 72.015 | 0,0000% | 0,00000% |
| 0% | Centro-Oeste | 1 | 38.048 | 8,3333% | 0,00263% |

Totais nacionais: 14.841 seções com abstenção até 10%; 639 até 5%; 66 até 2%; 12 com abstenção zero. As contagens e os dois percentuais de todas as 20 linhas de `reports/geografia_comparecimento_turno2.csv` coincidem com a implementação independente sobre o ZIP bruto, com tolerância absoluta de 1e-12 nas porcentagens.

## Limites da aprovação

Esta revisão confirma a disponibilidade local e a integridade contábil da versão recebida, não promete que ela seja a última versão atualmente servida em todos os nós de cache. O parecer não contém avaliação de candidaturas ou desempenho político, nem atribui causa à abstenção. O painel de votação e seus arquivos publicados permanecem fora do escopo de alteração. Qualquer promoção futura deve reconciliar também as fontes específicas exigidas pela funcionalidade que será publicada.

## Liberação do pacote documental

Conferência final em 26/10/2026 12:52:54 -0300. O texto de `reports/ATUALIZACAO_SEGUNDO_TURNO.md` foi revisado: cobertura, seis métricas, exceções, percentuais territoriais e arredondamentos coincidem com a auditoria. A descrição sobre o arquivo nominal foi limitada aos metadados retornados na consulta das 12h45 e à ausência de nova versão nominal obtida nesta atualização. Não afirma inexistência global de atualização no servidor.

A igualdade de SHA256 entre `resposta_cache_antiga.zip` e o ZIP original preservado foi reconferida independentemente: ambos `11a62c3a604e8b73fc328617b7688d2c635de1c76df02ba63b8f77879512f573`. O histórico específico das respostas HTTP permanece fundamentado no registro do coletor; não foi repetido pelo revisor.

Liberados para publicação os scripts revisados, o QA, o CSV territorial, este parecer e o relatório da atualização, no escopo descritivo e contábil acima. Esta liberação não inclui uma base integrada completa, nem substituição dos dados ou do aplicativo de votação.
