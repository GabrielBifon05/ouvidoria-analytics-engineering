output "bucket_raw" {
  value = aws_s3_bucket.raw.bucket
}

output "bucket_trusted" {
  value = aws_s3_bucket.trusted.bucket
}

output "bucket_refined" {
  value = aws_s3_bucket.refined.bucket
}

output "bucket_scripts" {
  value = aws_s3_bucket.scripts.bucket
}

output "glue_job_ingest" {
  value = aws_glue_job.ingest.name
}

output "glue_job_transform" {
  value = aws_glue_job.transform.name
}

output "glue_job_refine" {
  value = aws_glue_job.refine.name
}

output "glue_catalog_database" {
  value = aws_glue_catalog_database.ouvidoria.name
}

output "athena_workgroup" {
  value = aws_athena_workgroup.ouvidoria.name
}

output "lambda_trigger" {
  value = aws_lambda_function.trigger_glue.function_name
}