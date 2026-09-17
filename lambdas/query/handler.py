import os
import json
import pickle
import tempfile
import urllib.request
import urllib.error

import boto3
import faiss
import numpy as np

s3 = boto3.client("s3")

BUCKET = os.environ["DOCS_BUCKET"]
EMBEDDING_URL = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"


def get_embedding(text):
    api_key = os.environ["HUGGINGFACE_API_KEY"]
    payload = json.dumps({"inputs": text}).encode("utf-8")

    req = urllib.request.Request(
        EMBEDDING_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "rag-knowledge-assistant/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise ValueError(f"Error de la API de embeddings ({e.code}): {error_body}")


def load_index(tenant_id):
    tmp_index = tempfile.NamedTemporaryFile(suffix=".index", delete=False)
    tmp_index.close()

    s3.download_file(BUCKET, f"indexes/{tenant_id}/index.faiss", tmp_index.name)
    index = faiss.read_index(tmp_index.name)

    os.remove(tmp_index.name)

    metadata_obj = s3.get_object(Bucket=BUCKET, Key=f"indexes/{tenant_id}/metadata.pkl")
    metadata = pickle.loads(metadata_obj["Body"].read())

    return index, metadata


def search(tenant_id, query_text, top_n=3):
    index, metadata = load_index(tenant_id)

    query_vector = get_embedding(query_text)
    query_array = np.array([query_vector], dtype="float32")

    distances, positions = index.search(query_array, top_n)

    results = []
    for dist, pos in zip(distances[0], positions[0]):
        if pos == -1:
            continue
        chunk_meta = metadata[pos]
        results.append({
            "score": float(dist),
            "texto": chunk_meta["texto"],
            "doc_id": chunk_meta["doc_id"],
            "s3_path": chunk_meta["s3_path"],
        })
    return results


def build_prompt(query_text, chunks):
    contexto = "\n\n".join(
        f"[Documento: {c['doc_id']}]\n{c['texto']}"
        for c in chunks
    )

    return f"""Responde la pregunta del usuario basándote ÚNICAMENTE en el contexto proporcionado.
Si el contexto no tiene información suficiente para responder, dilo claramente, no inventes.
Al final de tu respuesta, indica de qué documento(s) sacaste la información, así: (Fuente: nombre-doc)

Contexto:
{contexto}

Pregunta: {query_text}

Respuesta:"""


def ask_groq(prompt):
    api_key = os.environ["GROQ_API_KEY"]
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "rag-knowledge-assistant/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise ValueError(f"Error de la API de Groq ({e.code}): {error_body}")


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        tenant_id = body.get("tenant_id")
        query_text = body.get("query")

        if not tenant_id or not query_text:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Faltan 'tenant_id' o 'query' en el body"}),
            }

        chunks = search(tenant_id, query_text, top_n=3)
        if not chunks:
            respuesta = "No encontré documentos relevantes para responder esa pregunta."
        else:
            prompt = build_prompt(query_text, chunks)
            respuesta = ask_groq(prompt)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"respuesta": respuesta}, ensure_ascii=False),
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }