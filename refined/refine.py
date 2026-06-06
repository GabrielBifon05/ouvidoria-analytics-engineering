"""
OuvidorIA Pipeline — Etapa 3: Refined Layer (Star Schema)
Versão AWS Glue
"""

import sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from awsglue.utils import getResolvedOptions

# Pega os argumentos passados pelo Glue Job
args = getResolvedOptions(sys.argv, ["input_path", "output_path"])

INPUT_PATH  = args["input_path"]   # s3://ouvidoria-trusted-gabrielbifon/
OUTPUT_PATH = args["output_path"]  # s3://ouvidoria-refined-gabrielbifon/

print(f"Input : {INPUT_PATH}")
print(f"Output: {OUTPUT_PATH}")

# -------------------------------------------------------
# SparkSession — no Glue não precisa de master, ele gerencia
# -------------------------------------------------------
spark = SparkSession.builder \
    .appName("OuvidorIA - Refined Layer") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")
print("SparkSession criada!")

# -------------------------------------------------------
# Carregar Trusted Layer
# -------------------------------------------------------
trusted_path = INPUT_PATH + "manifestacoes.parquet"
print(f"Lendo Trusted Layer: {trusted_path}")
df = spark.read.parquet(trusted_path)
print(f"Total de linhas: {df.count()}")

# -------------------------------------------------------
# Criar dimensões
# -------------------------------------------------------
print("\nCriando dim_tipo...")
window_tipo = Window.orderBy("tipo_manifestacao")
dim_tipo = df.select("tipo_manifestacao").distinct().orderBy("tipo_manifestacao")
dim_tipo = dim_tipo.withColumn("sk_tipo", F.row_number().over(window_tipo))
dim_tipo = dim_tipo.select("sk_tipo", "tipo_manifestacao")
print(f"dim_tipo: {dim_tipo.count()} registros")
dim_tipo.show()

print("\nCriando dim_orgao...")
window_orgao = Window.orderBy("nome_orgao")
dim_orgao = df.select("nome_orgao").distinct().orderBy("nome_orgao")
dim_orgao = dim_orgao.withColumn("sk_orgao", F.row_number().over(window_orgao))
dim_orgao = dim_orgao.select("sk_orgao", "nome_orgao")
print(f"dim_orgao: {dim_orgao.count()} registros")

print("\nCriando dim_safety...")
window_safety = Window.orderBy("prompt_safety_issues_clean", "response_safety_issues_clean")
dim_safety = df.select(
    "prompt_safety_issues_clean",
    "response_safety_issues_clean"
).distinct().orderBy("prompt_safety_issues_clean", "response_safety_issues_clean")
dim_safety = dim_safety.withColumn("sk_safety", F.row_number().over(window_safety))
dim_safety = dim_safety.select("sk_safety", "prompt_safety_issues_clean", "response_safety_issues_clean")
print(f"dim_safety: {dim_safety.count()} registros")

print("\nCriando dim_tempo...")
window_tempo = Window.orderBy("ingested_at")
dim_tempo = df.select(
    F.to_timestamp("_ingested_at").alias("ingested_at")
).distinct()
dim_tempo = dim_tempo \
    .withColumn("ano",        F.year("ingested_at")) \
    .withColumn("mes",        F.month("ingested_at")) \
    .withColumn("dia",        F.dayofmonth("ingested_at")) \
    .withColumn("dia_semana", F.dayofweek("ingested_at"))
dim_tempo = dim_tempo.withColumn("sk_tempo", F.row_number().over(window_tempo))
dim_tempo = dim_tempo.select("sk_tempo", "ingested_at", "ano", "mes", "dia", "dia_semana")
print(f"dim_tempo: {dim_tempo.count()} registros")

# -------------------------------------------------------
# Criar tabela fato
# -------------------------------------------------------
print("\nCriando fato_manifestacoes...")
fato = df.withColumn("ingested_at", F.to_timestamp("_ingested_at"))
fato = fato.join(dim_tipo,   on="tipo_manifestacao", how="left")
fato = fato.join(dim_orgao,  on="nome_orgao",        how="left")
fato = fato.join(dim_safety,
                 on=["prompt_safety_issues_clean", "response_safety_issues_clean"],
                 how="left")
fato = fato.join(dim_tempo,  on="ingested_at",       how="left")
fato = fato.select(
    "sk_tipo", "sk_orgao", "sk_safety", "sk_tempo",
    "assunto",
    F.lit(1).alias("quantidade")
)
print(f"fato_manifestacoes: {fato.count()} registros")

# -------------------------------------------------------
# Salvar Refined Layer no S3
# -------------------------------------------------------
print("\nSalvando Refined Layer no S3...")
dim_tipo.write.mode("overwrite").parquet(OUTPUT_PATH + "dim_tipo/")
dim_orgao.write.mode("overwrite").parquet(OUTPUT_PATH + "dim_orgao/")
dim_safety.write.mode("overwrite").parquet(OUTPUT_PATH + "dim_safety/")
dim_tempo.write.mode("overwrite").parquet(OUTPUT_PATH + "dim_tempo/")
fato.write.mode("overwrite").parquet(OUTPUT_PATH + "fato_manifestacoes/")

print("\n✅ Refined Layer concluída!")
print(f"   dim_tipo          : {dim_tipo.count()} registros")
print(f"   dim_orgao         : {dim_orgao.count()} registros")
print(f"   dim_safety        : {dim_safety.count()} registros")
print(f"   dim_tempo         : {dim_tempo.count()} registros")
print(f"   fato_manifestacoes: {fato.count()} registros")

spark.stop()