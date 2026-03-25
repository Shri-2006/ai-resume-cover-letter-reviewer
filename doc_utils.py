# ─────────────────────────────────────────────────────────────────────────────
#  doc_utils.py  –  No-placeholder template injection
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import copy, io
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def load_docx(file_like) -> Document:
    if isinstance(file_like, (io.BytesIO, io.RawIOBase, io.BufferedIOBase)):
        file_like.seek(0)
        return Document(file_like)
    try:
        file_like.seek(0)
    except Exception:
        pass
    return Document(io.BytesIO(file_like.read()))


def save_docx_to_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def extract_resume_text(doc: Document) -> str:
    """Plain-text dump of a resume .docx (body + tables)."""
    lines = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            lines.append(t)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    t = para.text.strip()
                    if t:
                        lines.append(t)
    return "\n".join(lines)


def get_template_context(doc: Document) -> str:
    """
    Return the template as a numbered paragraph list for the AI prompt.
    Example:  [0] Wolfie Seawolf
              [1] Town, State | email ...
              ...
    The AI uses these exact indices in its JSON response.
    """
    return "\n".join(f"[{i}] {p.text}" for i, p in enumerate(doc.paragraphs))


def apply_paragraph_replacements(doc: Document, replacements: dict) -> int:
    """
    Apply {paragraph_index: new_text} replacements to *doc* in place.
    Text may contain \\n to insert multiple lines at that position.
    Works in descending index order so insertions don't shift later indices.
    Returns the number of paragraphs touched.
    """
    paragraphs = doc.paragraphs
    applied = 0

    sorted_items = sorted(
        ((int(k), v) for k, v in replacements.items() if str(k).strip().lstrip("-").isdigit()),
        reverse=True,
    )

    for idx, new_text in sorted_items:
        if idx < 0 or idx >= len(paragraphs):
            continue

        para = paragraphs[idx]
        lines = new_text.split("\n")
        while lines and not lines[-1].strip():
            lines.pop()

        if not lines:
            _clear_para(para)
            applied += 1
            continue

        _set_para_text(para, lines[0])
        applied += 1

        anchor = para
        for extra in lines[1:]:
            new_elem = _clone_para(anchor, extra)
            anchor._element.addnext(new_elem)

    return applied


# ── internal helpers ──────────────────────────────────────────────────────────

def _clear_para(para):
    for r in para.runs:
        r.text = ""

def _set_para_text(para, text: str):
    if not para.runs:
        para.add_run(text)
        return
    para.runs[0].text = text
    for r in para.runs[1:]:
        r.text = ""

def _clone_para(src_para, text: str):
    new_p = copy.deepcopy(src_para._element)
    for r in new_p.findall(qn("w:r")):
        new_p.remove(r)
    new_r = OxmlElement("w:r")
    orig = src_para._element.findall(qn("w:r"))
    if orig:
        rpr = orig[0].find(qn("w:rPr"))
        if rpr is not None:
            new_r.append(copy.deepcopy(rpr))
    new_t = OxmlElement("w:t")
    new_t.text = text
    if text != text.strip():
        new_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    new_r.append(new_t)
    new_p.append(new_r)
    return new_p