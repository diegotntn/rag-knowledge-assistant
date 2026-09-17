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

BUCKET = "rag-assistant-docs-diego-tf"
EMBEDDING_URL = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/feature-extraction"


def get_embedding(text):
    api_key = os.environ["HUGGINGFACE_API_KEY"]
    payload = json.dumps({"inputs": text}).encode("utf-8")

    req = urllib.request.Request(
        EMBEDDING_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
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


if __name__ == "__main__":
    tenant_id = "tenant-demo"
    query = "¿Cómo se cambia la vigencia de un programa?"

    resultados = search(tenant_id, query, top_n=3)

    print(f"Pregunta: {query}\n")
    for i, r in enumerate(resultados, 1):
        print(f"--- Resultado {i} (score={r['score']:.4f}, doc={r['doc_id']}) ---")
        print(r["texto"][:200] + "...")
        print()