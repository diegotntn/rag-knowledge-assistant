data "archive_file" "query_zip" {
  type        = "zip"
  source_file = "../lambdas/query/handler.py"
  output_path = "query_function.zip"
}

resource "aws_lambda_function" "query" {
  function_name    = "rag-query-tf"
  runtime          = "python3.12"
  handler          = "handler.handler"
  role             = aws_iam_role.lambda_role.arn
  filename         = data.archive_file.query_zip.output_path
  source_code_hash = data.archive_file.query_zip.output_base64sha256
  layers           = [aws_lambda_layer_version.faiss.arn]
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      DOCS_BUCKET         = aws_s3_bucket.docs.id
      HUGGINGFACE_API_KEY = var.huggingface_api_key
      GROQ_API_KEY        = var.groq_api_key
    }
  }
}