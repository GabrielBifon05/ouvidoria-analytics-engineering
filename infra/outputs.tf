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