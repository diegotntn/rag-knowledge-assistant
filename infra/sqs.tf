resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "rag-ingestion-dlq"
  message_retention_seconds = 1209600 # 14 días
}