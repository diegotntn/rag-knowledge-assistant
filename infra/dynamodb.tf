resource "aws_dynamodb_table" "chunks" {
  name         = "rag-chunks"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "tenant_id"
  range_key = "chunk_pk"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "chunk_pk"
    type = "S"
  }

  tags = {
    Project = "rag-knowledge-assistant"
  }
}