"""
Lambda — Trigger automático do Glue Job
----------------------------------------
Disparado quando um CSV é criado no bucket S3 Raw.
Inicia o Glue Job de ingestão automaticamente.
"""

import json
import os
import boto3

def lambda_handler(event, context):
    glue_job_name = os.environ["GLUE_JOB_NAME"]

    # Pega o nome do arquivo que chegou no S3
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key    = event["Records"][0]["s3"]["object"]["key"]

    print(f"Arquivo detectado: s3://{bucket}/{key}")
    print(f"Disparando Glue Job: {glue_job_name}")

    # Inicia o Glue Job
    glue = boto3.client("glue")
    response = glue.start_job_run(
        JobName=glue_job_name,
        Arguments={
            "--input_path": f"s3://{bucket}/{key}"
        }
    )

    job_run_id = response["JobRunId"]
    print(f"Glue Job iniciado! JobRunId: {job_run_id}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Glue Job disparado com sucesso",
            "job_run_id": job_run_id
        })
    }