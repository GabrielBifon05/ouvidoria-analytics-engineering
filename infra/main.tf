terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# -------------------------------------------------------
# S3 — Raw Layer
# -------------------------------------------------------
resource "aws_s3_bucket" "raw" {
  bucket        = "${var.project_name}-raw-${var.student_name}"
  force_destroy = true

  tags = {
    Project = var.project_name
    Layer   = "raw"
  }
}

# -------------------------------------------------------
# S3 — Trusted Layer
# -------------------------------------------------------
resource "aws_s3_bucket" "trusted" {
  bucket        = "${var.project_name}-trusted-${var.student_name}"
  force_destroy = true

  tags = {
    Project = var.project_name
    Layer   = "trusted"
  }
}

# -------------------------------------------------------
# S3 — Refined Layer
# -------------------------------------------------------
resource "aws_s3_bucket" "refined" {
  bucket        = "${var.project_name}-refined-${var.student_name}"
  force_destroy = true

  tags = {
    Project = var.project_name
    Layer   = "refined"
  }
}

# -------------------------------------------------------
# S3 — Scripts (Glue vai ler os scripts daqui)
# -------------------------------------------------------
resource "aws_s3_bucket" "scripts" {
  bucket        = "${var.project_name}-scripts-${var.student_name}"
  force_destroy = true

  tags = {
    Project = var.project_name
    Layer   = "scripts"
  }
}

# -------------------------------------------------------
# Glue Job — Ingestão (Raw Layer)
# -------------------------------------------------------
resource "aws_glue_job" "ingest" {
  name         = "${var.project_name}-ingest"
  role_arn     = "arn:aws:iam::${var.account_id}:role/LabRole"
  glue_version = "4.0"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.scripts.bucket}/ingestion/ingest.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"        = "python"
    "--TempDir"             = "s3://${aws_s3_bucket.scripts.bucket}/tmp/"
    "--input_path"          = "s3://${aws_s3_bucket.raw.bucket}/brazilian_gov_formal_letters.csv"
    "--output_path"         = "s3://${aws_s3_bucket.raw.bucket}/"
  }

  max_retries       = 0
  number_of_workers = 2
  worker_type       = "G.1X"

  tags = {
    Project = var.project_name
    Layer   = "ingestion"
  }
}

# -------------------------------------------------------
# Glue Job — Transformação (Trusted Layer)
# -------------------------------------------------------
resource "aws_glue_job" "transform" {
  name         = "${var.project_name}-transform"
  role_arn     = "arn:aws:iam::${var.account_id}:role/LabRole"
  glue_version = "4.0"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.scripts.bucket}/transformation/transform.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language" = "python"
    "--TempDir"      = "s3://${aws_s3_bucket.scripts.bucket}/tmp/"
    "--input_path"   = "s3://${aws_s3_bucket.raw.bucket}/"
    "--output_path"  = "s3://${aws_s3_bucket.trusted.bucket}/"
  }

  max_retries       = 0
  number_of_workers = 2
  worker_type       = "G.1X"

  tags = {
    Project = var.project_name
    Layer   = "transformation"
  }
}

# -------------------------------------------------------
# Glue Job — Refined Layer (PySpark)
# -------------------------------------------------------
resource "aws_glue_job" "refine" {
  name         = "${var.project_name}-refine"
  role_arn     = "arn:aws:iam::${var.account_id}:role/LabRole"
  glue_version = "4.0"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.scripts.bucket}/refined/refine.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language" = "python"
    "--TempDir"      = "s3://${aws_s3_bucket.scripts.bucket}/tmp/"
    "--input_path"   = "s3://${aws_s3_bucket.trusted.bucket}/"
    "--output_path"  = "s3://${aws_s3_bucket.refined.bucket}/"
  }

  max_retries       = 0
  number_of_workers = 2
  worker_type       = "G.1X"

  tags = {
    Project = var.project_name
    Layer   = "refined"
  }
}

# -------------------------------------------------------
# Glue Crawler — Cataloga o Refined Layer no Data Catalog
# -------------------------------------------------------
resource "aws_glue_crawler" "refined" {
  name          = "${var.project_name}-crawler-refined"
  role          = "arn:aws:iam::${var.account_id}:role/LabRole"
  database_name = aws_glue_catalog_database.ouvidoria.name

  s3_target {
    path = "s3://${aws_s3_bucket.refined.bucket}/"
  }

  tags = {
    Project = var.project_name
  }
}

# -------------------------------------------------------
# Glue Catalog Database — para o Athena consultar
# -------------------------------------------------------
resource "aws_glue_catalog_database" "ouvidoria" {
  name = "${var.project_name}_db"
}

# -------------------------------------------------------
# Athena — Workgroup para queries no S3
# -------------------------------------------------------
resource "aws_athena_workgroup" "ouvidoria" {
  name = "${var.project_name}-workgroup"

  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.scripts.bucket}/athena-results/"
    }
  }

  tags = {
    Project = var.project_name
  }
}

# -------------------------------------------------------
# Lambda — Trigger automático quando CSV cair no S3 Raw
# -------------------------------------------------------

# Zip do código Lambda
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda/trigger_glue.py"
  output_path = "${path.module}/../lambda/trigger_glue.zip"
}

resource "aws_lambda_function" "trigger_glue" {
  function_name    = "${var.project_name}-trigger-glue"
  role             = "arn:aws:iam::${var.account_id}:role/LabRole"
  handler          = "trigger_glue.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      GLUE_JOB_NAME = aws_glue_job.ingest.name
    }
  }

  tags = {
    Project = var.project_name
  }
}

# Permissão para o S3 invocar o Lambda
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.trigger_glue.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.raw.arn
}

# Notificação do S3 Raw para disparar o Lambda
resource "aws_s3_bucket_notification" "raw_trigger" {
  bucket = aws_s3_bucket.raw.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.trigger_glue.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.allow_s3]
}