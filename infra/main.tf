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

# -------------------------------------------------------
# Glue Workflow — Orquestração automática do pipeline
# -------------------------------------------------------
resource "aws_glue_workflow" "pipeline" {
  name = "${var.project_name}-pipeline"

  tags = {
    Project = var.project_name
  }
}

# Trigger inicial — dispara o ingest
resource "aws_glue_trigger" "start_ingest" {
  name          = "${var.project_name}-start-ingest"
  type          = "ON_DEMAND"
  workflow_name = aws_glue_workflow.pipeline.name

  actions {
    job_name = aws_glue_job.ingest.name
    arguments = {
      "--input_path"  = "s3://${aws_s3_bucket.raw.bucket}/brazilian_gov_formal_letters.csv"
      "--output_path" = "s3://${aws_s3_bucket.raw.bucket}/"
    }
  }
}

# Trigger — quando ingest terminar, dispara transform
resource "aws_glue_trigger" "start_transform" {
  name          = "${var.project_name}-start-transform"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.pipeline.name

  predicate {
    conditions {
      job_name = aws_glue_job.ingest.name
      state    = "SUCCEEDED"
    }
  }

  actions {
    job_name = aws_glue_job.transform.name
    arguments = {
      "--input_path"  = "s3://${aws_s3_bucket.raw.bucket}/"
      "--output_path" = "s3://${aws_s3_bucket.trusted.bucket}/"
    }
  }
}

# Trigger — quando transform terminar, dispara refine
resource "aws_glue_trigger" "start_refine" {
  name          = "${var.project_name}-start-refine"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.pipeline.name

  predicate {
    conditions {
      job_name = aws_glue_job.transform.name
      state    = "SUCCEEDED"
    }
  }

  actions {
    job_name = aws_glue_job.refine.name
    arguments = {
      "--input_path"  = "s3://${aws_s3_bucket.trusted.bucket}/"
      "--output_path" = "s3://${aws_s3_bucket.refined.bucket}/"
    }
  }
}

# -------------------------------------------------------
# VPC + Subnet + Internet Gateway
# -------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Project = var.project_name
    Name    = "${var.project_name}-vpc"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"

  tags = {
    Project = var.project_name
    Name    = "${var.project_name}-subnet-public"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Project = var.project_name
    Name    = "${var.project_name}-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# -------------------------------------------------------
# Security Group — libera SSH e porta do Streamlit
# -------------------------------------------------------
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Streamlit dashboard"
  vpc_id      = aws_vpc.main.id

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Streamlit
  ingress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Saída livre
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = var.project_name
  }
}

# -------------------------------------------------------
# EC2 — Streamlit Dashboard
# -------------------------------------------------------
resource "aws_instance" "streamlit" {
  ami           = "ami-0c7217cdde317cfec" # Ubuntu 22.04 us-east-1
  instance_type = "t2.micro"
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = "ouvidoria-key"

  # Script que roda automaticamente ao iniciar a instância
  user_data = <<-EOF
    #!/bin/bash
    apt update -y
    apt install -y python3 python3-pip git

    pip3 install streamlit plotly pandas pyarrow boto3 fsspec s3fs

    mkdir -p /home/ubuntu/dashboard

    aws s3 cp s3://${aws_s3_bucket.scripts.bucket}/dashboard/app.py /home/ubuntu/dashboard/app.py

    cd /home/ubuntu/dashboard
    nohup streamlit run app.py \
      --server.port 8501 \
      --server.address 0.0.0.0 \
      > /home/ubuntu/streamlit.log 2>&1 &
  EOF

  tags = {
    Project = var.project_name
    Name    = "${var.project_name}-streamlit"
  }
}

# IAM Instance Profile para o EC2 acessar o S3
resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = "LabRole"
}





