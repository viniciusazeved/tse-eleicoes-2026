# Revisão independente: ingestão, análise e painel presidencial de 2026

Revisor: agente Astra independente do agente implementador. Conferência encerrada em 26/10/2026, 07:31:32, horário de Brasília. Escopo: arquivos `scripts/ingest.py`, `scripts/analyze.py`, `scripts/fetch_zonas.py`, `scripts/analyze_zones.py`, `app.py`, fontes brutas e relatórios. O revisor alterou somente este parecer e `tests/test_review.py`.

## Resumo

- Crítico pendente no snapshot auditado: 0.
- Atenção: 1, relativa à documentação de funções públicas.
- Sugestão: 1.

Veredicto: aprovado com ressalvas para a apresentação descritiva deste snapshot. Primeiro turno disponível por seção; segundo turno auditado apenas por município/zona. Boletins individuais do segundo turno existem, mas o pacote nacional consolidado por seção ainda não estava disponível nesta coleta. Não há liberação de afirmações sobre voto individual, votos depois das 17h, causalidade ou fraude. A implantação e o comportamento visual do Streamlit não fazem parte deste parecer numérico.

## Conferência na fonte

O Ruff foi executado antes da análise manual e passou nos cinco arquivos de produção. Foram criados cinco testes independentes, executados por etapas, com aprovação. Os testes não importam os scripts de ingestão nem os estimadores implementados. A comparação numérica usa tolerância absoluta de 1e-12 para correlações e 1e-8 para coeficientes e limites dos intervalos em pontos percentuais.

Primeiro turno: os dois ZIPs oficiais foram relidos. Todos os 499.248 registros de seção foram reconciliados pela chave turno, UF, município TSE, zona e seção, incluindo aptos, comparecimento, abstenção, válidos, brancos, nulos, código de local e votos de Lula, Flávio Bolsonaro e demais candidaturas. A conferência foi integral, não amostral. Os arquivos relidos contêm Presidente, ano 2026 e eleição ordinária. A ausência de linha de candidatura só vira zero após a reconciliação integral dos votos por seção. As 42 seções sem linha nominal têm comparecimento zero; 41 são não instaladas no exterior, com 423 aptos, e uma está marcada como instalada.

Segundo turno: os 6.292 JSONs EA20 de município/zona foram relidos e comparados campo a campo com o Parquet. Todos têm eleição 6258, turno 2, fase oficial, totalização final e andamento final. As chaves coincidem integralmente com o EA16. As somas de aptos, comparecimento, abstenção e válidos conciliam com as referências BR e de cada UF. Válidos equivalem à soma das duas candidaturas em todas as zonas. Comparecimento equivale a válidos, brancos e nulos em todas as zonas. Comparecimento mais abstenção equivale a `e.esi`, eleitorado das seções instaladas, em todos os JSONs.

Os 423 aptos de seções não instaladas no exterior estão em 40 chaves município/zona e explicam integralmente o saldo cadastral. O saldo foi também confrontado com as seções não instaladas do primeiro turno. A taxa analítica usa comparecimento/aptos de todo o cadastro; no exterior, não se deve apresentá-la como reprodução da taxa oficial baseada em eleitorado instalado. Não foram fabricadas abstenções para fechar o cadastro.

Hashes SHA256 dos arquivos auditados:

| Arquivo | SHA256 |
| :-- | :-- |
| `data/processed/secoes.parquet` | `6d02fb1711f1d7eabcd834f0c1fa5c4cfe6937ac7d333bfdc9d06e6d4d851b96` |
| `data/processed/zonas_turno2.parquet` | `ac3b9d4206fcc9ba960907b886f8d8a1c6845bfc7c59da7152385456f9dc9aa2` |

## Números auditados

Totais no território brasileiro, excluindo exterior:

| Indicador | Primeiro turno | Segundo turno |
| :-- | --: | --: |
| Aptos | 157.828.968 | 157.828.819 |
| Comparecimento | 124.934.069 | 127.854.631 |
| Abstenção | 32.894.899 | 29.974.188 |
| Válidos | 118.975.029 | 123.710.622 |
| Lula | 53.722.151 | 64.056.078 |
| Flávio Bolsonaro | 55.960.603 | 59.654.544 |
| Comparecimento/aptos | 79,157882% | 81,008419% |
| Lula/válidos | 45,154140% | 51,778964% |

No primeiro turno, Brasil mais exterior soma 53.879.538 votos para Lula e 56.104.503 para Flávio Bolsonaro. Os nomes foram conferidos nas linhas nominais. Não confundir o candidato de número 22 em 2026 com Jair Bolsonaro.

Primeiro turno, 497.897 seções do Brasil: Pearson entre comparecimento/aptos e Lula/válidos = 0,068486308602; Spearman = 0,064700882238. A correlação nacional é descritiva, sem ajuste territorial.

Os modelos com efeito fixo de local foram recalculados com solver de mínimos quadrados independente, após absorção ponderada dos efeitos fixos. O local inclui UF, município, zona e código de local. Controles: logaritmo de aptos e seu quadrado. Erros agrupados por município e correção finita de graus de liberdade conforme a implementação auditada. A amostra identificadora contém 476.122 seções em 72.353 locais e 5.570 municípios; locais sem variação de participação são removidos da estimação. Intervalos são incerteza do modelo, não erro amostral de um censo.

| Peso do modelo local | pp de apoio por 10 pp de participação | IC95 inferior | IC95 superior |
| :-- | --: | --: | --: |
| Igual por seção | -0,4271588323 | -0,5694854058 | -0,2848322588 |
| Votos válidos | -0,4550758421 | -0,6076676823 | -0,3024840019 |

O fator de conversão está correto: coeficiente de fração/fração multiplicado por 10 resulta em pontos percentuais de apoio por dez pontos percentuais de participação. Os dois resultados locais têm sinal diferente da associação nacional; isso impede interpretar a correlação bruta como mecanismo individual.

No primeiro turno, cortes cumulativos de participação de 90%, 95%, 98% e 100% contêm, respectivamente, 8.299, 559, 60 e 15 seções brasileiras. Aptos correspondentes: 2.024.189, 86.403, 5.942 e 1.031. Os totais e as participações de Lula nos cortes foram conferidos diretamente. Os grupos extremos são pequenos e seletivos; não são categorias de fraude. Os cortes não podem ser somados.

Na comparação entre turnos, todas as 6.292 chaves município/zona são pareadas, sem chaves exclusivas de um turno. São 6.106 no Brasil e 186 no exterior. As doze correlações publicadas em `resumo_zonas2.json`, de ambos os candidatos e universos, foram conferidas por cálculo independente a partir dos JSONs e da agregação do primeiro turno.

| Comparação de Lula no Brasil | n | Pearson | Spearman |
| :-- | --: | --: | --: |
| Entre zonas no primeiro turno | 6.106 | 0,025967186805 | 0,045339716389 |
| Entre zonas no segundo turno | 6.106 | -0,061026812941 | -0,038205000608 |
| Mudanças entre turnos, zonas com aptos iguais | 1.878 | 0,026225251502 | 0,081865015008 |

Mesmos aptos não garantem as mesmas pessoas. A mudança entre turnos também inclui a redistribuição dos votos das candidaturas eliminadas. No segundo turno, Lula e Flávio têm participações complementares entre válidos, portanto suas correlações opostas não são testes independentes. A comparação por seção continua pendente da obtenção e reconciliação de uma base nacional consolidada do segundo turno. A existência de boletins individuais não equivale a um censo nacional já coletado e auditado.

## Achados corrigidos durante a revisão

1. O pareamento inicial de zonas comparava identificadores textuais com zeros à esquerda diferentes. A interface agora normaliza os códigos numéricos nos dois lados. A reconciliação independente confirmou cobertura completa.
2. A comparação futura por seção inicialmente aceitava somente igualdade da chave. Agora exige aptos e código de local iguais e informa a cobertura, conforme a metodologia.
3. A interface inicialmente aceitava a existência do Parquet de segundo turno antes da conclusão do QA. Agora exige `apto_para_auditoria` e SHA256 compatível.
4. O primeiro QA de zonas comparava comparecimento mais abstenção com eleitorado totalizado. O campo correto é eleitorado das seções instaladas, `e.esi`. A correção foi conferida em todos os JSONs.
5. O pipeline de primeiro turno não interrompia a promoção de seções após falhas contábeis no QA. Foi adicionado bloqueio para votos sem detalhe, duplicações, divergências contábeis e contagens negativas, com exceção explícita das seções não instaladas no exterior.

6. A atualização inicialmente substituía `votos.parquet` antes do QA. Agora usa `votos.candidato.parquet`, promovido somente após as validações. A publicação é de um snapshot Git completo, não uma atualização concorrente de arquivos no painel.

O relatório `reports/RELATORIO.md` foi conferido: tabelas, arredondamentos, tamanhos das amostras e narrativa são compatíveis com os resultados auditados. A pendência do pacote nacional de seções do segundo turno e a ausência de censo nacional de eventos de log estão explicitadas.

## Achados de manutenção

### Funções públicas sem docstrings

Arquivos: `scripts/analyze.py`, funções `aggregate` e `main`; `scripts/analyze_zones.py`, função `main`; funções de consulta, formatação e gráficos em `app.py`. As assinaturas possuem type hints, mas parte das funções públicas não documenta seu contrato.

Correção sugerida:

```python
def aggregate(d: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Soma contagens por chaves e calcula razões com denominadores agregados."""
    ...
```

### Separar geração de relatórios da estimação

Arquivo: `scripts/analyze.py`, função `main`, a partir da linha 123. A função reúne agregações, cortes, correlações, modelos e persistência. Uma separação futura reduz o risco de atualizar apenas parte dos relatórios.

Antes:

```python
def main() -> None:
    # Agregações, cortes, correlações, modelos e escrita no mesmo fluxo.
    ...
```

Depois:

```python
def main() -> None:
    secoes = carregar_secoes_validadas()
    relatorios = calcular_relatorios(secoes)
    validar_relatorios(relatorios)
    publicar_versao(relatorios)
```

## Limites do parecer

Não houve leitura de logs de votação para quantificar eventos após 17h, nem atribuição temporal de votos por candidato. A explicação de horários deve manter a distinção entre evento de voto, encerramento, geração de boletim, recepção e divulgação. Os testes não verificam autenticidade do voto individual; verificam fidelidade da transformação dos arquivos oficiais e consistência dos cálculos.

Conclusão: snapshot numérico aprovado para análise observacional, com uma atenção e uma sugestão de manutenção acima. Qualquer mudança de fonte, código de estimação ou denominador exige nova conferência das partes afetadas.
