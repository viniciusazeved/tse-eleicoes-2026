# Observatório do voto 2026

Dados públicos do TSE sobre comparecimento e votação para Presidente, com exploração por seção, zona, município e UF. Projeto independente, sem vínculo institucional com a Justiça Eleitoral.

[Abrir o painel publicado](https://observatorio-voto-2026.streamlit.app/~/+/) · [Ler o relatório](reports/RELATORIO.md) · [Conferência dos dois turnos](docs/REVISAO_DOIS_TURNOS_SECAO.md)

O link usa o acesso direto à aplicação, conferido visualmente na nuvem. Na publicação de 26/10, a página externa do Streamlit permaneceu no carregamento, enquanto o acesso direto funcionou. Registro da versão e da conferência: [snapshot_publicado.json](reports/snapshot_publicado.json).

A hipótese examinada é a associação entre participação eleitoral e apoio às candidaturas. Padrões estatísticos não identificam voto em nome de ausentes. Horários dos logs não revelam candidato. Consulte [METODOLOGIA.md](METODOLOGIA.md).

## Cobertura

O snapshot consolidado de 26/10/2026 contém os dois turnos presidenciais por seção, com Brasil e exterior identificados separadamente. A base de município/zona, coletada anteriormente, permanece como referência de conciliação e camada complementar. O pareamento entre turnos explicita cobertura, diferenças de aptos e de local, sem presumir identidade dos eleitores.

## Executar

Python 3.12 e uv:

```powershell
uv sync
uv run streamlit run app.py
```

Os Parquets e relatórios publicados bastam para executar o painel. Os ZIPs e JSONs originais ficam no arquivo local de auditoria, com URLs e hashes documentados em [fontes.json](reports/fontes.json) e [QA da integração](reports/qa_integracao_20261026-144303.json). Para reproduzir a integração e a análise, com esses originais preservados:

```powershell
uv run python scripts/stage_nominal_update.py
uv run python scripts/analyze.py --data-dir data/interim/20261026-144303 --reports-dir data/interim/20261026-144303/reports --database data/interim/20261026-144303/tse2026.duckdb
```

O primeiro comando tem caminhos versionados explícitos para o detalhe e a votação nominal deste snapshot; todos podem ser substituídos por argumentos descritos em `--help`. Os resultados ficam em staging até a revisão. O importador inicial `scripts/ingest.py --skip-download` continua disponível, mas seus padrões apontam para o arquivo inicial e não devem substituir esta versão consolidada. O script `scripts/fetch_zonas.py` coleta os JSONs oficiais por zona com cache e concorrência limitada. Não é necessário repetir essa coleta para abrir o painel.

Os testes em `tests/test_review.py` reabrem as fontes brutas quando estão disponíveis. Os demais testes verificam o cálculo de efeitos fixos, as regras de pareamento e a interface. Novas versões exigem conferência de integridade, cobertura, somas e revisão antes de publicar conclusões.

## Organização

- `data/raw`: ZIPs originais, JSONs oficiais e manifesto de origem; preservados localmente.
- `data/processed/secoes.parquet`: uma linha por seção e turno.
- `data/processed/votos.parquet`: linhas de votação publicadas, incluindo brancos e nulos.
- `data/processed/zonas_turno2.parquet`: segundo turno por zona, quando coletado.
- `data/processed/pareamento_secoes.parquet`: seções presentes nos dois turnos, com critérios de elegibilidade e diferenças.
- `data/tse2026.duckdb`: banco local com tabelas para consultas SQL.
- `reports`: resultados descritivos, correlações, modelos e QA.
- `docs`: parecer metodológico e documentação de horários.

Códigos de município são códigos eleitorais TSE, não códigos IBGE. O exterior é identificado por ZZ. As taxas entre válidos são indefinidas nas seções sem votos válidos, nunca substituídas por zero. Aptos repetidos em linhas de candidato não são somados.

## Reprodutibilidade

Os ZIPs mantêm o hash SHA-256 e as URLs do TSE. O banco preserva exceções da origem. Os intervalos dos modelos refletem incerteza da especificação, não erro amostral da eleição observada. Não há estimativa de probabilidade de fraude ou lista de responsáveis.

Dados: [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026), licença de atribuição indicada pelo portal. As escolhas de método e as limitações estão documentadas junto ao código.
