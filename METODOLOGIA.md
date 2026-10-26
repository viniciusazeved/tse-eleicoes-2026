# Comparecimento e votação presidencial de 2026

## Pergunta e alcance

Investigar se seções com maior comparecimento apresentam maior participação de votos para cada candidatura e como essa associação muda dentro da mesma geografia. Trata-se de análise observacional do censo de registros publicados. Uma associação não identifica votos em nome de ausentes, nem sua ausência exclui irregularidade localizada.

## Universo e integridade

Somente Presidência e eleição ordinária de 2026. Os turnos são tratados separadamente e só comparados quando ambos estiverem disponíveis. Dados brutos oficiais preservados com URL, horário de coleta, versão e hash. A chave de seção é turno, UF, código TSE do município, zona e seção. Códigos TSE de município não são códigos IBGE. Exterior é separado do território brasileiro. Conferir duplicações, situações de totalização, registros faltantes e junção dos arquivos antes de inferir resultados. Seções agregadas, transferências e alterações cadastrais podem limitar o pareamento.

O catálogo oficial alerta sobre 39 registros de transferências temporárias também vinculados às seções de origem. Os totais extraídos serão preservados e essa diferença documentada; não haverá dedução arbitrária em seções desconhecidas.

## Indicadores

Comparecimento dividido por aptos mede participação; abstenção dividida por aptos mede ausência. Votos do candidato divididos por votos presidenciais válidos medem sua participação na disputa. Também são apresentados votos por comparecente e por apto. A razão votos/aptos contém mecanicamente a participação e não é evidência independente de irregularidade. Aptos, comparecimento e abstenção não podem ser somados repetidamente a partir das linhas de candidatos.

## Análises previamente definidas

1. Totais por turno, UF, município, zona e seção; distribuição de participação; votos de todos os candidatos, brancos e nulos.
2. Pearson e Spearman entre participação e apoio entre válidos; resultados nacionais e por UF. São descrições, sem interpretação causal.
3. Regressões com efeito fixo de município e de local de votação, quando disponível, controlando logaritmo de aptos e seu quadrado. Versões com peso igual por seção e ponderadas pelos votos válidos. A inclinação é apresentada em pontos percentuais de apoio por dez pontos percentuais de participação. Locais sem variação não identificam a inclinação. Identificação de local inclui município e zona.
4. Intervalos de 95% com erros agrupados por município, como incerteza do modelo, não erro amostral do censo. Não usar significância como probabilidade de fraude. Candidatos do segundo turno são complementares, não testes independentes.
5. Cortes de participação de 90%, 95%, 98% e 100%, fixados antes de observar resultados. Apresentar tamanho, composição territorial e votos de cada grupo. Cortes cumulativos não podem ser somados entre si. Faixas exclusivas complementam os cortes.
6. Sensibilidade ao tamanho das seções: repetir modelos em seções com pelo menos 100 aptos. Seções menores não são apagadas da base.
7. Se ambos os turnos forem publicados, parear a chave completa e apresentar cobertura; análise principal restrita a aptos e local iguais, sem presumir identidade do eleitorado. Mudanças de votos incluem migração dos candidatos eliminados. Não atribuir os ganhos aos eleitores adicionais.

## Operacionalização do pareamento

A junção dos turnos é um para um pela chave UF, município TSE, zona e seção, com cobertura e chaves exclusivas registradas. Todas as chaves elegíveis exigem aptos e votos válidos positivos nos dois turnos. O recorte principal exige ainda aptos iguais e código de local válido e igual; dois valores ausentes ou sentinelas não constituem igualdade de local. Exterior e território brasileiro são apresentados separadamente. Contagens de exclusão por aptos, local e denominadores podem se sobrepor.

As diferenças de comparecimento e de participação de cada finalista entre os válidos são calculadas por seção. Pearson e Spearman descrevem a associação entre essas diferenças. A média de diferenças por seção é identificada separadamente da diferença entre razões de totais agregados. Variações de votos e de comparecimento não identificam a preferência dos eleitores adicionais, nem a origem individual dos ganhos dos finalistas.

O recorte regional dos cortes de alto comparecimento usa as cinco regiões do IBGE e explicita dois denominadores: o conjunto nacional de seções que atende ao corte e os votos válidos somados nas seções da região dentro do corte. As análises de apoio exigem votos válidos positivos; as tabelas exclusivamente de abstenção não precisam desse denominador.

## Horários

A nota oficial do TSE de 25/10/2026 confirma prorrogação excepcional nas seções ainda não encerradas às 17h e retomada da divulgação depois das 19h. Esse fato deve ser considerado no segundo turno, além da regra ordinária de atendimento à fila.

Horário do último voto, encerramento da urna, geração do boletim, recepção e divulgação são eventos diferentes. A análise temporal exige logs, interpretação do evento e validação de fuso e relógio. O arquivo do segundo turno pode conter histórico do primeiro: a data exata de votação deve ser filtrada. Logs não revelam a escolha do eleitor e o RDV não fornece correspondência cronológica. Não é possível afirmar que votos depois das 17h foram para um candidato a partir desses arquivos. Uma extensão futura pode contar eventos de votação e construir limites aritméticos, jamais uma atribuição observada de candidato.

## Limitações de interpretação

Idade, escolaridade, urbanização, mobilidade, campanhas, transporte e composição do cadastro podem afetar comparecimento e preferência. Controles geográficos não eliminam todos esses fatores. Pontos extremos são locais para esclarecimento documental, não acusações. Evidência sobre voto em nome de ausentes exigiria confrontar presença e identificação com documentação independente, atas e ocorrências verificadas.

## Fontes

- [Resultados oficiais de 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026)
- [Boletins de urna de 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna)
- [Nota oficial sobre a prorrogação de 25/10](https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/esclarecimento-sobre-prorrogacao-da-votacao)
- [Explicação da Justiça Eleitoral sobre sigilo e logs](https://www.justicaeleitoral.jus.br/fato-ou-boato/checagens/2024/codigo-fonte-da-urna-eletronica-nao-revela-voto-do-eleitorado)

Plano revisto por agente Astra independente antes dos cálculos. Desvios decorrentes da disponibilidade dos dados devem constar no relatório.
