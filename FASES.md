# Plan de Proyecto: Asistente de Conocimiento con IA (RAG) en AWS

**Objetivo:** construir un pipeline de datos multi-tenant que permita subir documentos y hacer preguntas sobre ellos con un agente de IA, usando solo servicios con capa gratuita de AWS.

**Ritmo:** fines de semana. Estimado: 12-16 semanas (3-4 meses).

**Presupuesto:** $0 en AWS (con guardrails). Modelo LLM vía Groq (gratis) o crédito de bienvenida de un proveedor.

---

## Stack técnico final

| Componente | Servicio | Costo |
|---|---|---|
| Almacenamiento de documentos | S3 | Gratis (5GB) |
| Procesamiento (extracción, chunking) | Lambda | Gratis (1M invocaciones/mes) |
| Metadatos / registro de documentos | DynamoDB | Gratis (25GB) |
| Vector store | FAISS (dentro de Lambda o EC2 t2.micro) | Gratis |
| Modelo LLM (generación) | Groq API (Llama 3) | Gratis |
| Embeddings | Modelo open-source (sentence-transformers) corriendo en Lambda, o embeddings de Groq/HuggingFace | Gratis |
| Autenticación multi-tenant | Cognito | Gratis (50k usuarios activos) |
| API | API Gateway | Gratis (1M llamadas/mes, primeros 12 meses) |
| Orquestación | Step Functions | Gratis (4k transiciones/mes) |
| Infraestructura como código | Terraform | Gratis (open-source) |
| Frontend | React (artifact o Amplify Hosting free tier) | Gratis |

---

## Cronograma por fases

### Fase 0 — Preparación (Semana 1)
- Crear cuenta AWS
- Configurar AWS Budget de $1 USD con alerta por correo + acción automática de apagado
- Instalar AWS CLI y configurar credenciales (usuario IAM, NUNCA el root)
- Crear repositorio en GitHub: `rag-knowledge-assistant`
- Instalar Terraform localmente

**Entregable:** cuenta lista, budget activo, repo inicial con README.

### Fase 1 — Fundamentos AWS (Semanas 2-3)
- Crear un bucket S3 manualmente, subir/bajar archivos
- Crear un rol IAM con permisos mínimos (principio de menor privilegio)
- Crear tu primera función Lambda: recibe un evento S3 (nuevo archivo) y solo hace `print` del nombre del archivo
- Migrar esa Lambda a Terraform (que el `terraform apply` la cree, no la consola)

**Entregable:** al subir un archivo a S3, se dispara una Lambda y lo ves en CloudWatch Logs. Todo deployado con Terraform.

### Fase 2 — Ingesta y procesamiento de documentos (Semanas 4-6)
- La Lambda del paso anterior ahora: descarga el PDF, extrae texto (librería `pypdf`), lo divide en chunks (~500 tokens con solapamiento)
- Guarda cada chunk en DynamoDB con: `tenant_id`, `doc_id`, `chunk_id`, `texto`, `s3_path`
- Maneja errores (PDF corrupto, archivo no soportado) con una cola DLQ (Dead Letter Queue) en SQS

**Entregable:** subes un PDF y en segundos tienes sus chunks en DynamoDB, con logs claros de éxito/error.

### Fase 3 — Embeddings y búsqueda semántica (Semanas 7-9)
- Añade generación de embeddings a la Lambda (usa `sentence-transformers` con un modelo pequeño tipo `all-MiniLM-L6-v2`, corre bien en Lambda con capa/layer)
- Guarda los embeddings en un índice FAISS (persistido en S3, se carga en memoria al invocar)
- Escribe una función de búsqueda: dado un texto de consulta, devuelve los N chunks más similares

**Entregable:** script/Lambda que recibe una pregunta y devuelve los fragmentos de texto más relevantes, con su score de similitud.

### Fase 4 — Motor RAG y agente (Semanas 10-11)
- Conecta la búsqueda semántica con Groq: los chunks recuperados + la pregunta van al LLM, que responde citando de qué documento salió cada dato
- (Opcional, si quieres sumar "agente") añade una segunda herramienta simple, ej: "resumir todo el documento X" o "listar documentos disponibles", y deja que el LLM decida cuál usar según la pregunta

**Entregable:** puedes hacer una pregunta en lenguaje natural y recibir una respuesta correcta con fuente citada.

### Fase 5 — API y multi-tenant (Semanas 12-13)
- Expón todo con API Gateway + Lambda (endpoints: `POST /documents`, `POST /query`)
- Añade Cognito: cada usuario pertenece a un `tenant_id`, y todos los queries/documentos se filtran por ese id
- Prueba con 2 "clientes" ficticios para confirmar que sus datos nunca se mezclan

**Entregable:** API funcional con autenticación, probada con Postman o curl, con aislamiento de datos verificado.

### Fase 6 — Costos, IaC y pulido (Semana 14)
- Todo el stack debe poder crearse con `terraform apply` y destruirse con `terraform destroy`
- Documenta en el README el costo estimado mensual para 1 vs 10 vs 100 tenants (aunque hoy sea $0, muestra que entiendes cómo escala el costo)
- Añade un diagrama de arquitectura (puedes pedírmelo cuando lleguemos aquí)

**Entregable:** repo reproducible por cualquier persona con `terraform apply`, documentación de costos.

### Fase 7 — Frontend y demo (Semanas 15-16)
- Interfaz simple: subir documento, hacer preguntas, ver respuestas con fuente
- Grabar un video corto (2-3 min) mostrando el flujo completo
- Escribir el README final: problema que resuelve, arquitectura, decisiones técnicas, cómo correrlo, costos, próximos pasos

**Entregable:** proyecto de portfolio completo, listo para poner en el CV y LinkedIn.

---

## Guardrails de presupuesto (hacer ANTES de tocar cualquier servicio)

1. AWS Budgets → crear presupuesto de $1 USD, alerta al 80% y 100%
2. (Opcional pero recomendado) Lambda que reciba la alerta de budget y detenga/borre recursos automáticamente
3. Regla personal: `terraform destroy` al terminar cada sesión de fin de semana. Nunca dejar nada corriendo entre semana.
4. Revisar el Cost Explorer cada domingo antes de cerrar la sesión (toma 2 minutos, evita sorpresas)

---

## Checklist para EMPEZAR ESTE FIN DE SEMANA (Fase 0 + inicio Fase 1)

- [ ] Crear cuenta AWS (tarjeta requerida, pero no se cobra nada si sigues los guardrails)
- [ ] Crear usuario IAM para ti mismo con permisos de administrador (dejar de usar el root inmediatamente)
- [ ] Configurar MFA en la cuenta root y en tu usuario IAM
- [ ] Crear el AWS Budget de $1 con alertas
- [ ] Instalar AWS CLI (`aws configure` con las credenciales del usuario IAM)
- [ ] Instalar Terraform
- [ ] Crear repo en GitHub con estructura inicial:
  ```
  rag-knowledge-assistant/
    infra/          # Terraform
    lambdas/        # código de las funciones
    docs/           # diagramas, decisiones técnicas
    README.md
  ```
- [ ] Crear un bucket S3 vía Terraform (tu primer `terraform apply`)
- [ ] Subir un PDF de prueba manualmente y confirmar que aparece en el bucket

Cuando termines este checklist, dime y seguimos con el código de la primera Lambda (Fase 1).