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