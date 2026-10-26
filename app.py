from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
SECOES_PATH = APP_DIR / "data" / "processed" / "secoes.parquet"
VOTOS_PATH = APP_DIR / "data" / "processed" / "votos.parquet"
ZONAS_TURNO2_PATH = APP_DIR / "data" / "processed" / "zonas_turno2.parquet"
QA_ZONAS_TURNO2_PATH = APP_DIR / "reports" / "qa_zonas_turno2.json"
QA_EXCECOES_PATH = APP_DIR / "data" / "processed" / "qa_excecoes.csv"
PAREAMENTO_PATH = APP_DIR / "data" / "processed" / "pareamento_secoes.parquet"
PAREAMENTO_RELATORIO_PATH = APP_DIR / "reports" / "pareamento_secoes.csv"
CORTES_REGIOES_PATH = APP_DIR / "reports" / "cortes_regioes.csv"
METODOLOGIA_PATH = APP_DIR / "METODOLOGIA.md"
RESUMO_PATH = APP_DIR / "reports" / "resumo.json"
MODELOS_PATH = APP_DIR / "reports" / "modelos.csv"

PETROLEO = "#123C4A"
AZUL = "#287C91"
OCRE = "#C58A2B"
AZUL_CLARO = "#8AB7C2"
CINZA = "#687881"
FUNDO = "#F4F7F8"
GRADE = "#DCE5E8"

COLUNAS_OBRIGATORIAS = {
    "turno",
    "uf",
    "municipio_codigo",
    "municipio_nome",
    "zona",
    "secao",
    "aptos",
    "comparecimento",
    "abstencao",
    "validos",
    "brancos",
    "nulos",
    "lula",
    "bolsonaro",
    "outros",
    "participacao",
    "lula_validos",
    "bolsonaro_validos",
    "lula_aptos",
    "bolsonaro_aptos",
}


st.set_page_config(
    page_title="Observatório do voto 2026",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap');
    :root {{ --petroleo: {PETROLEO}; --azul: {AZUL}; --ocre: {OCRE}; --fundo: {FUNDO}; }}
    html, body, [class*="css"] {{ font-family: "Source Sans 3", sans-serif; color: #1F3037; }}
    .stApp {{ background: linear-gradient(180deg, #FFFFFF 0, #FFFFFF 18rem, {FUNDO} 18rem); }}
    [data-testid="stHeader"] {{ background: rgba(255,255,255,.92); }}
    [data-testid="stSidebar"] {{ background: #EAF0F2; border-right: 1px solid {GRADE}; }}
    [data-testid="stSidebar"] h2 {{ color: {PETROLEO}; letter-spacing: -.02em; }}
    .block-container {{ max-width: 1440px; padding-top: 2.2rem; padding-bottom: 4rem; }}
    .hero {{ border-left: 7px solid {OCRE}; padding: .25rem 0 .35rem 1.25rem; margin: .3rem 0 1.6rem; max-width: 980px; }}
    .hero h1 {{ color: {PETROLEO}; font-size: clamp(2.2rem, 5vw, 4.5rem); line-height: .96; letter-spacing: -.055em; margin: 0 0 .7rem; font-weight: 700; }}
    .hero p {{ font-size: 1.16rem; line-height: 1.45; margin: 0; max-width: 760px; color: #435861; }}
    .question {{ background: {PETROLEO}; color: white; padding: 1.05rem 1.3rem; margin: .4rem 0 1.5rem; font-size: 1.15rem; line-height: 1.45; }}
    .question strong {{ color: #F2C46D; font-weight: 600; }}
    .section-title {{ color: {PETROLEO}; font-size: 1.55rem; letter-spacing: -.025em; margin: 1.4rem 0 .15rem; font-weight: 650; }}
    .section-note {{ color: #52666F; max-width: 820px; margin: 0 0 1rem; line-height: 1.45; }}
    [data-testid="stMetric"] {{ background: #FFFFFF; border-top: 3px solid {AZUL}; padding: .85rem 1rem .7rem; }}
    [data-testid="stMetricLabel"] {{ color: #52666F; font-size: .94rem; }}
    [data-testid="stMetricValue"] {{ color: {PETROLEO}; letter-spacing: -.025em; }}
    div[data-testid="stAlert"] {{ border-radius: 2px; }}
    .qa-ok, .qa-warn {{ padding: .7rem .9rem; border-left: 4px solid {AZUL}; background: #EEF5F6; margin: .4rem 0; }}
    .qa-warn {{ border-left-color: {OCRE}; background: #FBF5E9; }}
    .method-box {{ background: white; border: 1px solid {GRADE}; padding: 1rem 1.2rem; line-height: 1.5; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 1.5rem; border-bottom: 1px solid {GRADE}; }}
    .stTabs [data-baseweb="tab"] {{ padding-left: 0; padding-right: 0; }}
    .stTabs [aria-selected="true"] {{ color: {PETROLEO}; font-weight: 650; }}
    .stButton button, .stDownloadButton button {{ border-radius: 2px; border-color: {PETROLEO}; color: {PETROLEO}; }}
    .stButton button:focus-visible, .stDownloadButton button:focus-visible {{ outline: 3px solid #E5B958; outline-offset: 2px; }}
    @media (max-width: 700px) {{
      .block-container {{ padding: 1.2rem .9rem 3rem; }}
      .hero h1 {{ font-size: 2.7rem; }}
      .hero {{ margin-bottom: 1rem; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto !important; transition: none !important; }} }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _fingerprint(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


@st.cache_data(show_spinner=False, max_entries=8)
def calcular_sha256(caminho: str, fingerprint: tuple[int, int]) -> str:
    del fingerprint
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def validar_qa_zonas() -> tuple[bool, str]:
    if not ZONAS_TURNO2_PATH.exists():
        return (
            False,
            "A base oficial agregada do 2º turno por zona ainda não está disponível.",
        )
    if not QA_ZONAS_TURNO2_PATH.exists():
        return (
            False,
            "A camada por zona existe, mas o relatório obrigatório de QA ainda não foi publicado.",
        )
    try:
        qa = json.loads(QA_ZONAS_TURNO2_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False, "O relatório de QA da camada por zona não pôde ser lido."
    if qa.get("apto_para_auditoria") is not True:
        return (
            False,
            "A camada por zona ainda não foi liberada pelo controle de qualidade.",
        )
    sha_esperado = str(qa.get("sha256_parquet", "")).strip().lower()
    if not sha_esperado:
        return False, "O relatório de QA não informa o SHA256 do Parquet."
    sha_observado = calcular_sha256(
        str(ZONAS_TURNO2_PATH), _fingerprint(ZONAS_TURNO2_PATH)
    )
    if sha_observado != sha_esperado:
        return False, "O SHA256 da camada por zona não coincide com o relatório de QA."
    return True, "Dados por zona conferidos com os totais oficiais do TSE."


@st.cache_data(show_spinner=False, max_entries=48)
def consultar(
    sql: str, parametros: tuple, fingerprint: tuple[int, int]
) -> pd.DataFrame:
    del fingerprint
    with duckdb.connect() as con:
        return con.execute(sql, list(parametros)).fetch_df()


def formatar_inteiro(valor: float) -> str:
    return f"{int(valor):,}".replace(",", ".")


def formatar_percentual(valor: float | None, casas: int = 1) -> str:
    if valor is None or pd.isna(valor):
        return "Sem base"
    return f"{100 * float(valor):.{casas}f}%".replace(".", ",")


def nome_candidato(numero: str, nome: str) -> str:
    conhecidos = {
        "13": "Luiz Inácio Lula da Silva",
        "22": "Flávio Bolsonaro",
    }
    if numero in conhecidos:
        return conhecidos[numero]
    palavras_menores = {"da", "de", "do", "das", "dos", "e"}
    partes = str(nome).strip().lower().split()
    return " ".join(p if p in palavras_menores else p.capitalize() for p in partes)


def layout_grafico(fig: go.Figure, altura: int = 390) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin={"l": 20, "r": 20, "t": 105, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font={"family": "Source Sans 3", "color": "#263A42", "size": 14},
        title={
            "font": {"color": PETROLEO, "size": 18},
            "y": 0.98,
            "yanchor": "top",
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.08,
            "xanchor": "left",
            "x": 0,
        },
        hoverlabel={"bgcolor": "#FFFFFF", "font_color": "#263A42"},
    )
    fig.update_xaxes(gridcolor=GRADE, zeroline=False, title_standoff=12)
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, title_standoff=12)
    return fig


def cabecalho_secao(titulo: str, nota: str) -> None:
    st.markdown(f'<div class="section-title">{titulo}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-note">{nota}</div>', unsafe_allow_html=True)


def esquema_disponivel() -> tuple[set[str], list[str]]:
    sql = f"DESCRIBE SELECT * FROM read_parquet('{_sql_path(SECOES_PATH)}')"
    frame = consultar(sql, (), _fingerprint(SECOES_PATH))
    colunas = set(frame["column_name"].astype(str))
    return colunas, sorted(COLUNAS_OBRIGATORIAS - colunas)


def clausula_filtro(
    turno: int | None,
    uf_escolhida: str,
    municipio_codigo: str | None,
    alias: str = "",
) -> tuple[str, tuple]:
    p = f"{alias}." if alias else ""
    partes: list[str] = []
    parametros: list[object] = []
    if turno is not None:
        partes.append(f"{p}turno = ?")
        parametros.append(int(turno))
    if uf_escolhida == "Brasil sem exterior":
        partes.append(f"{p}uf <> 'ZZ'")
    elif uf_escolhida == "Exterior (ZZ)":
        partes.append(f"{p}uf = 'ZZ'")
    else:
        partes.append(f"{p}uf = ?")
        parametros.append(uf_escolhida)
    if municipio_codigo:
        partes.append(f"TRY_CAST({p}municipio_codigo AS BIGINT) = ?")
        parametros.append(int(municipio_codigo))
    return " AND ".join(partes) if partes else "TRUE", tuple(parametros)


def catalogo_candidatos(turno: int) -> list[tuple[str, str]]:
    if not VOTOS_PATH.exists():
        return [
            ("13", "Luiz Inácio Lula da Silva"),
            ("22", "Flávio Bolsonaro"),
            ("outros", "Outras candidaturas"),
        ]
    sql = f"""
        SELECT numero, nome
        FROM (
          SELECT CAST(numero AS VARCHAR) AS numero, any_value(nome) AS nome
          FROM read_parquet('{_sql_path(VOTOS_PATH)}')
          WHERE turno = ? AND CAST(numero AS VARCHAR) NOT IN ('95', '96')
          GROUP BY 1
        )
        ORDER BY TRY_CAST(numero AS INTEGER), numero
    """
    frame = consultar(sql, (turno,), _fingerprint(VOTOS_PATH))
    return [
        (str(r.numero), nome_candidato(str(r.numero), str(r.nome)))
        for r in frame.itertuples()
    ]


def dados_faixas(
    turno: int,
    uf: str,
    municipio: str | None,
    candidato_numero: str,
) -> pd.DataFrame:
    filtro, parametros = clausula_filtro(turno, uf, municipio, "s")
    caso = """
        CASE
          WHEN s.participacao < 0.50 THEN 'Abaixo de 50%'
          WHEN s.participacao < 0.60 THEN '50% a 59,9%'
          WHEN s.participacao < 0.70 THEN '60% a 69,9%'
          WHEN s.participacao < 0.80 THEN '70% a 79,9%'
          WHEN s.participacao < 0.90 THEN '80% a 89,9%'
          WHEN s.participacao < 0.95 THEN '90% a 94,9%'
          WHEN s.participacao < 0.98 THEN '95% a 97,9%'
          WHEN s.participacao < 1.00 THEN '98% a menos de 100%'
          ELSE '100%'
        END
    """
    ordem = """
        CASE
          WHEN s.participacao < 0.50 THEN 1 WHEN s.participacao < 0.60 THEN 2
          WHEN s.participacao < 0.70 THEN 3 WHEN s.participacao < 0.80 THEN 4
          WHEN s.participacao < 0.90 THEN 5 WHEN s.participacao < 0.95 THEN 6
          WHEN s.participacao < 0.98 THEN 7 WHEN s.participacao < 1.00 THEN 8
          ELSE 9
        END
    """
    if VOTOS_PATH.exists() and candidato_numero != "outros":
        sql = f"""
            WITH votos AS (
              SELECT turno, uf, TRY_CAST(municipio_codigo AS BIGINT) municipio_id,
                     TRY_CAST(zona AS BIGINT) zona_id, TRY_CAST(secao AS BIGINT) secao_id,
                     SUM(votos) AS votos
              FROM read_parquet('{_sql_path(VOTOS_PATH)}')
              WHERE CAST(numero AS VARCHAR) = ?
              GROUP BY 1,2,3,4,5
            )
            SELECT {caso} AS faixa, {ordem} AS ordem,
                   COUNT(*) AS secoes, SUM(s.aptos) AS aptos,
                   SUM(s.comparecimento) / NULLIF(SUM(s.aptos), 0) AS participacao,
                   SUM(COALESCE(v.votos, 0)) / NULLIF(SUM(s.validos), 0) AS candidato_validos,
                   SUM(COALESCE(v.votos, 0)) / NULLIF(SUM(s.aptos), 0) AS candidato_aptos
            FROM read_parquet('{_sql_path(SECOES_PATH)}') s
            LEFT JOIN votos v
              ON s.turno = v.turno AND s.uf = v.uf
             AND TRY_CAST(s.municipio_codigo AS BIGINT) = v.municipio_id
             AND TRY_CAST(s.zona AS BIGINT) = v.zona_id
             AND TRY_CAST(s.secao AS BIGINT) = v.secao_id
            WHERE {filtro}
            GROUP BY 1,2 ORDER BY 2
        """
        params = (str(candidato_numero),) + parametros
    else:
        coluna = {"13": "lula", "22": "bolsonaro", "outros": "outros"}.get(
            candidato_numero, "outros"
        )
        sql = f"""
            SELECT {caso} AS faixa, {ordem} AS ordem,
                   COUNT(*) AS secoes, SUM(s.aptos) AS aptos,
                   SUM(s.comparecimento) / NULLIF(SUM(s.aptos), 0) AS participacao,
                   SUM(s.{coluna}) / NULLIF(SUM(s.validos), 0) AS candidato_validos,
                   SUM(s.{coluna}) / NULLIF(SUM(s.aptos), 0) AS candidato_aptos
            FROM read_parquet('{_sql_path(SECOES_PATH)}') s
            WHERE {filtro}
            GROUP BY 1,2 ORDER BY 2
        """
        params = parametros
    return consultar(sql, params, _fingerprint(SECOES_PATH))


@st.cache_data(show_spinner=False, max_entries=3, ttl=900)
def gerar_csv_gzip(sql: str, parametros: tuple, fingerprint: tuple[int, int]) -> bytes:
    del fingerprint
    with tempfile.NamedTemporaryFile(suffix=".csv.gz", delete=False) as arquivo:
        caminho = Path(arquivo.name)
    caminho.unlink(missing_ok=True)
    try:
        destino = caminho.as_posix().replace("'", "''")
        with duckdb.connect() as con:
            con.execute(
                f"COPY ({sql}) TO '{destino}' (FORMAT CSV, HEADER, COMPRESSION GZIP)",
                list(parametros),
            )
        return caminho.read_bytes()
    finally:
        caminho.unlink(missing_ok=True)


st.markdown(
    """
    <div class="hero">
      <h1>Observatório<br>do voto 2026</h1>
      <p>Análise descritiva por seção eleitoral sobre participação e votação para a Presidência da República.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="question"><strong>Pergunta central:</strong> seções com menor abstenção apresentam proporções diferentes de voto em uma candidatura?</div>
    """,
    unsafe_allow_html=True,
)

if not SECOES_PATH.exists():
    st.info(
        "A base processada ainda não está disponível. O painel será preenchido quando "
        "data/processed/secoes.parquet for gerado pelo pipeline. Nenhum resultado de exemplo é exibido."
    )
    st.markdown(
        """
        <div class="method-box">
        <strong>Contrato esperado</strong><br>
        Uma linha por seção e turno, com eleitorado apto, comparecimento, abstenção, votos válidos,
        brancos, nulos e totais por candidatura. O exterior deve usar UF ZZ. As frações devem estar
        no intervalo de zero a um.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

colunas, faltantes = esquema_disponivel()
if faltantes:
    st.error(
        "A base processada não segue o contrato. Colunas ausentes: "
        + ", ".join(faltantes)
    )
    st.stop()

arquivo_secoes = _sql_path(SECOES_PATH)
fp_secoes = _fingerprint(SECOES_PATH)
turnos_df = consultar(
    f"SELECT DISTINCT CAST(turno AS INTEGER) turno FROM read_parquet('{arquivo_secoes}') ORDER BY 1",
    (),
    fp_secoes,
)
turnos = turnos_df["turno"].astype(int).tolist()

if turnos != [1, 2]:
    presentes = ", ".join(f"{t}º" for t in turnos) if turnos else "nenhum"
    st.warning(
        f"Dados por seção disponíveis: {presentes} turno. A comparação dos dois turnos por seção "
        "aguarda a publicação do pacote nacional completo. Consulte a aba própria para o segundo turno por zona."
    )

with st.sidebar:
    st.header("Recorte da análise")
    turno = st.selectbox(
        "Turno dos dados por seção", options=turnos, format_func=lambda x: f"{x}º turno"
    )
    st.link_button(
        "Ler o relatório da análise",
        "https://github.com/viniciusazeved/tse-eleicoes-2026/blob/main/reports/RELATORIO.md",
    )
    st.link_button(
        "Ler a revisão independente",
        "https://github.com/viniciusazeved/tse-eleicoes-2026/blob/main/docs/REVISAO_DOIS_TURNOS_SECAO.md",
    )
    ufs_df = consultar(
        f"SELECT DISTINCT uf FROM read_parquet('{arquivo_secoes}') WHERE turno = ? ORDER BY 1",
        (int(turno),),
        fp_secoes,
    )
    ufs_reais = [str(x) for x in ufs_df["uf"].dropna().tolist()]
    opcoes_uf = ["Brasil sem exterior"] + [x for x in ufs_reais if x != "ZZ"]
    if "ZZ" in ufs_reais:
        opcoes_uf.append("Exterior (ZZ)")
    uf_escolhida = st.selectbox("UF ou abrangência", opcoes_uf)

    if uf_escolhida == "Brasil sem exterior":
        municipio_opcoes: list[tuple[str | None, str]] = [(None, "Todos os municípios")]
    else:
        uf_codigo = "ZZ" if uf_escolhida == "Exterior (ZZ)" else uf_escolhida
        municipios_df = consultar(
            f"""
            SELECT DISTINCT CAST(municipio_codigo AS VARCHAR) codigo, municipio_nome nome
            FROM read_parquet('{arquivo_secoes}')
            WHERE turno = ? AND uf = ? ORDER BY nome, codigo
            """,
            (int(turno), uf_codigo),
            fp_secoes,
        )
        municipio_opcoes = [(None, "Todos os municípios")] + [
            (str(r.codigo), str(r.nome)) for r in municipios_df.itertuples()
        ]
    municipio_item = st.selectbox(
        "Município", municipio_opcoes, format_func=lambda x: x[1]
    )
    municipio_codigo = municipio_item[0]

    catalogo = catalogo_candidatos(int(turno))
    candidato = st.selectbox(
        "Candidatura em destaque",
        options=catalogo,
        format_func=lambda x: f"{x[1]} ({x[0]})" if x[0] != "outros" else x[1],
    )
    st.caption(
        "Brasil exclui seções no exterior. Selecione Exterior (ZZ) para analisá-las separadamente."
    )

filtro, parametros = clausula_filtro(int(turno), uf_escolhida, municipio_codigo)
resumo = consultar(
    f"""
    SELECT COUNT(*) secoes, SUM(aptos) aptos, SUM(comparecimento) comparecimento,
           SUM(abstencao) abstencao, SUM(validos) validos, SUM(brancos) brancos,
           SUM(nulos) nulos, SUM(lula) lula, SUM(bolsonaro) bolsonaro, SUM(outros) outros
    FROM read_parquet('{arquivo_secoes}') WHERE {filtro}
    """,
    parametros,
    fp_secoes,
).iloc[0]

if int(resumo["secoes"] or 0) == 0:
    st.warning("Nenhuma seção corresponde aos filtros selecionados.")
    st.stop()

participacao_total = (
    float(resumo["comparecimento"] / resumo["aptos"]) if resumo["aptos"] else None
)
abstencao_total = (
    float(resumo["abstencao"] / resumo["aptos"]) if resumo["aptos"] else None
)
validos_comparecimento = (
    float(resumo["validos"] / resumo["comparecimento"])
    if resumo["comparecimento"]
    else None
)

tabs = st.tabs(
    [
        "Visão geral",
        "Comparar turnos",
        "Segundo turno por zona",
        "Seções e download",
        "Método e QA",
        "Horários",
    ]
)

with tabs[0]:
    cabecalho_secao(
        "Participação no recorte",
        "Os totais são somas das seções filtradas. As proporções usam os denominadores indicados, sem ponderação oculta.",
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Seções", formatar_inteiro(resumo["secoes"]))
    c2.metric("Eleitorado apto", formatar_inteiro(resumo["aptos"]))
    c3.metric("Comparecimento", formatar_percentual(participacao_total))
    c4.metric("Abstenção", formatar_percentual(abstencao_total))
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Votos válidos", formatar_inteiro(resumo["validos"]))
    c6.metric("Válidos entre presentes", formatar_percentual(validos_comparecimento))
    c7.metric("Brancos", formatar_inteiro(resumo["brancos"]))
    c8.metric("Nulos", formatar_inteiro(resumo["nulos"]))

    cabecalho_secao(
        "Faixas de comparecimento",
        "Cada ponto resume todas as seções da faixa. A linha mostra a proporção de votos da candidatura entre votos válidos; as barras mostram quantas seções sustentam o ponto.",
    )
    faixas = dados_faixas(int(turno), uf_escolhida, municipio_codigo, candidato[0])
    fig_faixas = go.Figure()
    fig_faixas.add_bar(
        x=faixas["faixa"],
        y=faixas["secoes"],
        name="Seções",
        marker_color=AZUL_CLARO,
        opacity=0.55,
        yaxis="y2",
        hovertemplate="%{x}<br>%{y:,.0f} seções<extra></extra>",
    )
    fig_faixas.add_scatter(
        x=faixas["faixa"],
        y=100 * faixas["candidato_validos"],
        name=f"{candidato[1]} entre válidos",
        mode="lines+markers",
        line={"color": OCRE, "width": 3},
        marker={"size": 9, "line": {"color": "#FFFFFF", "width": 2}},
        hovertemplate="%{x}<br>%{y:.2f}% dos válidos<extra></extra>",
    )
    layout_grafico(fig_faixas, 430)
    fig_faixas.update_layout(
        yaxis={
            "title": "Votos válidos na candidatura (%)",
            "ticksuffix": "%",
            "gridcolor": GRADE,
        },
        yaxis2={
            "title": "Número de seções",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        barmode="overlay",
    )
    st.plotly_chart(fig_faixas, width="stretch", config={"displaylogo": False})
    st.caption(
        "Leitura descritiva. Diferenças entre faixas podem refletir composição territorial, tamanho das seções e outros fatores. O gráfico não identifica causa nem voto individual."
    )

    cabecalho_secao(
        "Cortes de participação elevada",
        "Cortes cumulativos definidos em 90%, 95%, 98% e 100%. Um corte menor inclui as seções dos cortes maiores; as linhas não podem ser somadas.",
    )
    cortes = consultar(
        f"""
        WITH limites(limiar, ordem, corte) AS (
          VALUES (0.90, 1, '90% ou mais'),
                 (0.95, 2, '95% ou mais'),
                 (0.98, 3, '98% ou mais'),
                 (1.00, 4, '100%')
        )
        SELECT l.corte, l.ordem, COUNT(*) secoes, SUM(s.aptos) aptos,
               SUM(s.validos) votos_validos,
               SUM(s.lula) votos_lula, SUM(s.bolsonaro) votos_flavio,
               SUM(s.lula) / NULLIF(SUM(s.validos), 0) apoio_lula,
               SUM(s.bolsonaro) / NULLIF(SUM(s.validos), 0) apoio_flavio
        FROM read_parquet('{arquivo_secoes}') s
        CROSS JOIN limites l
        WHERE {filtro} AND s.participacao >= l.limiar
        GROUP BY l.corte, l.ordem
        ORDER BY l.ordem
        """,
        parametros,
        fp_secoes,
    )
    st.dataframe(
        cortes.drop(columns="ordem"),
        width="stretch",
        hide_index=True,
        column_config={
            "corte": "Corte cumulativo",
            "secoes": st.column_config.NumberColumn("Seções", format="localized"),
            "aptos": st.column_config.NumberColumn("Aptos", format="localized"),
            "votos_validos": st.column_config.NumberColumn(
                "Votos válidos", format="localized"
            ),
            "votos_lula": st.column_config.NumberColumn(
                "Votos em Lula", format="localized"
            ),
            "votos_flavio": st.column_config.NumberColumn(
                "Votos em Flávio Bolsonaro", format="localized"
            ),
            "apoio_lula": st.column_config.NumberColumn(
                "Lula entre válidos", format="percent"
            ),
            "apoio_flavio": st.column_config.NumberColumn(
                "Flávio Bolsonaro entre válidos", format="percent"
            ),
        },
    )
    st.caption(
        "A tabela é descritiva e usa o recorte atual. Seções de um corte mais alto também pertencem aos cortes inferiores."
    )

    if uf_escolhida == "Brasil sem exterior":
        cabecalho_secao(
            "Participação elevada por região",
            "Distribuição das seções brasileiras do corte entre as cinco regiões e apoio agregado entre votos válidos.",
        )
        if CORTES_REGIOES_PATH.exists():
            cortes_regioes = pd.read_csv(CORTES_REGIOES_PATH)
            colunas_regionais = {
                "turno",
                "regiao",
                "corte",
                "secoes_regiao",
                "secoes_no_corte",
                "secoes_corte_brasil",
                "percentual_corte_nacional",
                "aptos",
                "comparecimento",
                "abstencao",
                "validos",
                "brancos",
                "nulos",
                "lula",
                "bolsonaro",
                "outros",
                "lula_validos",
                "bolsonaro_validos",
            }
            if not colunas_regionais.issubset(cortes_regioes.columns):
                st.warning(
                    "reports/cortes_regioes.csv existe, mas não segue o contrato esperado."
                )
            else:
                dados_turno_regiao = cortes_regioes.loc[
                    cortes_regioes["turno"].eq(int(turno))
                ].copy()
                cortes_disponiveis = sorted(
                    dados_turno_regiao["corte"].dropna().astype(float).unique().tolist()
                )
                if not cortes_disponiveis:
                    st.info("Ainda não há cortes regionais para o turno selecionado.")
                else:
                    corte_regional = st.selectbox(
                        "Corte regional de comparecimento",
                        options=cortes_disponiveis,
                        index=0,
                        format_func=lambda valor: f"{100 * valor:.0f}% ou mais",
                        key=f"corte_regional_turno_{turno}",
                    )
                    regional = dados_turno_regiao.loc[
                        dados_turno_regiao["corte"].astype(float).eq(corte_regional)
                    ].copy()
                    ordem_regioes = [
                        "Norte",
                        "Nordeste",
                        "Centro-Oeste",
                        "Sudeste",
                        "Sul",
                    ]
                    regional["regiao"] = pd.Categorical(
                        regional["regiao"], categories=ordem_regioes, ordered=True
                    )
                    regional = regional.sort_values("regiao")
                    parcela_corte = regional["percentual_corte_nacional"].astype(float)
                    if parcela_corte.abs().max() > 1:
                        parcela_corte = parcela_corte / 100
                    fig_regioes = go.Figure()
                    fig_regioes.add_bar(
                        x=regional["regiao"],
                        y=100 * parcela_corte,
                        name="Seções da região entre as seções do corte nacional",
                        marker_color=AZUL_CLARO,
                    )
                    fig_regioes.add_bar(
                        x=regional["regiao"],
                        y=100 * regional["lula_validos"],
                        name="Lula entre votos válidos da região",
                        marker_color=AZUL,
                    )
                    fig_regioes.add_bar(
                        x=regional["regiao"],
                        y=100 * regional["bolsonaro_validos"],
                        name="Flávio Bolsonaro entre votos válidos da região",
                        marker_color=OCRE,
                    )
                    fig_regioes.update_layout(
                        title=f"Regiões no corte de {100 * corte_regional:.0f}% ou mais",
                        barmode="group",
                    )
                    fig_regioes.update_yaxes(title="Proporção (%)", ticksuffix="%")
                    st.plotly_chart(
                        layout_grafico(fig_regioes, 430),
                        width="stretch",
                        config={"displaylogo": False},
                    )
                    tabela_regional = regional[
                        [
                            "regiao",
                            "secoes_regiao",
                            "secoes_no_corte",
                            "secoes_corte_brasil",
                            "aptos",
                            "validos",
                            "lula_validos",
                            "bolsonaro_validos",
                        ]
                    ].copy()
                    tabela_regional.insert(
                        4, "parcela_corte_nacional", parcela_corte.to_numpy()
                    )
                    st.dataframe(
                        tabela_regional,
                        width="stretch",
                        hide_index=True,
                        column_config={
                            "regiao": "Região",
                            "secoes_regiao": st.column_config.NumberColumn(
                                "Seções na região", format="localized"
                            ),
                            "secoes_no_corte": st.column_config.NumberColumn(
                                "Seções da região no corte", format="localized"
                            ),
                            "secoes_corte_brasil": st.column_config.NumberColumn(
                                "Seções no corte nacional", format="localized"
                            ),
                            "parcela_corte_nacional": st.column_config.NumberColumn(
                                "% das seções do corte nacional", format="percent"
                            ),
                            "aptos": st.column_config.NumberColumn(
                                "Aptos no corte", format="localized"
                            ),
                            "validos": st.column_config.NumberColumn(
                                "Votos válidos no corte", format="localized"
                            ),
                            "lula_validos": st.column_config.NumberColumn(
                                "Lula entre válidos", format="percent"
                            ),
                            "bolsonaro_validos": st.column_config.NumberColumn(
                                "Flávio Bolsonaro entre válidos", format="percent"
                            ),
                        },
                    )
                    st.caption(
                        "“% das seções do corte nacional” descreve onde estão as seções do corte. “Entre válidos” descreve a composição dos votos válidos dentro de cada região."
                    )
        else:
            st.caption(
                "A tabela regional dos cortes ainda não foi publicada nesta versão."
            )

    cabecalho_secao(
        "Distribuição do comparecimento",
        "Histograma agregado em intervalos de dois pontos percentuais. Nenhum ponto representa eleitor individual.",
    )
    distribuicao = consultar(
        f"""
        SELECT LEAST(98, GREATEST(0, FLOOR(participacao * 50) * 2)) AS inicio,
               COUNT(*) secoes, SUM(aptos) aptos
        FROM read_parquet('{arquivo_secoes}')
        WHERE {filtro} AND participacao BETWEEN 0 AND 1
        GROUP BY 1 ORDER BY 1
        """,
        parametros,
        fp_secoes,
    )
    fig_dist = go.Figure(
        go.Bar(
            x=distribuicao["inicio"] + 1,
            y=distribuicao["secoes"],
            width=1.7,
            marker_color=AZUL,
            hovertemplate="%{x:.0f}% aproximadamente<br>%{y:,.0f} seções<extra></extra>",
        )
    )
    fig_dist.update_layout(title="Seções por nível de comparecimento", showlegend=False)
    fig_dist.update_xaxes(title="Comparecimento (%)", ticksuffix="%", range=[0, 100])
    fig_dist.update_yaxes(title="Número de seções")
    st.plotly_chart(
        layout_grafico(fig_dist),
        width="stretch",
        config={"displaylogo": False},
    )

with tabs[1]:
    cabecalho_secao(
        "Seções observadas nos dois turnos",
        "Pareamento pela mesma UF, município, zona e seção. O recorte principal também exige eleitorado apto e código do local iguais.",
    )
    if PAREAMENTO_PATH.exists():
        arquivo_pareamento = _sql_path(PAREAMENTO_PATH)
        fp_pareamento = _fingerprint(PAREAMENTO_PATH)
        esquema_pareamento = consultar(
            f"DESCRIBE SELECT * FROM read_parquet('{arquivo_pareamento}')",
            (),
            fp_pareamento,
        )
        colunas_pareamento = set(esquema_pareamento["column_name"].astype(str))
        obrigatorias_pareamento = {
            "uf",
            "municipio_codigo",
            "zona",
            "secao",
            "aptos_t1",
            "aptos_t2",
            "comparecimento_t1",
            "comparecimento_t2",
            "validos_t1",
            "validos_t2",
            "lula_t1",
            "lula_t2",
            "bolsonaro_t1",
            "bolsonaro_t2",
            "aptos_iguais",
            "local_igual",
            "elegivel",
            "principal",
            "delta_participacao",
            "delta_lula_validos",
            "delta_bolsonaro_validos",
            "delta_lula",
            "delta_bolsonaro",
        }
        faltantes_pareamento = sorted(obrigatorias_pareamento - colunas_pareamento)
        if faltantes_pareamento:
            st.error(
                "O arquivo de pareamento não segue o contrato. Colunas ausentes: "
                + ", ".join(faltantes_pareamento)
            )
        else:
            recorte_pareamento = st.radio(
                "Recorte do pareamento",
                options=["principal", "todos_elegiveis"],
                format_func=lambda valor: (
                    "Principal: aptos e local iguais"
                    if valor == "principal"
                    else "Todas as chaves elegíveis"
                ),
                horizontal=True,
            )
            filtro_dominio, parametros_dominio = clausula_filtro(
                None, uf_escolhida, municipio_codigo, "p"
            )
            criterio_recorte = (
                "p.principal IS TRUE"
                if recorte_pareamento == "principal"
                else "p.elegivel IS TRUE"
            )
            cobertura = consultar(
                f"""
                SELECT COUNT(*) chaves,
                       SUM(CASE WHEN p.elegivel IS TRUE THEN 1 ELSE 0 END) elegiveis,
                       SUM(CASE WHEN p.principal IS TRUE THEN 1 ELSE 0 END) principais
                FROM read_parquet('{arquivo_pareamento}') p
                WHERE {filtro_dominio}
                """,
                parametros_dominio,
                fp_pareamento,
            ).iloc[0]
            resumo_pareamento = consultar(
                f"""
                SELECT COUNT(*) secoes,
                       SUM(p.aptos_t1) aptos_t1, SUM(p.aptos_t2) aptos_t2,
                       SUM(p.comparecimento_t1) / NULLIF(SUM(p.aptos_t1), 0) participacao_t1,
                       SUM(p.comparecimento_t2) / NULLIF(SUM(p.aptos_t2), 0) participacao_t2,
                       SUM(p.lula_t1) / NULLIF(SUM(p.validos_t1), 0) lula_validos_t1,
                       SUM(p.lula_t2) / NULLIF(SUM(p.validos_t2), 0) lula_validos_t2,
                       SUM(p.bolsonaro_t1) / NULLIF(SUM(p.validos_t1), 0) bolsonaro_validos_t1,
                       SUM(p.bolsonaro_t2) / NULLIF(SUM(p.validos_t2), 0) bolsonaro_validos_t2,
                       SUM(p.delta_lula) delta_lula,
                       SUM(p.delta_bolsonaro) delta_bolsonaro
                FROM read_parquet('{arquivo_pareamento}') p
                WHERE {filtro_dominio} AND {criterio_recorte}
                """,
                parametros_dominio,
                fp_pareamento,
            ).iloc[0]
            if not int(resumo_pareamento["secoes"] or 0):
                st.info(
                    "Nenhuma seção pareada corresponde ao domínio e ao recorte selecionados."
                )
            else:
                excluidas_principal = int(cobertura["chaves"] - cobertura["principais"])
                pc1, pc2, pc3, pc4 = st.columns(4)
                pc1.metric(
                    "Chaves correspondentes", formatar_inteiro(cobertura["chaves"])
                )
                pc2.metric("Chaves elegíveis", formatar_inteiro(cobertura["elegiveis"]))
                pc3.metric(
                    "Recorte principal", formatar_inteiro(cobertura["principais"])
                )
                pc4.metric("Fora do principal", formatar_inteiro(excluidas_principal))
                st.caption(
                    "Principal significa chave correspondente com aptos e local iguais. Isso melhora a comparabilidade cadastral, mas não demonstra que as mesmas pessoas votaram nos dois turnos."
                )

                delta_participacao = 100 * (
                    resumo_pareamento["participacao_t2"]
                    - resumo_pareamento["participacao_t1"]
                )
                delta_lula_apoio = 100 * (
                    resumo_pareamento["lula_validos_t2"]
                    - resumo_pareamento["lula_validos_t1"]
                )
                delta_flavio_apoio = 100 * (
                    resumo_pareamento["bolsonaro_validos_t2"]
                    - resumo_pareamento["bolsonaro_validos_t1"]
                )
                pm1, pm2, pm3, pm4 = st.columns(4)
                pm1.metric(
                    "Seções no recorte",
                    formatar_inteiro(resumo_pareamento["secoes"]),
                )
                pm2.metric(
                    "Mudança no comparecimento",
                    f"{delta_participacao:+.2f} pp".replace(".", ","),
                )
                pm3.metric(
                    "Mudança no apoio a Lula",
                    f"{delta_lula_apoio:+.2f} pp".replace(".", ","),
                )
                pm4.metric(
                    "Mudança no apoio a Flávio Bolsonaro",
                    f"{delta_flavio_apoio:+.2f} pp".replace(".", ","),
                )

                fig_pareamento = go.Figure()
                fig_pareamento.add_bar(
                    x=["1º turno", "2º turno"],
                    y=[
                        100 * resumo_pareamento["participacao_t1"],
                        100 * resumo_pareamento["participacao_t2"],
                    ],
                    name="Comparecimento",
                    marker_color=AZUL_CLARO,
                )
                fig_pareamento.add_bar(
                    x=["1º turno", "2º turno"],
                    y=[
                        100 * resumo_pareamento["lula_validos_t1"],
                        100 * resumo_pareamento["lula_validos_t2"],
                    ],
                    name="Lula entre válidos",
                    marker_color=AZUL,
                )
                fig_pareamento.add_bar(
                    x=["1º turno", "2º turno"],
                    y=[
                        100 * resumo_pareamento["bolsonaro_validos_t1"],
                        100 * resumo_pareamento["bolsonaro_validos_t2"],
                    ],
                    name="Flávio Bolsonaro entre válidos",
                    marker_color=OCRE,
                )
                fig_pareamento.update_layout(
                    title="Participação e apoio nas mesmas chaves de seção",
                    barmode="group",
                )
                fig_pareamento.update_yaxes(title="Proporção (%)", ticksuffix="%")
                st.plotly_chart(
                    layout_grafico(fig_pareamento),
                    width="stretch",
                    config={"displaylogo": False},
                )

                relacao_mudancas = consultar(
                    f"""
                    SELECT FLOOR(p.delta_participacao * 50) / 50 AS faixa_delta_participacao,
                           COUNT(*) secoes,
                           AVG(p.delta_lula_validos) delta_lula_validos,
                           AVG(p.delta_bolsonaro_validos) delta_bolsonaro_validos
                    FROM read_parquet('{arquivo_pareamento}') p
                    WHERE {filtro_dominio} AND {criterio_recorte}
                      AND p.delta_participacao IS NOT NULL
                      AND p.delta_lula_validos IS NOT NULL
                      AND p.delta_bolsonaro_validos IS NOT NULL
                    GROUP BY 1 ORDER BY 1
                    """,
                    parametros_dominio,
                    fp_pareamento,
                )
                fig_mudancas = go.Figure()
                fig_mudancas.add_bar(
                    x=100 * relacao_mudancas["faixa_delta_participacao"],
                    y=relacao_mudancas["secoes"],
                    name="Seções",
                    marker_color=AZUL_CLARO,
                    opacity=0.45,
                    yaxis="y2",
                )
                fig_mudancas.add_scatter(
                    x=100 * relacao_mudancas["faixa_delta_participacao"],
                    y=100 * relacao_mudancas["delta_lula_validos"],
                    name="Mudança média no apoio a Lula",
                    line={"color": AZUL, "width": 3},
                    mode="lines+markers",
                )
                fig_mudancas.add_scatter(
                    x=100 * relacao_mudancas["faixa_delta_participacao"],
                    y=100 * relacao_mudancas["delta_bolsonaro_validos"],
                    name="Mudança média no apoio a Flávio Bolsonaro",
                    line={"color": OCRE, "width": 3},
                    mode="lines+markers",
                )
                layout_grafico(fig_mudancas, 430)
                fig_mudancas.update_layout(
                    title="Mudança de apoio por faixa de mudança no comparecimento",
                    yaxis={
                        "title": "Mudança média no apoio (pp)",
                        "ticksuffix": " pp",
                        "gridcolor": GRADE,
                    },
                    yaxis2={
                        "title": "Número de seções",
                        "overlaying": "y",
                        "side": "right",
                        "showgrid": False,
                    },
                )
                fig_mudancas.update_xaxes(
                    title="Mudança no comparecimento (pp)", ticksuffix=" pp"
                )
                st.plotly_chart(
                    fig_mudancas,
                    width="stretch",
                    config={"displaylogo": False},
                )
                st.caption(
                    "Cada ponto resume uma faixa de dois pontos percentuais de mudança no comparecimento. A média é por seção e não representa fluxo individual de eleitores."
                )
                st.warning(
                    "Ganhos e perdas agregados entre turnos incluem mudanças de comparecimento e votos em candidaturas eliminadas. Eles não identificam de onde vieram ou para onde foram votos individuais."
                )

                if (
                    PAREAMENTO_RELATORIO_PATH.exists()
                    and uf_escolhida
                    in {
                        "Brasil sem exterior",
                        "Exterior (ZZ)",
                    }
                    and municipio_codigo is None
                ):
                    correlacoes = pd.read_csv(PAREAMENTO_RELATORIO_PATH)
                    if {"universo", "recorte"}.issubset(correlacoes.columns):
                        universo_relatorio = (
                            "Brasil"
                            if uf_escolhida == "Brasil sem exterior"
                            else "Exterior"
                        )
                        mascara_relatorio = correlacoes["universo"].astype(
                            str
                        ).str.casefold().eq(
                            universo_relatorio.casefold()
                        ) & correlacoes["recorte"].astype(str).str.casefold().eq(
                            recorte_pareamento.casefold()
                        )
                        correlacoes_recorte = correlacoes.loc[mascara_relatorio]
                        if not correlacoes_recorte.empty:
                            with st.expander(
                                "Correlações publicadas para este universo"
                            ):
                                st.dataframe(
                                    correlacoes_recorte,
                                    width="stretch",
                                    hide_index=True,
                                )
                                st.caption(
                                    "Pearson e Spearman descrevem associação entre mudanças agregadas. Não são testes de transferência individual ou fraude."
                                )
    elif not {1, 2}.issubset(set(turnos)):
        st.info(
            "O 2º turno ainda não está disponível nesta base. Esta área será ativada automaticamente quando os dois turnos forem processados."
        )
    else:
        filtro_sem_turno, parametros_sem_turno = clausula_filtro(
            None, uf_escolhida, municipio_codigo, "s1"
        )
        coluna = {"13": "lula", "22": "bolsonaro", "outros": "outros"}.get(candidato[0])
        if "local_codigo" not in colunas:
            st.info(
                "A comparação exige o código do local de votação nos dois turnos. Esse campo não está disponível nesta base."
            )
        elif coluna is None:
            st.info(
                "A comparação entre turnos para esta candidatura depende da presença dela nos dois turnos. Selecione uma candidatura comum aos dois para comparar."
            )
        else:
            comparacao = consultar(
                f"""
                WITH primeiro AS (
                  SELECT * FROM read_parquet('{arquivo_secoes}') s1
                  WHERE s1.turno = 1 AND {filtro_sem_turno}
                ), segundo AS (
                  SELECT * FROM read_parquet('{arquivo_secoes}') WHERE turno = 2
                ), pares AS (
                  SELECT s1.*, s2.aptos aptos_t2, s2.comparecimento comparecimento_t2,
                         s2.validos validos_t2, s2.{coluna} candidato_t2,
                         s2.uf IS NOT NULL chave_pareada,
                         s2.uf IS NOT NULL
                           AND s1.aptos = s2.aptos
                           AND TRY_CAST(s1.local_codigo AS BIGINT) = TRY_CAST(s2.local_codigo AS BIGINT)
                           AS pareada_estrita
                  FROM primeiro s1
                  LEFT JOIN segundo s2
                    ON s1.uf = s2.uf
                   AND TRY_CAST(s1.municipio_codigo AS BIGINT) = TRY_CAST(s2.municipio_codigo AS BIGINT)
                   AND TRY_CAST(s1.zona AS BIGINT) = TRY_CAST(s2.zona AS BIGINT)
                   AND TRY_CAST(s1.secao AS BIGINT) = TRY_CAST(s2.secao AS BIGINT)
                )
                SELECT COUNT(*) secoes_t1,
                       COUNT(*) FILTER (WHERE chave_pareada) chaves_pareadas,
                       COUNT(*) FILTER (WHERE pareada_estrita) secoes_pareadas,
                       SUM(aptos) FILTER (WHERE pareada_estrita) aptos_t1,
                       SUM(aptos_t2) FILTER (WHERE pareada_estrita) aptos_t2,
                       SUM(comparecimento) FILTER (WHERE pareada_estrita)
                         / NULLIF(SUM(aptos) FILTER (WHERE pareada_estrita), 0) participacao_t1,
                       SUM(comparecimento_t2) FILTER (WHERE pareada_estrita)
                         / NULLIF(SUM(aptos_t2) FILTER (WHERE pareada_estrita), 0) participacao_t2,
                       SUM({coluna}) FILTER (WHERE pareada_estrita)
                         / NULLIF(SUM(validos) FILTER (WHERE pareada_estrita), 0) candidato_t1,
                       SUM(candidato_t2) FILTER (WHERE pareada_estrita)
                         / NULLIF(SUM(validos_t2) FILTER (WHERE pareada_estrita), 0) candidato_t2
                FROM pares
                """,
                parametros_sem_turno,
                fp_secoes,
            ).iloc[0]
            if not comparacao["secoes_pareadas"]:
                st.info(
                    "Nenhuma seção atendeu simultaneamente à chave territorial, ao eleitorado apto e ao código do local iguais nos dois turnos."
                )
            else:
                excluidas = int(comparacao["secoes_t1"] - comparacao["secoes_pareadas"])
                p1, p2, p3 = st.columns(3)
                p1.metric(
                    "Seções elegíveis no 1º turno",
                    formatar_inteiro(comparacao["secoes_t1"]),
                )
                p2.metric(
                    "Pareadas com aptos e local iguais",
                    formatar_inteiro(comparacao["secoes_pareadas"]),
                )
                p3.metric(
                    "Excluídas do pareamento",
                    formatar_inteiro(excluidas),
                )
                st.caption(
                    f"{formatar_inteiro(comparacao['chaves_pareadas'])} seções tiveram chave territorial correspondente antes da exigência de aptos e local iguais. O pareamento melhora a comparabilidade cadastral, mas não demonstra que as mesmas pessoas votaram nos dois turnos."
                )
                fig_comp = go.Figure()
                fig_comp.add_bar(
                    x=["1º turno", "2º turno"],
                    y=[
                        100 * comparacao["participacao_t1"],
                        100 * comparacao["participacao_t2"],
                    ],
                    name="Comparecimento",
                    marker_color=AZUL,
                )
                fig_comp.add_bar(
                    x=["1º turno", "2º turno"],
                    y=[
                        100 * comparacao["candidato_t1"],
                        100 * comparacao["candidato_t2"],
                    ],
                    name=f"{candidato[1]} entre válidos",
                    marker_color=OCRE,
                )
                fig_comp.update_layout(
                    title="Participação e votação nas seções correspondentes",
                    barmode="group",
                )
                fig_comp.update_yaxes(title="Proporção (%)", ticksuffix="%")
                st.plotly_chart(
                    layout_grafico(fig_comp),
                    width="stretch",
                    config={"displaylogo": False},
                )
                st.warning(
                    "A urna não registra transferência individual de voto entre turnos. Mudanças agregadas não identificam fluxo entre candidaturas, abstenção, branco ou nulo. Mesmo com aptos e local iguais, não se presume identidade do eleitorado."
                )

with tabs[2]:
    cabecalho_secao(
        "Segundo turno por zona eleitoral",
        "Camada própria de resultados agregados por zona. Os filtros de UF e município da barra lateral também se aplicam aqui.",
    )
    st.warning(
        "Cada zona reúne várias seções. Estes resultados permitem comparar zonas, mas não substituir a análise de cada seção."
    )
    qa_zonas_ok, mensagem_qa_zonas = validar_qa_zonas()
    if not qa_zonas_ok:
        if ZONAS_TURNO2_PATH.exists():
            st.warning(
                mensagem_qa_zonas + " Os resultados por zona permanecem bloqueados."
            )
        else:
            st.info(
                mensagem_qa_zonas
                + " O guia será preenchido quando o Parquet e seu relatório de QA forem publicados."
            )
    else:
        st.success(mensagem_qa_zonas)
        arquivo_zonas = _sql_path(ZONAS_TURNO2_PATH)
        fp_zonas = _fingerprint(ZONAS_TURNO2_PATH)
        esquema_zonas = consultar(
            f"DESCRIBE SELECT * FROM read_parquet('{arquivo_zonas}')",
            (),
            fp_zonas,
        )
        colunas_zonas = set(esquema_zonas["column_name"].astype(str))
        obrigatorias_zonas = {
            "turno",
            "uf",
            "municipio_codigo",
            "municipio_nome",
            "zona",
            "aptos",
            "comparecimento",
            "abstencao",
            "validos",
            "lula",
            "bolsonaro",
        }
        faltantes_zonas = sorted(obrigatorias_zonas - colunas_zonas)
        if faltantes_zonas:
            st.error(
                "A camada por zona não segue o contrato. Colunas ausentes: "
                + ", ".join(faltantes_zonas)
            )
        else:
            filtro_zonas, parametros_zonas = clausula_filtro(
                2, uf_escolhida, municipio_codigo, "z"
            )
            comparacao_zonas = consultar(
                f"""
                WITH primeiro AS (
                  SELECT uf, TRY_CAST(municipio_codigo AS BIGINT) municipio_id,
                         any_value(municipio_nome) municipio_nome,
                         TRY_CAST(zona AS BIGINT) zona_id,
                         SUM(aptos) aptos, SUM(comparecimento) comparecimento,
                         SUM(validos) validos, SUM(lula) lula, SUM(bolsonaro) bolsonaro
                  FROM read_parquet('{arquivo_secoes}')
                  WHERE turno = 1
                  GROUP BY 1,2,4
                ), segundo AS (
                  SELECT z.uf, TRY_CAST(z.municipio_codigo AS BIGINT) municipio_id,
                         z.municipio_nome, TRY_CAST(z.zona AS BIGINT) zona_id,
                         z.aptos, z.comparecimento, z.validos, z.lula, z.bolsonaro
                  FROM read_parquet('{arquivo_zonas}') z
                  WHERE {filtro_zonas}
                )
                SELECT COUNT(*) zonas,
                       SUM(p.aptos) aptos_t1, SUM(s.aptos) aptos_t2,
                       SUM(p.comparecimento) / NULLIF(SUM(p.aptos), 0) participacao_t1,
                       SUM(s.comparecimento) / NULLIF(SUM(s.aptos), 0) participacao_t2,
                       SUM(p.lula) / NULLIF(SUM(p.validos), 0) lula_t1,
                       SUM(s.lula) / NULLIF(SUM(s.validos), 0) lula_t2,
                       SUM(p.bolsonaro) / NULLIF(SUM(p.validos), 0) flavio_t1,
                       SUM(s.bolsonaro) / NULLIF(SUM(s.validos), 0) flavio_t2
                FROM segundo s
                INNER JOIN primeiro p
                  ON s.uf = p.uf
                 AND s.municipio_id = p.municipio_id
                 AND s.zona_id = p.zona_id
                """,
                parametros_zonas,
                (fp_secoes[0] + fp_zonas[0], fp_secoes[1] + fp_zonas[1]),
            ).iloc[0]
            if not comparacao_zonas["zonas"]:
                st.info(
                    "Nenhuma zona correspondente foi encontrada nos dois turnos para este recorte."
                )
            else:
                delta_aptos = int(
                    comparacao_zonas["aptos_t2"] - comparacao_zonas["aptos_t1"]
                )
                delta_participacao = 100 * (
                    comparacao_zonas["participacao_t2"]
                    - comparacao_zonas["participacao_t1"]
                )
                delta_lula = 100 * (
                    comparacao_zonas["lula_t2"] - comparacao_zonas["lula_t1"]
                )
                delta_flavio = 100 * (
                    comparacao_zonas["flavio_t2"] - comparacao_zonas["flavio_t1"]
                )
                z1, z2, z3, z4 = st.columns(4)
                z1.metric(
                    "Zonas correspondentes", formatar_inteiro(comparacao_zonas["zonas"])
                )
                z2.metric(
                    "Aptos no 2º turno",
                    formatar_inteiro(comparacao_zonas["aptos_t2"]),
                    delta=f"{delta_aptos:+,}".replace(",", ".") + " ante o 1º",
                )
                z3.metric(
                    "Mudança no comparecimento",
                    f"{delta_participacao:+.2f} pp".replace(".", ","),
                )
                z4.metric(
                    "Comparecimento no 2º turno",
                    formatar_percentual(comparacao_zonas["participacao_t2"]),
                )

                cabecalho_secao(
                    "Apoio entre votos válidos",
                    "As barras partem do centro para facilitar a leitura equilibrada das duas candidaturas. As cores servem apenas para distinguir séries.",
                )
                fig_zonas = go.Figure()
                fig_zonas.add_bar(
                    y=["1º turno", "2º turno"],
                    x=[
                        100 * comparacao_zonas["lula_t1"],
                        100 * comparacao_zonas["lula_t2"],
                    ],
                    orientation="h",
                    name="Luiz Inácio Lula da Silva",
                    marker_color=AZUL,
                    customdata=[delta_lula, delta_lula],
                    hovertemplate="%{y}<br>Lula: %{x:.2f}% dos válidos<extra></extra>",
                )
                fig_zonas.add_bar(
                    y=["1º turno", "2º turno"],
                    x=[
                        -100 * comparacao_zonas["flavio_t1"],
                        -100 * comparacao_zonas["flavio_t2"],
                    ],
                    orientation="h",
                    name="Flávio Bolsonaro",
                    marker_color=OCRE,
                    customdata=[
                        [100 * comparacao_zonas["flavio_t1"], delta_flavio],
                        [100 * comparacao_zonas["flavio_t2"], delta_flavio],
                    ],
                    hovertemplate="%{y}<br>Flávio Bolsonaro: %{customdata[0]:.2f}% dos válidos<br>Mudança: %{customdata[1]:.2f} pp<extra></extra>",
                )
                fig_zonas.update_layout(
                    title="Comparação nas mesmas zonas",
                    barmode="relative",
                    bargap=0.28,
                )
                fig_zonas.update_xaxes(
                    title="Participação nos votos válidos (%)",
                    range=[-100, 100],
                    tickvals=[-100, -75, -50, -25, 0, 25, 50, 75, 100],
                    ticktext=[
                        "100%",
                        "75%",
                        "50%",
                        "25%",
                        "0",
                        "25%",
                        "50%",
                        "75%",
                        "100%",
                    ],
                )
                st.plotly_chart(
                    layout_grafico(fig_zonas, 410),
                    width="stretch",
                    config={"displaylogo": False},
                )
                delta_lula_texto = f"{delta_lula:+.2f}".replace(".", ",")
                delta_flavio_texto = f"{delta_flavio:+.2f}".replace(".", ",")
                st.caption(
                    f"Mudança entre os turnos nas zonas correspondentes: Lula {delta_lula_texto} pp; Flávio Bolsonaro {delta_flavio_texto} pp. Mudanças agregadas não identificam transferência individual de voto."
                )

with tabs[3]:
    cabecalho_secao(
        "Tabela explorável",
        "A prévia mostra até mil seções por página. O arquivo para download contém todas as linhas do recorte filtrado.",
    )
    total_paginas = max(1, (int(resumo["secoes"]) + 999) // 1000)
    pagina = st.number_input(
        "Página", min_value=1, max_value=total_paginas, value=1, step=1
    )
    colunas_tabela = [
        "turno",
        "uf",
        "municipio_codigo",
        "municipio_nome",
        "zona",
        "secao",
        "aptos",
        "comparecimento",
        "abstencao",
        "validos",
        "brancos",
        "nulos",
        "lula",
        "bolsonaro",
        "outros",
        "participacao",
        "lula_validos",
        "bolsonaro_validos",
    ]
    if "local" in colunas:
        colunas_tabela.insert(6, "local")
    selecao_colunas = ", ".join(colunas_tabela)
    tabela = consultar(
        f"""
        SELECT {selecao_colunas} FROM read_parquet('{arquivo_secoes}')
        WHERE {filtro}
        ORDER BY uf, municipio_nome, TRY_CAST(zona AS INTEGER), TRY_CAST(secao AS INTEGER)
        LIMIT 1000 OFFSET ?
        """,
        parametros + ((int(pagina) - 1) * 1000,),
        fp_secoes,
    )
    st.dataframe(
        tabela,
        width="stretch",
        hide_index=True,
        column_config={
            "participacao": st.column_config.NumberColumn(
                "comparecimento", format="percent"
            ),
            "lula_validos": st.column_config.NumberColumn(
                "Lula entre válidos", format="percent"
            ),
            "bolsonaro_validos": st.column_config.NumberColumn(
                "Flávio Bolsonaro entre válidos", format="percent"
            ),
        },
    )
    if int(resumo["secoes"]) > 250_000:
        st.caption(
            "O recorte é amplo. A preparação do CSV pode levar alguns segundos e o arquivo será compactado para reduzir o tamanho."
        )
    if st.button("Preparar CSV filtrado", type="secondary"):
        sql_exportacao = f"SELECT {selecao_colunas} FROM read_parquet('{arquivo_secoes}') WHERE {filtro} ORDER BY uf, municipio_nome, zona, secao"
        with st.spinner("Preparando arquivo compactado..."):
            conteudo = gerar_csv_gzip(sql_exportacao, parametros, fp_secoes)
        st.download_button(
            "Baixar CSV filtrado",
            data=conteudo,
            file_name=f"observatorio_voto_2026_turno_{turno}.csv.gz",
            mime="application/gzip",
        )

with tabs[4]:
    cabecalho_secao(
        "Como ler a análise",
        "O painel descreve associações agregadas por seção. Ele não mede comportamento individual e não testa integridade da votação.",
    )
    st.markdown(
        """
        <div class="method-box">
        <strong>Unidade de análise:</strong> seção eleitoral em cada turno.<br>
        <strong>Participação:</strong> comparecimento dividido pelo eleitorado apto.<br>
        <strong>Voto na candidatura entre válidos:</strong> votos na candidatura divididos pelos votos válidos.<br>
        <strong>Exterior:</strong> excluído do total Brasil por padrão e disponível como recorte próprio.<br><br>
        Associação entre duas proporções agregadas não demonstra causa, fraude, transferência de voto ou escolha individual.
        Diferenças territoriais e sociais podem influenciar simultaneamente comparecimento e votação.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if METODOLOGIA_PATH.exists():
        with st.expander("Metodologia completa"):
            st.markdown(METODOLOGIA_PATH.read_text(encoding="utf-8"))
    else:
        st.caption("O arquivo METODOLOGIA.md ainda não foi publicado nesta versão.")

    cabecalho_secao(
        "Análise ajustada nacional",
        "Modelos para o Brasil sem exterior. Estes resultados são nacionais e não mudam com os filtros de UF e município da interface.",
    )
    if MODELOS_PATH.exists():
        try:
            modelos = pd.read_csv(MODELOS_PATH)
            colunas_modelo = {
                "turno",
                "aptos_minimos",
                "candidato",
                "efeito_fixo",
                "ponderacao",
                "n",
                "grupos",
                "municipios_cluster",
                "status",
                "pp_por_10pp",
                "ic95_inferior",
                "ic95_superior",
                "r2_dentro",
            }
            if not colunas_modelo.issubset(modelos.columns):
                st.warning(
                    "reports/modelos.csv existe, mas não segue o contrato esperado."
                )
            else:
                turnos_modelos = sorted(
                    modelos["turno"].dropna().astype(int).unique().tolist()
                )
                turno_padrao = (
                    turnos_modelos.index(int(turno))
                    if int(turno) in turnos_modelos
                    else 0
                )
                turno_modelo = st.selectbox(
                    "Turno do modelo nacional",
                    options=turnos_modelos,
                    index=turno_padrao,
                    format_func=lambda x: f"{x}º turno",
                    key="turno_modelo_nacional",
                )
                modelos_turno = modelos.loc[
                    modelos["turno"].eq(int(turno_modelo))
                ].copy()
                if modelos_turno.empty:
                    st.info(
                        "Ainda não há modelo nacional publicado para o turno selecionado."
                    )
                else:
                    modelos_turno["candidato"] = modelos_turno["candidato"].replace(
                        {
                            "lula": "Luiz Inácio Lula da Silva",
                            "bolsonaro": "Flávio Bolsonaro",
                        }
                    )
                    exibicao_modelos = modelos_turno[
                        [
                            "candidato",
                            "aptos_minimos",
                            "efeito_fixo",
                            "ponderacao",
                            "n",
                            "grupos",
                            "municipios_cluster",
                            "status",
                            "pp_por_10pp",
                            "ic95_inferior",
                            "ic95_superior",
                            "r2_dentro",
                        ]
                    ]
                    st.dataframe(
                        exibicao_modelos,
                        width="stretch",
                        hide_index=True,
                        column_config={
                            "aptos_minimos": "Aptos mínimos",
                            "efeito_fixo": "Efeito fixo",
                            "ponderacao": "Ponderação",
                            "n": st.column_config.NumberColumn(
                                "Observações", format="localized"
                            ),
                            "grupos": st.column_config.NumberColumn(
                                "Grupos", format="localized"
                            ),
                            "municipios_cluster": st.column_config.NumberColumn(
                                "Municípios no agrupamento", format="localized"
                            ),
                            "status": "Status",
                            "pp_por_10pp": st.column_config.NumberColumn(
                                "pp de apoio por 10 pp de participação", format="%.3f"
                            ),
                            "ic95_inferior": st.column_config.NumberColumn(
                                "IC95 inferior", format="%.3f"
                            ),
                            "ic95_superior": st.column_config.NumberColumn(
                                "IC95 superior", format="%.3f"
                            ),
                            "r2_dentro": st.column_config.NumberColumn(
                                "R² dentro", format="%.3f"
                            ),
                        },
                    )
                    st.caption(
                        "A inclinação indica a mudança estimada, em pontos percentuais de apoio, associada a dez pontos percentuais de participação. O intervalo descreve incerteza do modelo e não probabilidade de fraude."
                    )
        except (OSError, ValueError, pd.errors.ParserError):
            st.warning("reports/modelos.csv existe, mas não pôde ser lido.")
    else:
        st.caption(
            "A tabela de modelos ajustados ainda não foi publicada nesta versão."
        )

    cabecalho_secao(
        "Exceções documentadas na fonte",
        "Casos preservados pelo pipeline, sem correção arbitrária dos totais oficiais.",
    )
    if QA_EXCECOES_PATH.exists():
        excecoes = pd.read_csv(QA_EXCECOES_PATH)
        falha_balanco = (
            excecoes["falha_aptos_igual_comparecimento_mais_abstencao"]
            .astype(str)
            .str.casefold()
            .isin({"true", "1"})
        )
        sem_linha = (
            excecoes["sem_linha_nominal_publicada"]
            .astype(str)
            .str.casefold()
            .isin({"true", "1"})
        )
        instalada = excecoes["secao_instalada"].astype(str).str.casefold().eq("sim")
        divergentes = excecoes.loc[falha_balanco]
        sem_votos_instalada = excecoes.loc[sem_linha & instalada]
        st.info(
            f"A publicação contém {formatar_inteiro(len(divergentes))} divergências entre aptos e comparecimento mais abstenção. "
            f"Elas estão no exterior, somam {formatar_inteiro(divergentes['aptos'].sum())} aptos e correspondem a locais marcados como não instalados. "
            f"Há {formatar_inteiro(sem_linha.sum())} registros sem linha nominal de votação; {formatar_inteiro(len(sem_votos_instalada))} deles está marcado como instalado, com comparecimento zero. "
            "Essas ocorrências são documentadas como exceções da fonte e não são classificadas automaticamente como erro ou fraude."
        )
        with st.expander("Consultar as exceções publicadas"):
            st.dataframe(excecoes, width="stretch", hide_index=True)
    else:
        st.caption("O arquivo de exceções da ingestão ainda não está disponível.")

    cabecalho_secao(
        "Controle de qualidade",
        "Checagens executadas diretamente sobre o recorte selecionado.",
    )
    soma_comparecimento = "validos + brancos + nulos"
    if "anulados_apu_sep" in colunas:
        soma_comparecimento += " + anulados_apu_sep"
    qa = consultar(
        f"""
        SELECT
          COUNT(*) total,
          SUM(CASE WHEN aptos < 0 OR comparecimento < 0 OR abstencao < 0 OR validos < 0 OR brancos < 0 OR nulos < 0 THEN 1 ELSE 0 END) negativos,
          SUM(CASE WHEN participacao < 0 OR participacao > 1 OR participacao IS NULL THEN 1 ELSE 0 END) participacao_invalida,
          SUM(CASE WHEN aptos <> comparecimento + abstencao THEN 1 ELSE 0 END) balanco_eleitorado,
          SUM(CASE WHEN comparecimento <> {soma_comparecimento} THEN 1 ELSE 0 END) balanco_votos
        FROM read_parquet('{arquivo_secoes}') WHERE {filtro}
        """,
        parametros,
        fp_secoes,
    ).iloc[0]
    checks = [
        ("Valores negativos", int(qa["negativos"] or 0)),
        ("Participação fora de zero a um", int(qa["participacao_invalida"] or 0)),
        (
            "Aptos diferentes de comparecimento mais abstenção",
            int(qa["balanco_eleitorado"] or 0),
        ),
        (
            "Comparecimento diferente de válidos mais brancos, nulos e anulados separados",
            int(qa["balanco_votos"] or 0),
        ),
    ]
    for rotulo, quantidade in checks:
        classe = "qa-ok" if quantidade == 0 else "qa-warn"
        resultado = (
            "sem ocorrência"
            if quantidade == 0
            else f"{formatar_inteiro(quantidade)} ocorrência(s)"
        )
        st.markdown(
            f'<div class="{classe}"><strong>{rotulo}:</strong> {resultado}</div>',
            unsafe_allow_html=True,
        )
    st.caption(
        f"Arquivo processado: {formatar_inteiro(SECOES_PATH.stat().st_size)} bytes. Linhas verificadas no recorte: {formatar_inteiro(qa['total'])}."
    )

    cabecalho_secao(
        "Fontes e cobertura",
        "Os artefatos de origem e a data de coleta devem ser documentados pelo pipeline reproduzível.",
    )
    if RESUMO_PATH.exists():
        try:
            resumo_fonte = json.loads(RESUMO_PATH.read_text(encoding="utf-8"))
            st.json(resumo_fonte, expanded=False)
        except (json.JSONDecodeError, OSError):
            st.warning(
                "reports/resumo.json existe, mas não pôde ser lido como JSON válido."
            )
    else:
        st.caption(
            "O arquivo reports/resumo.json ainda não foi publicado nesta versão."
        )
    st.markdown(
        "Fonte institucional: [Resultados eleitorais do TSE](https://dadosabertos.tse.jus.br/)"
    )

with tabs[5]:
    cabecalho_secao(
        "Horário de encerramento em 2026",
        "A dimensão temporal exige fonte própria. A base de votação por seção usada neste painel não liga horário de log a candidato.",
    )
    st.info(
        "O TSE informou prorrogação excepcional da votação até 19h em 25 de outubro de 2026, "
        "somente nas seções que ainda não haviam encerrado às 17h. Esse fato não permite atribuir votos por horário ou candidatura."
    )
    st.markdown(
        "[Ler o esclarecimento oficial do TSE](https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/esclarecimento-sobre-prorrogacao-da-votacao)"
    )
    st.warning(
        "Não é possível concluir, a partir desta base, por que uma seção encerrou depois das 17h. "
        "Fila pode ser uma hipótese operacional, mas não é a única explicação documentada."
    )

st.caption(
    "Observatório do voto 2026 | Análise descritiva com dados agregados por seção eleitoral"
)
