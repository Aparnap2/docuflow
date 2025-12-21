import os
import json
from typing import List, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import Table
import tempfile

app = FastAPI()
ENGINE_SECRET = os.getenv("ENGINE_SECRET", "")

def extract_sections(doc) -> List[Dict[str, Any]]:
    """Extract section hierarchy for smart citations"""
    sections = []
    current_hierarchy = []
    
    for item in doc.body:
        if hasattr(item, 'level') and hasattr(item, 'text'):
            level = item.level
            text = item.text
            
            # Maintain hierarchy based on heading levels
            if level <= len(current_hierarchy):
                current_hierarchy = current_hierarchy[:level-1]
            else:
                current_hierarchy.extend([""] * (level - len(current_hierarchy) - 1))
            
            if level <= len(current_hierarchy):
                current_hierarchy[level-1] = text
            else:
                current_hierarchy.append(text)
            
            sections.append({
                "level": level,
                "text": text,
                "hierarchy": current_hierarchy.copy(),
                "page": getattr(item, 'page', 1)
            })
    
    return sections

@app.post("/process")
async def process(req: Request):
    """
    Enhanced document processing with table extraction and section hierarchy.
    Per PRD v2.0: Parse PDF/DOCX → Markdown + Tables (HTML) + Section Hierarchy.
    """
    secret = req.headers.get("x-secret", "")
    if secret != ENGINE_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")

    filename = req.headers.get("x-filename", "document.pdf")
    content = await req.body()
    if not content:
        raise HTTPException(status_code=400, detail="empty body")

    suffix = ".pdf"
    low = filename.lower()
    if low.endswith(".docx"):
        suffix = ".docx"
    elif low.endswith(".md") or low.endswith(".markdown"):
        suffix = ".md"
    elif low.endswith(".html") or low.endswith(".htm"):
        suffix = ".html"

    # Handle markdown and HTML directly
    if suffix in [".md", ".html"]:
        return {
            "markdown": content.decode("utf-8", errors="ignore"),
            "tables_html": [],
            "sections": [],
            "page_count": 1
        }

    # Process PDF and DOCX with Docling
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as f:
        f.write(content)
        f.flush()
        
        converter = DocumentConverter()
        result = converter.convert(f.name)
        doc = result.document
        
        # Extract tables as HTML
        tables_html = []
        for table in doc.tables:
            tables_html.append(table.export_to_html())
        
        # Extract section hierarchy for citations
        sections = extract_sections(doc)
        
        # Get structured markdown
        markdown = doc.export_to_markdown()
        
        return {
            "markdown": markdown,
            "tables_html": tables_html,
            "sections": sections,
            "page_count": len(doc.pages)
        }

@app.get("/health")
def health():
    return {"status": "ok"}