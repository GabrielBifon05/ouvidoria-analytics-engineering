"""
OuvidorIA Pipeline — Etapa 1: Ingestão (Raw Layer)
Lê o CSV, trata campos de safety e salva como Parquet.

Uso:
    python ingest.py --input brazilian_gov_formal_letters.csv
"""

import argparse
import json
from datetime import datetime, timezone

import pandas as pd

# Caminho onde os arquivos vão ser salvos
RAW_DIR = "data/raw"

# Cria a pasta se não existir
import os
os.makedirs(RAW_DIR, exist_ok=True)


# 1. Carregar o CSV
# -------------------------------------------------------
def load_csv(path):
    print(f"Lendo o arquivo: {path}")
    df = pd.read_csv(path, encoding="utf-8")
    print(f"Arquivo carregado! Total de linhas: {len(df)}, colunas: {len(df.columns)}")
    return df


# 2. Limpar os campos de safety
# -------------------------------------------------------
def clean_safety(value):
    """
    Esse campo vem bagunçado do CSV:
    - vazio ou NaN → retorna "none"
    - ["sexual"]   → retorna "sexual"
    """
    if pd.isna(value):
        return "none"

    value = str(value).strip()

    if value == "" or value == "[]" or value == "nan":
        return "none"

    # Remove os colchetes e aspas: ["sexual"] → sexual
    value = value.replace("[", "")
    value = value.replace("]", "")
    value = value.replace('"', "")
    value = value.replace("'", "")
    value = value.strip()

    if value == "":
        return "none"

    return value


# 3. Gerar relatório básico de qualidade
# -------------------------------------------------------
def generate_quality_report(df):
    report = {}

    report["timestamp"] = datetime.now(timezone.utc).isoformat()
    report["total_rows"] = len(df)
    report["total_columns"] = len(df.columns)
    report["columns"] = list(df.columns)

    # Contar valores nulos por coluna
    null_counts = {}
    for col in df.columns:
        null_counts[col] = int(df[col].isnull().sum())
    report["null_counts"] = null_counts

    # Distribuição de tipo_manifestacao
    if "tipo_manifestacao" in df.columns:
        dist = df["tipo_manifestacao"].value_counts(dropna=False)
        report["tipo_manifestacao_dist"] = {str(k): int(v) for k, v in dist.items()}

    # Distribuição dos campos de safety
    if "prompt_safety_issues_clean" in df.columns:
        dist = df["prompt_safety_issues_clean"].value_counts(dropna=False)
        report["safety_prompt_dist"] = {str(k): int(v) for k, v in dist.items()}

    return report


# 4. Rodar o pipeline
# -------------------------------------------------------
def run(input_path):
    # Passo 1: carregar
    df = load_csv(input_path)

    # Passo 2: adicionar colunas de controle
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    df["_source_file"] = input_path

    # Passo 3: limpar safety
    print("Limpando campos de safety...")
    if "prompt_safety_issues" in df.columns:
        df["prompt_safety_issues_clean"] = df["prompt_safety_issues"].apply(clean_safety)

    if "response_safety_issues" in df.columns:
        df["response_safety_issues_clean"] = df["response_safety_issues"].apply(clean_safety)

    # Passo 4: gerar relatório de qualidade
    print("Gerando relatório de qualidade...")
    report = generate_quality_report(df)

    print(f"  Total de linhas: {report['total_rows']}")
    print("  Distribuição tipo_manifestacao:")
    for tipo, count in report["tipo_manifestacao_dist"].items():
        print(f"    {tipo}: {count}")
    print("  Safety (prompt):")
    for tag, count in report["safety_prompt_dist"].items():
        print(f"    {tag}: {count}")

    # Passo 5: salvar relatório em JSON
    report_path = RAW_DIR + "/quality_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Relatório salvo em: {report_path}")

    # Passo 6: salvar como Parquet
    parquet_path = RAW_DIR + "/brazilian_gov_formal_letters.parquet"
    df.to_parquet(parquet_path, index=False, engine="pyarrow")
    print(f"Parquet salvo em: {parquet_path}")

    print("Ingestão concluída!")


# -------------------------------------------------------
# Entry point
# -------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Caminho para o CSV")
    args = parser.parse_args()

    run(args.input)