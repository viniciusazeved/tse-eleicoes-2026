# Parecer independente de método

Autor: subagente Astra de revisão. Atualizado em 2026-10-26 07:14:17 -03:00. Escopo autorizado: presidência, Brasil, eleição de 2026, dois turnos. Sem resultados eleitorais quantitativos neste parecer.

## Decisão

Concordo com investigação descritiva de associação entre participação e apoio aos candidatos, condicionada às verificações abaixo. A hipótese de voto em nome de ausentes não é identificável apenas pelos resultados agregados. Associação residual pode orientar investigação documental, mas não confirma nem exclui esse mecanismo.

## Plano aprovado com correções

1. Fixar universo, turno, data de extração, versão e cobertura. Preservar fontes oficiais e hashes. Auditar duplicatas, reprocessamentos, seções agregadas, urnas substituídas e situação de totalização. Aptos e comparecimento repetidos em linhas de candidatos entram uma única vez por seção.
2. Definir A=aptos; C=comparecimento; V=válidos presidenciais; L=votos do candidato. Participação=C/A; abstenção=(A-C)/A; apoio entre válidos=L/V. Mostrar também L/C e L/A, mas explicar o componente mecânico de L/A: mantendo preferência constante, maior participação aumenta votos por apto. Conferir no leiaute se C coincide com votantes presidenciais e tratar diferenças reais.
3. Aplicar as mesmas análises a todos os candidatos, brancos e nulos. Segundo turno: proporções dos finalistas entre válidos são complementares e seus testes não são evidências independentes. Identidade e número de candidato devem vir da base real.
4. Apresentar associação nacional bruta e dentro de UF, município e local de votação. Modelo principal com efeito fixo de local, ajuste flexível pelo tamanho da seção e comparação entre seções do mesmo local. Município como alternativa documentada. Informar exclusão de locais sem variação ou com seção única. Escolaridade, idade, urbanização, cadastro, transporte e mobilização permanecem confundidores possíveis.
5. Mostrar inclinação em pontos percentuais de apoio por 10 pontos percentuais de participação. Versões ponderada pelos válidos e não ponderada respondem a perguntas diferentes. Usar agrupamento por município nos intervalos do modelo. Em censo completo, tais intervalos não representam erro amostral dos totais observados. Priorizar magnitude e estabilidade, não significância isolada.
6. Fixar previamente faixas de participação >=90%, >=95%, >=98% e 100%, acompanhadas de cortes exclusivos para evitar dupla contagem interpretativa. Informar seções, aptos, comparecentes, votos e abrangência geográfica. Seções pequenas atingem extremos mais facilmente. Não escolher cortes depois dos resultados.
7. Parear por chave completa, verificando composição e eleitorado entre turnos. Diferenças dentro de seção podem receber efeitos de município/local e apoio inicial como sensibilidade. Mudança entre turnos também incorpora transferência de votos dos eliminados. Não atribuir preferência aos eleitores adicionais, aos ausentes ou aos votantes tardios.
8. Não transformar resíduos, extrapolações ou cenários em contagens de votos fraudulentos. Conclusões sobre personificação exigem evidência independente e verificada de presença, identificação, atas ou ocorrências.

## Correção factual sobre horários

A nota oficial do TSE de 25/10/2026 informa que a votação continuava somente nos locais que não haviam encerrado às 17h e que recebimento de BUs, totalização e divulgação seriam retomados após as 19h. A análise do segundo turno deve incorporar essa situação excepcional. Não basta aplicar a explicação ordinária de continuidade da fila. Fonte: [nota TSE sobre prorrogação](https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/esclarecimento-sobre-prorrogacao-da-votacao).

Horário de voto concluído, encerramento, geração do BU, recebimento e totalização são eventos diferentes. Logs e RDV não permitem vincular escolha do candidato ao horário individual. Fonte: [explicação da Justiça Eleitoral sobre log e RDV](https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2024/codigo-fonte-da-urna-eletronica-nao-revela-voto-do-eleitorado).

O procedimento técnico e suas pendências estão em [HORARIOS.md](HORARIOS.md).

## Limite da aprovação

Parecer de método aprovado. Nenhum resultado quantitativo foi ratificado nesta etapa. Conferência independente posterior deve consultar arquivos brutos e reproduzir somas, denominadores, exclusões e estimativas principais.

## Adendo técnico de 2026-10-26 07:25:36 -03:00

Foi implementada coleta oficial do segundo turno por município/zona, em `scripts/fetch_zonas.py`, preservando unidade agregada. O primeiro turno pode ser agregado à mesma chave para comparação entre turnos; não se deve apresentar os dados de zona como se fossem seções nem aplicar a eles comparação dentro do local de votação. Resultados continuam sujeitos à auditoria independente da raiz.

Correção de denominador confirmada no leiaute [EA20, páginas 18 e 19](https://www.tse.jus.br/eleicoes/eleicoes-2026-content/arquivos/divulgacao-de-resultados/tse-ea20-arquivo-de-resultado-unificado): aptos totais (`e.te`) incluem eleitorado de seções não instaladas; comparecimento e abstenção são relativos às instaladas (`e.esi`). Logo `C+A=e.esi`, não necessariamente `e.te` nem `e.est`. O Parquet mantém aptos originais e acrescenta `eleitores_instaladas` e `eleitores_nao_instaladas`. As taxas oficiais usam o eleitorado instalado; seções não instaladas não devem ser classificadas como abstenção total. Ao analisar seção instalada, verificar essa igualdade na fonte.
