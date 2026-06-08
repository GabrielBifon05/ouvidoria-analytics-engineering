"""
OuvidorIA Pipeline — Dashboard
--------------------------------
Consume a Refined Layer e exibe análises das manifestações.

Uso:
    streamlit run dashboard/app.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st

# -------------------------------------------------------
# Configuração da página
# -------------------------------------------------------
st.set_page_config(
    page_title="OuvidorIA — Análise de Manifestações",
    page_icon="📋",
    layout="wide"
)

# -------------------------------------------------------
# 1. Carregar os dados da Refined Layer
# -------------------------------------------------------

# Usamos cache para não recarregar toda vez que o usuário
# interage com o dashboard
@st.cache_data
def load_data():
    fato      = pd.read_parquet("s3://ouvidoria-refined-gabrielbifon/fato_manifestacoes/")
    dim_tipo  = pd.read_parquet("s3://ouvidoria-refined-gabrielbifon/dim_tipo/")
    dim_orgao = pd.read_parquet("s3://ouvidoria-refined-gabrielbifon/dim_orgao/")

    # Join fato com dimensões para ter os nomes legíveis
    df = fato.merge(dim_tipo,  on="sk_tipo",  how="left")
    df = df.merge(dim_orgao, on="sk_orgao", how="left")

    return df

df = load_data()

# -------------------------------------------------------
# 2. Cabeçalho
# -------------------------------------------------------
st.title("📋 OuvidorIA — Análise de Manifestações")
st.markdown("Análise das manifestações registradas no sistema de Ouvidoria do Governo Federal.")
st.divider()

# -------------------------------------------------------
# 3. Métricas gerais no topo
# -------------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("Total de Manifestações", f"{len(df):,}".replace(",", "."))
col2.metric("Tipos de Manifestação",  df["tipo_manifestacao"].nunique())
col3.metric("Órgãos Envolvidos",      df["nome_orgao"].nunique())

st.divider()

# -------------------------------------------------------
# 4. Gráficos lado a lado
# -------------------------------------------------------
col_esq, col_dir = st.columns(2)

# Gráfico 1 — Volume por tipo de manifestação
with col_esq:
    st.subheader("Volume por Tipo de Manifestação")

    contagem_tipo = df["tipo_manifestacao"].value_counts().reset_index()
    contagem_tipo.columns = ["Tipo", "Quantidade"]

    fig_tipo = px.bar(
        contagem_tipo,
        x="Tipo",
        y="Quantidade",
        color="Tipo",
        text="Quantidade",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_tipo.update_traces(textposition="outside")
    fig_tipo.update_layout(showlegend=False)
    st.plotly_chart(fig_tipo, use_container_width=True)

# Gráfico 2 — Pizza por tipo
with col_dir:
    st.subheader("Proporção por Tipo")

    fig_pizza = px.pie(
        contagem_tipo,
        names="Tipo",
        values="Quantidade",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_pizza.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_pizza, use_container_width=True)

st.divider()

# -------------------------------------------------------
# 5. Top 10 órgãos
# -------------------------------------------------------
st.subheader("Top 10 Órgãos com Mais Manifestações")

top_orgaos = df["nome_orgao"].value_counts().head(10).reset_index()
top_orgaos.columns = ["Órgão", "Quantidade"]

fig_orgaos = px.bar(
    top_orgaos,
    x="Quantidade",
    y="Órgão",
    orientation="h",
    text="Quantidade",
    color="Quantidade",
    color_continuous_scale="Blues"
)
fig_orgaos.update_traces(textposition="outside")
fig_orgaos.update_layout(yaxis=dict(autorange="reversed"))
st.plotly_chart(fig_orgaos, use_container_width=True)

st.divider()

# -------------------------------------------------------
# 6. Filtro interativo por tipo
# -------------------------------------------------------
st.subheader("Explorar por Tipo de Manifestação")

tipo_selecionado = st.selectbox(
    "Selecione um tipo:",
    options=["Todos"] + sorted(df["tipo_manifestacao"].unique().tolist())
)

if tipo_selecionado == "Todos":
    df_filtrado = df.copy()
else:
    df_filtrado = df[df["tipo_manifestacao"] == tipo_selecionado]

# Top 10 órgãos do tipo selecionado
top_filtrado = df_filtrado["nome_orgao"].value_counts().head(10).reset_index()
top_filtrado.columns = ["Órgão", "Quantidade"]

fig_filtrado = px.bar(
    top_filtrado,
    x="Quantidade",
    y="Órgão",
    orientation="h",
    text="Quantidade",
    color="Quantidade",
    color_continuous_scale="Oranges",
    title=f"Top 10 Órgãos — {tipo_selecionado}"
)
fig_filtrado.update_traces(textposition="outside")
fig_filtrado.update_layout(yaxis=dict(autorange="reversed"))
st.plotly_chart(fig_filtrado, use_container_width=True)

# Tabela com os dados filtrados
st.subheader(f"Dados — {tipo_selecionado}")
st.dataframe(
    df_filtrado[["tipo_manifestacao", "nome_orgao", "assunto", "quantidade"]],
    use_container_width=True,
    hide_index=True
)