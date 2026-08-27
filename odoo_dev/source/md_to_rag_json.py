#!/usr/bin/env python3
"""
md_to_rag_json.py — Convert Markdown docs into RAG-ready JSON chunks.
Splits by ## / ### headings; each chunk carries metadata for Qdrant ingestion.
Usage: python md_to_rag_json.py input.md [output.json]
"""
import json, re, sys, os

def md_to_chunks(md_path):
    with open(md_path, encoding="utf-8") as f:
        text = f.read()

    doc_id = os.path.splitext(os.path.basename(md_path))[0]
    # Grab doc title (first # heading) if present
    m = re.search(r"^#\s+(.+)$", text, re.M)
    doc_title = m.group(1).strip() if m else doc_id

    # Split on ## or ### headings, keeping the heading with its body
    parts = re.split(r"^(#{2,3}\s+.+)$", text, flags=re.M)
    chunks, current_h2 = [], None
    idx = 0
    # parts: [preamble, heading, body, heading, body, ...]
    for i in range(1, len(parts), 2):
        heading_line = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        level = 2 if heading_line.startswith("## ") else 3
        title = re.sub(r"^#{2,3}\s+", "", heading_line)
        if level == 2:
            current_h2 = title
            section_path = title
        else:
            section_path = f"{current_h2} > {title}" if current_h2 else title
        content = f"{title}\n\n{body}" if body else title
        if len(body) < 20:   # skip near-empty structural headings
            continue
        idx += 1
        chunks.append({
            "id": f"{doc_id}_{idx:03d}",
            "doc_id": doc_id,
            "doc_title": doc_title,
            "section": section_path,
            "content": content,
            "char_count": len(content),
            "source_file": os.path.basename(md_path),
        })
    return chunks

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    md_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else md_path.rsplit(".", 1)[0] + ".json"
    chunks = md_to_chunks(md_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"document": os.path.basename(md_path),
                   "total_chunks": len(chunks),
                   "chunks": chunks}, f, ensure_ascii=False, indent=2)
    print(f"{out_path}: {len(chunks)} chunks")

if __name__ == "__main__":
    main()
