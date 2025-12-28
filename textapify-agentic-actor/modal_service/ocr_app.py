import modal

app = modal.App("granite-docling-ocr")
image = modal.Image.debian_slim().pip_install("docling", "docling-core")

@app.function(
    image=image,
    gpu="T4",  # Cheap, fast GPU
    timeout=120,
    container_idle_timeout=300
)
@modal.web_endpoint(method="POST")
def process_pdf(data: dict):
    from docling.document_converter import DocumentConverter

    url = data.get("pdf_url")
    if not url:
        return {"error": "No URL provided"}, 400

    print(f"Processing: {url}")
    converter = DocumentConverter() # Loads standard models
    result = converter.convert(url)
    markdown = result.document.export_to_markdown()

    return {"markdown": markdown, "status": "success"}