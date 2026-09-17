resource "aws_lambda_layer_version" "faiss" {
  layer_name          = "faiss-layer"
  filename            = "${path.module}/../lambdas/layers/faiss-layer.zip"
  compatible_runtimes = ["python3.12"]
}