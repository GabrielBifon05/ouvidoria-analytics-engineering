variable "aws_region" {
  description = "Região AWS"
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nome base do projeto"
  default     = "ouvidoria"
}

variable "student_name" {
  description = "Nome do estudante para unicidade dos buckets"
  default     = "gabrielbifon"
}

variable "account_id" {
  description = "ID da conta AWS"
  default     = "958228573368"
}