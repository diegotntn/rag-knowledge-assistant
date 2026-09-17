# RAG Knowledge Assistant

Asistente que responde preguntas sobre documentos PDF usando búsqueda 
semántica + un modelo de lenguaje (RAG - Retrieval Augmented Generation). 
Corre completamente en AWS, con toda la infraestructura definida en Terraform.

## Cómo funciona

1. **Ingesta**: subes un PDF a S3 → se dispara una Lambda automáticamente, 
   que extrae el texto, lo corta en fragmentos (chunks), genera un embedding 
   por cada uno con HuggingFace, y guarda todo en DynamoDB.
2. **Indexado**: tras cada ingesta, se construye un índice FAISS con los 
   vectores del tenant y se guarda en S3.
3. **Consulta**: alguien hace una pregunta → una Lambda busca los chunks 
   más relevantes por significado, arma un prompt con ese contexto, y se 
   lo manda a Groq (LLM) para generar la respuesta, citando de qué 
   documento salió la información.
4. **Acceso**: protegido con Amazon Cognito. El usuario inicia sesión, 
   recibe un token (JWT), y de ese token sale su `tenant_id` — así cada 
   cliente solo ve sus propios documentos.

## Stack

- **AWS Lambda** — ingesta y consulta
- **Amazon S3** — almacenamiento de PDFs e índices FAISS
- **Amazon DynamoDB** — chunks de texto por tenant
- **Amazon SQS** — cola de errores (DLQ) para fallos de ingesta
- **Amazon API Gateway (HTTP API)** — expone la consulta como endpoint REST
- **Amazon Cognito** — autenticación y aislamiento multi-tenant
- **HuggingFace** — generación de embeddings (`sentence-transformers/all-MiniLM-L6-v2`)
- **Groq** — modelo de lenguaje (`openai/gpt-oss-20b`)
- **Terraform** — toda la infraestructura como código

## Estado del proyecto

| Fase | Qué hace | Estado |
|---|---|---|
| 0-1 — Fundamentos | Cuenta AWS, S3, IAM, primera Lambda | Listo |
| 2 — Ingesta | Extrae texto, chunks, DynamoDB, DLQ | Listo |
| 3 — Embeddings | Vectores por chunk, índice FAISS | Listo |
| 4 — Motor RAG | Búsqueda + Groq, cita la fuente | Listo |
| 5 — API y multi-tenant | API Gateway + Cognito (JWT) | Listo |
| 6 — Costos e IaC | Reproducibilidad y documentación de costos | En curso |
| 7 — Frontend y demo | Interfaz web, video, demo público | En curso |

## Configuración inicial de usuarios (Cognito)

Después de `terraform apply`, Cognito no trae usuarios por default — hay que 
crear al menos uno a mano para poder autenticarse contra la API.

1. Obtén los IDs necesarios:
```powershell
   terraform output user_pool_id
   terraform output user_pool_client_id
```

2. Crea el usuario, asignándole su `tenant_id`:
```powershell
   aws cognito-idp admin-create-user `
     --user-pool-id <user_pool_id> `
     --username <nombre-usuario> `
     --user-attributes Name=email,Value=<correo> Name=email_verified,Value=true Name="custom:tenant_id",Value=<tenant-id> `
     --temporary-password <TempPass123!>
```

3. Fija la contraseña permanente:
```powershell
   aws cognito-idp admin-set-user-password `
     --user-pool-id <user_pool_id> `
     --username <nombre-usuario> `
     --password <PasswordFinal123!> `
     --permanent
```

4. Obtén el token (`IdToken`) para llamar a la API:
```powershell
   aws cognito-idp initiate-auth `
     --client-id <user_pool_client_id> `
     --auth-flow USER_PASSWORD_AUTH `
     --auth-parameters USERNAME=<nombre-usuario>,PASSWORD=<PasswordFinal123!>
```

Nota: este paso es manual a propósito. Un flujo de registro de usuarios 
reales (self-service signup) queda fuera del alcance de este proyecto.

## Frontend

Hay una interfaz web simple en `frontend/index.html` — login contra Cognito 
y una pantalla para hacer preguntas sobre los documentos ya indexados.

Para correrla localmente:
```powershell
cd frontend
python -m http.server 5500
```
Abre `http://localhost:5500` en el navegador.

Nota: el `client_id`, la región de Cognito y la URL del API están 
hardcodeados al inicio del `<script>` del archivo — si vuelves a correr 
`terraform destroy` + `apply`, esos IDs cambian y hay que actualizarlos ahí.

## Reproducibilidad

Todo el stack se puede recrear desde cero:
```powershell
cd infra
terraform destroy
terraform apply
```
Después del apply, hay que repetir el paso de crear el usuario de Cognito 
(arriba) y volver a subir al menos un PDF a S3 para regenerar el índice.

## Pendiente

- Documentar costos estimados (Fase 6)
- Demo público con upload temporal de documentos, protegido con rate 
  limiting y borrado automático (Fase 7)
- Video demo
