resource "aws_lambda_layer_version" "pypdf" {
  layer_name          = "pypdf-layer"
  filename            = "${path.module}/../lambdas/layers/pypdf-layer.zip"
  compatible_runtimes = ["python3.12"]
}