"""
OuvidorIA Pipeline — Etapa 2: Transformação (Trusted Layer)
Versão AWS Glue
"""

import sys
from datetime import datetime, timezone

import pandas as pd
from awsglue.utils import getResolvedOptions

# Pega os argumentos passados pelo Glue Job
args = getResolvedOptions(sys.argv, ["input_path", "output_path"])

INPUT_PATH  = args["input_path"]   # s3://ouvidoria-raw-gabrielbifon/
OUTPUT_PATH = args["output_path"]  # s3://ouvidoria-trusted-gabrielbifon/

print(f"Input : {INPUT_PATH}")
print(f"Output: {OUTPUT_PATH}")

# -------------------------------------------------------
# Funções
# -------------------------------------------------------

def clean_text_columns(df):
    text_cols = ["assunto", "nome_orgao", "tipo_manifestacao"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].str.strip()
            df[col] = df[col].str.replace(r"\s+", " ", regex=True)
    print("Colunas de texto limpas.")
    return df


def standardize_tipo(df):
    df["tipo_manifestacao"] = df["tipo_manifestacao"].str.capitalize()
    print("Distribuição tipo_manifestacao após padronização:")
    for tipo, count in df["tipo_manifestacao"].value_counts().items():
        print(f"  {tipo}: {count}")
    return df


def drop_raw_columns(df):
    cols_to_drop = ["prompt_safety_issues", "response_safety_issues"]
    cols_to_drop = [c for c in cols_to_drop if c in df.columns]
    df = df.drop(columns=cols_to_drop)
    print(f"Colunas removidas: {cols_to_drop}")
    return df


def add_metadata(df):
    df["_transformed_at"] = datetime.now(timezone.utc).isoformat()
    return df


# -------------------------------------------------------
# Pipeline
# -------------------------------------------------------

# Lê o Parquet da Raw Layer
parquet_input = INPUT_PATH + "brazilian_gov_formal_letters.parquet"
print(f"Lendo Parquet: {parquet_input}")
df = pd.read_parquet(parquet_input, engine="pyarrow")
print(f"Carregado! Linhas: {len(df)}, Colunas: {len(df.columns)}")

print("\n-- Limpando colunas de texto...")
df = clean_text_columns(df)

print("\n-- Padronizando tipo_manifestacao...")
df = standardize_tipo(df)

print("\n-- Removendo colunas brutas...")
df = drop_raw_columns(df)

df = add_metadata(df)

# Salva na Trusted Layer
trusted_path = OUTPUT_PATH + "manifestacoes.parquet"
df.to_parquet(trusted_path, index=False, engine="pyarrow")
print(f"\nTrusted Layer salva em: {trusted_path}")
print(f"✅ Transformação concluída. Registros: {len(df)}")