from handler import extract_text_from_pdf, chunk_text

with open("factura-prueba.pdf", "rb") as f:
    pdf_bytes = f.read()

text = extract_text_from_pdf(pdf_bytes)
print(f"Texto extraído: {len(text)} caracteres")

chunks = chunk_text(text)
print(f"Total de chunks: {len(chunks)}")
print("--- Primer chunk ---")
print(chunks[0])