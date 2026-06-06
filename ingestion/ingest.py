"""
OuvidorIA Pipeline — Etapa 1: Ingestão (Raw Layer)
Versão AWS Glue
"""

import json
import sys
from datetime import datetime, timezone

import boto3
import pandas as pd
from awsglue.utils import getResolvedOptions

# Pega os argumentos passados pelo Glue Job
args = getResolvedOptions(sys.argv, ["input_path", "output_path"])

INPUT_PATH  = args["input_path"]   # s3://ouvidoria-raw-gabrielbifon/brazilian_gov_formal_letters.csv
OUTPUT_PATH = args["output_path"]  # s3://ouvidoria-raw-gabrielbifon/

print(f"Input : {INPUT_PATH}")
print(f"Output: {OUTPUT_PATH}")

# -------------------------------------------------------
# Funções (mesmas de antes)
# -------------------------------------------------------

def clean_safety(value):
    if pd.isna(value):
        return "none"
    value = str(value).strip()
    if value == "" or value == "[]" or value == "nan":
        return "none"
    value = value.replace("[", "").replace("]", "").replace('"', "").replace("'", "").strip()
    return value if value else "none"


def generate_quality_report(df):
    report = {}
    report["timestamp"] = datetime.now(timezone.utc).isoformat()
    report["total_rows"] = len(df)
    report["total_columns"] = len(df.columns)
    report["columns"] = list(df.columns)

    null_counts = {}
    for col in df.columns:
        null_counts[col] = int(df[col].isnull().sum())
    report["null_counts"] = null_counts

    if "tipo_manifestacao" in df.columns:
        dist = df["tipo_manifestacao"].value_counts(dropna=False)
        report["tipo_manifestacao_dist"] = {str(k): int(v) for k, v in dist.items()}

    if "prompt_safety_issues_clean" in df.columns:
        dist = df["prompt_safety_issues_clean"].value_counts(dropna=False)
        report["safety_prompt_dist"] = {str(k): int(v) for k, v in dist.items()}

    return report


# -------------------------------------------------------
# Pipeline
# -------------------------------------------------------

print("Lendo CSV do S3...")
df = pd.read_csv(INPUT_PATH, encoding="utf-8")
print(f"Carregado! Linhas: {len(df)}, Colunas: {len(df.columns)}")

# Metadados
df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
df["_source_file"] = INPUT_PATH.split("/")[-1]

# Safety
print("Limpando campos de safety...")
if "prompt_safety_issues" in df.columns:
    df["prompt_safety_issues_clean"] = df["prompt_safety_issues"].apply(clean_safety)
if "response_safety_issues" in df.columns:
    df["response_safety_issues_clean"] = df["response_safety_issues"].apply(clean_safety)

# Quality report
print("Gerando quality report...")
report = generate_quality_report(df)

print(f"  Total de linhas: {report['total_rows']}")
print("  Distribuição tipo_manifestacao:")
for tipo, count in report["tipo_manifestacao_dist"].items():
    print(f"    {tipo}: {count}")

# Salva quality report no S3
s3 = boto3.client("s3")
bucket = OUTPUT_PATH.replace("s3://", "").split("/")[0]
s3.put_object(
    Bucket=bucket,
    Key="quality_report.json",
    Body=json.dumps(report, ensure_ascii=False, indent=2, default=str)
)
print(f"Quality report salvo em: {OUTPUT_PATH}quality_report.json")

# Salva Parquet no S3
parquet_path = OUTPUT_PATH + "brazilian_gov_formal_letters.parquet"
df.to_parquet(parquet_path, index=False, engine="pyarrow")
print(f"Parquet salvo em: {parquet_path}")

print("✅ Ingestão concluída.")