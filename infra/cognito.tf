resource "aws_cognito_user_pool" "users" {
  name = "rag-users"

  schema {
    name                = "tenant_id"
    attribute_data_type = "String"
    mutable             = true
    required            = false

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "rag-api-client"
  user_pool_id = aws_cognito_user_pool.users.id

  explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
}

output "user_pool_id" {
  value = aws_cognito_user_pool.users.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.client.id
}