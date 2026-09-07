resource "aws_iam_role_policy" "dynamodb_write" {
  name = "dynamodb-write-chunks"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:BatchWriteItem", "dynamodb:PutItem"]
      Resource = aws_dynamodb_table.chunks.arn
    }]
  })
}

resource "aws_iam_role_policy" "sqs_dlq_send" {
  name = "sqs-send-dlq"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = aws_sqs_queue.ingestion_dlq.arn
    }]
  })
}

resource "aws_lambda_function_event_invoke_config" "s3_trigger_retry" {
  function_name          = aws_lambda_function.s3_trigger.function_name
  maximum_retry_attempts = 2

  destination_config {
    on_failure {
      destination = aws_sqs_queue.ingestion_dlq.arn
    }
  }
}