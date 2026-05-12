"""
OuvidorIA Pipeline — Etapa 3: Refined Layer (Star Schema)
----------------------------------------------------------
Lê a Trusted Layer com PySpark, cria as dimensões e a tabela
fato no modelo Star Schema e salva na Refined Layer.

Uso:
    python refined/refine.py
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Caminhos
TRUSTED_PATH = "data/trusted/manifestacoes.parquet"
REFINED_DIR = "data/refined"
os.makedirs(REFINED_DIR, exist_ok=True)

# -------------------------------------------------------
# 1. Iniciar PySpark
# -------------------------------------------------------
print("Iniciando SparkSession...")
spark = SparkSession.builder \
    .appName("OuvidorIA - Refined Layer") \
    .master("local[*]") \
    .getOrCreate()

# Reduzind os logs do Spark no terminal, só mostrando warnings e erros
spark.sparkContext.setLogLevel("WARN")
print("SparkSession criada!")

# -------------------------------------------------------
# 2. Ler a Trusted Layer
# -------------------------------------------------------
print(f"\nLendo Trusted Layer: {TRUSTED_PATH}")
df = spark.read.parquet(TRUSTED_PATH)
print(f"Total de linhas carregadas: {df.count()}")

# -------------------------------------------------------
# 3. Criar dim_tipo
# Pega os valores únicos de tipo_manifestacao e cria um ID
# -------------------------------------------------------
print("\nCriando dim_tipo...")

# Pega só os valores distintos da coluna
dim_tipo = df.select("tipo_manifestacao").distinct().orderBy("tipo_manifestacao")

# Cria uma chave numérica única para cada tipo (sk = surrogate key)
# row_number() gera um número sequencial ordenado para a sk_tipo
window_tipo = Window.orderBy("tipo_manifestacao")
dim_tipo = dim_tipo.withColumn("sk_tipo", F.row_number().over(window_tipo))

# Reordena as colunas: chave primeiro, depois o valor
dim_tipo = dim_tipo.select("sk_tipo", "tipo_manifestacao")

print(f"dim_tipo criada com {dim_tipo.count()} registros:")
dim_tipo.show()

# -------------------------------------------------------
# 4. Criar dim_orgao
# -------------------------------------------------------
print("\nCriando dim_orgao...")

dim_orgao = df.select("nome_orgao").distinct().orderBy("nome_orgao")

window_orgao = Window.orderBy("nome_orgao")
dim_orgao = dim_orgao.withColumn("sk_orgao", F.row_number().over(window_orgao))
dim_orgao = dim_orgao.select("sk_orgao", "nome_orgao")

print(f"dim_orgao criada com {dim_orgao.count()} registros")

# -------------------------------------------------------
# 5. Criar dim_safety
# -------------------------------------------------------
print("\nCriando dim_safety...")

#prompt_safety + response_safety (por tratarem do mesmo resultado)
dim_safety = df.select(
    "prompt_safety_issues_clean",
    "response_safety_issues_clean"
).distinct().orderBy("prompt_safety_issues_clean", "response_safety_issues_clean")

window_safety = Window.orderBy("prompt_safety_issues_clean", "response_safety_issues_clean")
dim_safety = dim_safety.withColumn("sk_safety", F.row_number().over(window_safety))
dim_safety = dim_safety.select("sk_safety", "prompt_safety_issues_clean", "response_safety_issues_clean")

print(f"dim_safety criada com {dim_safety.count()} registros:")
# pode gerar Warn de WindowExec por não ter feito várias partições de acordo com a linha 27, mas o tamanho do dataset não necessita disso
dim_safety.show()

# -------------------------------------------------------
# 6. Criar dim_tempo
# -------------------------------------------------------
print("\nCriando dim_tempo...")

dim_tempo = df.select(
    F.to_timestamp("_ingested_at").alias("ingested_at")
).distinct()

# Extrai partes da data
dim_tempo = dim_tempo \
    .withColumn("ano",       F.year("ingested_at")) \
    .withColumn("mes",       F.month("ingested_at")) \
    .withColumn("dia",       F.dayofmonth("ingested_at")) \
    .withColumn("dia_semana", F.dayofweek("ingested_at"))

window_tempo = Window.orderBy("ingested_at")
dim_tempo = dim_tempo.withColumn("sk_tempo", F.row_number().over(window_tempo))
dim_tempo = dim_tempo.select("sk_tempo", "ingested_at", "ano", "mes", "dia", "dia_semana")

print(f"dim_tempo criada com {dim_tempo.count()} registros:")
dim_tempo.show()

# -------------------------------------------------------
# 7. Criar fato_manifestacoes
# Tabela principal com uma linha por manifestação
# Faz join com cada dimensão para trazer a surrogate key
# -------------------------------------------------------
print("\nCriando fato_manifestacoes...")

# Começa com o dataframe completo
fato = df.withColumn("ingested_at", F.to_timestamp("_ingested_at"))

# para pegar sk_tipo
fato = fato.join(dim_tipo, on="tipo_manifestacao", how="left")

# sk_orgao
fato = fato.join(dim_orgao, on="nome_orgao", how="left")

# sk_safety
fato = fato.join(dim_safety,
                 on=["prompt_safety_issues_clean", "response_safety_issues_clean"],
                 how="left")

# sk_tempo
fato = fato.join(dim_tempo, on="ingested_at", how="left")

# Seleciona só as colunas que ficam na fato
# F.lit(1) cria uma coluna constante com valor 1 — usada para contar manifestações
fato = fato.select(
    "sk_tipo",
    "sk_orgao",
    "sk_safety",
    "sk_tempo",
    "assunto",
    F.lit(1).alias("quantidade")
)

print(f"fato_manifestacoes criada com {fato.count()} registros")

# -------------------------------------------------------
# 8. Salvar tudo na Refined Layer
# -------------------------------------------------------
print("\nSalvando Refined Layer...")

dim_tipo.write.mode("overwrite").parquet(f"{REFINED_DIR}/dim_tipo")
print("dim_tipo salva!")

dim_orgao.write.mode("overwrite").parquet(f"{REFINED_DIR}/dim_orgao")
print("dim_orgao salva!")

dim_safety.write.mode("overwrite").parquet(f"{REFINED_DIR}/dim_safety")
print("dim_safety salva!")

dim_tempo.write.mode("overwrite").parquet(f"{REFINED_DIR}/dim_tempo")
print("dim_tempo salva!")

fato.write.mode("overwrite").parquet(f"{REFINED_DIR}/fato_manifestacoes")
print("fato_manifestacoes salva!")

print("\n✅ Refined Layer concluída!")
print(f"   dim_tipo          : {dim_tipo.count()} registros")
print(f"   dim_orgao         : {dim_orgao.count()} registros")
print(f"   dim_safety        : {dim_safety.count()} registros")
print(f"   dim_tempo         : {dim_tempo.count()} registros")
print(f"   fato_manifestacoes: {fato.count()} registros")

spark.stop()