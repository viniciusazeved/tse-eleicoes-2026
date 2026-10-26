# Observatório do voto 2026

Dados públicos do TSE sobre comparecimento e votação para Presidente, com exploração por seção, zona, município e UF. Projeto independente, sem vínculo institucional com a Justiça Eleitoral.

[Abrir o painel publicado](https://observatorio-voto-2026.streamlit.app/) · [Ler o relatório inicial](reports/RELATORIO.md) · [Conferência independente](docs/REVISAO_INDEPENDENTE.md)

A hipótese examinada é a associação entre participação eleitoral e apoio às candidaturas. Padrões estatísticos não identificam voto em nome de ausentes. Horários dos logs não revelam candidato. Consulte [METODOLOGIA.md](METODOLOGIA.md).

## Cobertura inicial

Os arquivos nacionais por seção disponíveis na coleta de 26/10/2026 continham somente o primeiro turno. A aplicação mostra apenas os turnos efetivamente importados. Dados do segundo turno por zona, quando presentes, aparecem em camada própria, sem serem apresentados como dados por seção. A ausência do pacote nacional não significa ausência de resultados oficiais ou de boletins individuais.

## Executar

Python 3.12 e uv:

```powershell
uv sync
uv run python scripts/ingest.py
uv run python scripts/analyze.py
uv run streamlit run app.py
```

Para reconstruir com os ZIPs já arquivados, usar `scripts/ingest.py --skip-download`. O script `scripts/fetch_zonas.py` coleta os JSONs oficiais do segundo turno por zona, com cache e concorrência limitada. Novas versões exigem conferência de integridade, cobertura, somas e revisão antes de publicar conclusões.

## Organização

- `data/raw`: ZIPs originais, JSONs oficiais e manifesto de origem; preservados localmente.
- `data/processed/secoes.parquet`: uma linha por seção e turno.
- `data/processed/votos.parquet`: linhas de votação publicadas, incluindo brancos e nulos.
- `data/processed/zonas_turno2.parquet`: segundo turno por zona, quando coletado.
- `data/tse2026.duckdb`: banco local com tabelas para consultas SQL.
- `reports`: resultados descritivos, correlações, modelos e QA.
- `docs`: parecer metodológico e documentação de horários.

Códigos de município são códigos eleitorais TSE, não códigos IBGE. O exterior é identificado por ZZ. As taxas entre válidos são indefinidas nas seções sem votos válidos, nunca substituídas por zero. Aptos repetidos em linhas de candidato não são somados.

## Reprodutibilidade

Os ZIPs mantêm o hash SHA-256 e as URLs do TSE. O banco preserva exceções da origem. Os intervalos dos modelos refletem incerteza da especificação, não erro amostral da eleição observada. Não há estimativa de probabilidade de fraude ou lista de responsáveis.

Dados: [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026), licença de atribuição indicada pelo portal. As escolhas de método e as limitações estão documentadas junto ao código.
