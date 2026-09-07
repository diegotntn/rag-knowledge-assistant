terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "docs" {
  bucket = "rag-assistant-docs-diego-tf"
}

resource "aws_iam_role" "lambda_role" {
  name = "rag-lambda-s3-reader-tf"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "s3_read" {
  name = "s3-read-only"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = "${aws_s3_bucket.docs.arn}/*"
    }]
  })
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../lambdas/ingest/handler.py"
  output_path = "lambda_function.zip"
}

resource "aws_lambda_function" "s3_trigger" {
  function_name    = "rag-s3-trigger-tf"
  runtime          = "python3.12"
  handler          = "handler.handler"
  role             = aws_iam_role.lambda_role.arn
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  layers           = [aws_lambda_layer_version.pypdf.arn]
  timeout          = 60
  memory_size      = 512

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.chunks.name
    }
  }
}

resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.s3_trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.docs.arn
}

resource "aws_s3_bucket_notification" "trigger" {
  bucket = aws_s3_bucket.docs.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.s3_trigger.arn
    events              = ["s3:ObjectCreated:*"]
  }
  depends_on = [aws_lambda_permission.allow_s3]
}