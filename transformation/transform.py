"""
OuvidorIA Pipeline — Etapa 2: Transformação (Trusted Layer)
------------------------------------------------------------
Lê o Parquet da Raw Layer, limpa e padroniza os dados,
separa registros em quarentena e salva na Trusted Layer.

Uso:
    python transformation/transform.py
"""

import json
import os
from datetime import datetime, timezone

import pandas as pd

# Caminhos
RAW_PATH = "data/raw/brazilian_gov_formal_letters.parquet"
TRUSTED_DIR = "data/trusted"
os.makedirs(TRUSTED_DIR, exist_ok=True)


# 1. Carregar o Parquet da Raw Layer
# -------------------------------------------------------
def load_parquet(path):
    print(f"Lendo Parquet: {path}")
    df = pd.read_parquet(path, engine="pyarrow")
    print(f"Carregado! Linhas: {len(df)}, Colunas: {len(df.columns)}")
    return df


# 2. Separar registros em quarentena (safety = "sexual")
# -------------------------------------------------------
def split_quarantine(df):
    mask = (df["prompt_safety_issues_clean"] == "sexual") | \
           (df["response_safety_issues_clean"] == "sexual")

    df_quarantine = df[mask].copy()
    df_clean = df[~mask].copy()

    print(f"Registros em quarentena: {len(df_quarantine)}")
    print(f"Registros limpos: {len(df_clean)}")
    return df_clean, df_quarantine


# 3. Limpar colunas de texto
# -------------------------------------------------------
def clean_text_columns(df):
    text_cols = ["assunto", "nome_orgao", "tipo_manifestacao"]

    for col in text_cols:
        if col in df.columns:
            # Remove espaços extras no início e fim
            df[col] = df[col].str.strip()
            # Substitui espaços duplos por simples
            df[col] = df[col].str.replace(r"\s+", " ", regex=True)

    print("Colunas de texto limpas.")
    return df


# 4. Padronizar tipo_manifestacao
# -------------------------------------------------------
def standardize_tipo(df):
    # Garante que a primeira letra é maiúscula e o resto minúsculo
    df["tipo_manifestacao"] = df["tipo_manifestacao"].str.capitalize()

    print("Distribuição tipo_manifestacao após padronização:")
    for tipo, count in df["tipo_manifestacao"].value_counts().items():
        print(f"  {tipo}: {count}")

    return df


# 5. Dropar colunas brutas que já foram tratadas
# -------------------------------------------------------
def drop_raw_columns(df):
    cols_to_drop = ["prompt_safety_issues", "response_safety_issues"]
    cols_to_drop = [c for c in cols_to_drop if c in df.columns]
    df = df.drop(columns=cols_to_drop)
    print(f"Colunas removidas: {cols_to_drop}")
    return df


# 6. Adicionar metadados da transformação
# -------------------------------------------------------
def add_metadata(df):
    df["_transformed_at"] = datetime.now(timezone.utc).isoformat()
    return df


# 7. Gerar quality report da Trusted Layer
# -------------------------------------------------------
def generate_quality_report(df):
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(df),
        "columns": list(df.columns),
        "null_counts": {k: int(v) for k, v in df.isnull().sum().items()},
        "tipo_manifestacao_dist": {
            str(k): int(v)
            for k, v in df["tipo_manifestacao"].value_counts(dropna=False).items()
        },
        "nome_orgao_top10": {
            str(k): int(v)
            for k, v in df["nome_orgao"].value_counts().head(10).items()
        },
    }
    return report


# Pipeline principal
# -------------------------------------------------------
def run():
    df = load_parquet(RAW_PATH)

    print("\n-- Limpando colunas de texto...")
    df = clean_text_columns(df)

    print("\n-- Padronizando tipo_manifestacao...")
    df = standardize_tipo(df)

    print("\n-- Removendo colunas brutas...")
    df = drop_raw_columns(df)

    df = add_metadata(df)

    print("\n-- Gerando quality report...")
    report = generate_quality_report(df)
    report_path = TRUSTED_DIR + "/quality_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Quality report salvo em: {report_path}")

    trusted_path = TRUSTED_DIR + "/manifestacoes.parquet"
    df.to_parquet(trusted_path, index=False, engine="pyarrow")
    print(f"Trusted Layer salva em: {trusted_path}")

    print(f"\n✅ Transformação concluída. Registros: {len(df)}")


if __name__ == "__main__":
    run()