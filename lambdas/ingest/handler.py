import boto3
import os
import re
import json
import urllib.request
import urllib.error
from decimal import Decimal
from pypdf import PdfReader
from io import BytesIO
import faiss
import numpy as np
import pickle
import tempfile


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def get_table():
    return dynamodb.Table(os.environ["DYNAMODB_TABLE"])

CHUNK_SIZE = 500       # palabras aproximadas por chunk
CHUNK_OVERLAP = 50     # palabras de solapamiento entre chunks


def extract_tenant_and_doc_id(s3_key):
    # convención: {tenant_id}/{doc_id}.pdf
    parts = s3_key.split("/")
    if len(parts) < 2:
        raise ValueError(f"Ruta S3 inesperada, falta tenant_id: {s3_key}")
    tenant_id = parts[0]
    doc_id = parts[-1].rsplit(".", 1)[0]
    return tenant_id, doc_id


def extract_text_from_pdf(pdf_bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    if len(reader.pages) == 0:
        raise ValueError("PDF sin páginas legibles")
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""
    if not full_text.strip():
        raise ValueError("No se pudo extraer texto (¿PDF escaneado sin OCR?)")
    return full_text

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


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = re.split(r"\s+", text.strip())
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start = end - overlap
    return chunks


def save_chunks(tenant_id, doc_id, chunks, s3_path):
    table = get_table()
    with table.batch_writer() as batch:
        for i, chunk_val in enumerate(chunks):
            embedding = get_embedding(chunk_val)
            embedding_decimal = [Decimal(str(v)) for v in embedding]

            batch.put_item(Item={
                "tenant_id": tenant_id,
                "chunk_pk": f"{doc_id}#{i:04d}",
                "doc_id": doc_id,
                "chunk_id": i,
                "texto": chunk_val,
                "s3_path": s3_path,
                "embedding": embedding_decimal,
            })
            
            
def get_all_tenant_chunks(tenant_id):
    table = get_table()
    response = table.query(
        KeyConditionExpression="tenant_id = :tid",
        ExpressionAttributeValues={":tid": tenant_id},
    )
    items = response["Items"]

    # DynamoDB pagina resultados grandes, hay que seguir pidiendo hasta agotarlos
    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression="tenant_id = :tid",
            ExpressionAttributeValues={":tid": tenant_id},
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response["Items"])

    return items

def build_and_upload_index(tenant_id, bucket):
    chunks = get_all_tenant_chunks(tenant_id)

    if not chunks:
        print(f"Sin chunks para tenant={tenant_id}, no se construye índice")
        return

    valid_chunks = [item for item in chunks if "embedding" in item]
    skipped = len(chunks) - len(valid_chunks)
    if skipped:
        print(f"Aviso: {skipped} chunks sin embedding, se omiten del índice")

    if not valid_chunks:
        print(f"Sin chunks con embedding para tenant={tenant_id}, no se construye índice")
        return

    vectors = np.array(
        [[float(v) for v in item["embedding"]] for item in valid_chunks],
        dtype="float32",
    )

    metadata = [
        {
            "chunk_pk": item["chunk_pk"],
            "doc_id": item["doc_id"],
            "texto": item["texto"],
            "s3_path": item["s3_path"],
        }
        for item in valid_chunks
    ]

    dimension = vectors.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(vectors)

    # FAISS solo sabe escribir a un archivo en disco, no directo a S3
    with tempfile.NamedTemporaryFile(suffix=".index") as tmp_index:
        faiss.write_index(index, tmp_index.name)
        tmp_index.seek(0)
        s3.upload_file(tmp_index.name, bucket, f"indexes/{tenant_id}/index.faiss")

    # la metadata la guardamos aparte, como pickle
    metadata_bytes = pickle.dumps(metadata)
    s3.put_object(
        Bucket=bucket,
        Key=f"indexes/{tenant_id}/metadata.pkl",
        Body=metadata_bytes,
    )

    print(f"Índice actualizado: {len(chunks)} chunks para tenant={tenant_id}")

def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        s3_path = f"s3://{bucket}/{key}"

        print(f"Procesando: {s3_path}")

        try:
            if not key.lower().endswith(".pdf"):
                raise ValueError(f"Tipo de archivo no soportado: {key}")

            tenant_id, doc_id = extract_tenant_and_doc_id(key)

            obj = s3.get_object(Bucket=bucket, Key=key)
            pdf_bytes = obj["Body"].read()

            text = extract_text_from_pdf(pdf_bytes)
            chunks = chunk_text(text)
            save_chunks(tenant_id, doc_id, chunks, s3_path)
            build_and_upload_index(tenant_id, bucket)

            print(f"OK: {len(chunks)} chunks guardados para doc_id={doc_id}, tenant={tenant_id}")

        except Exception as e:
            print(f"ERROR procesando {s3_path}: {str(e)}")
            raise