import boto3
import os
import re
from pypdf import PdfReader
from io import BytesIO

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
            batch.put_item(Item={
                "tenant_id": tenant_id,
                "chunk_pk": f"{doc_id}#{i:04d}",
                "doc_id": doc_id,
                "chunk_id": i,
                "texto": chunk_val,
                "s3_path": s3_path,
            })


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

            print(f"OK: {len(chunks)} chunks guardados para doc_id={doc_id}, tenant={tenant_id}")

        except Exception as e:
            print(f"ERROR procesando {s3_path}: {str(e)}")
            raise