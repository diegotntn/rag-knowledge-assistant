variable "huggingface_api_key" {
  description = "API key de HuggingFace para generar embeddings"
  type        = string
  sensitive   = true
}

variable "groq_api_key" {
  description = "API key de Groq para el LLM"
  type        = string
  sensitive   = true
}