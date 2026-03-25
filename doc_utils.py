# ─────────────────────────────────────────────────────────────────────────────
#  doc_utils.py
#
#  Utility module for all python-docx operations:
#    • Loading .docx files from Streamlit UploadedFile objects
#    • Extracting plain text from a resume document
#    • Replacing {{PLACEHOLDER}} tokens inside templates while preserving
#      the original paragraph / run formatting as much as possible
#    • Serialising a modified Document back to raw bytes for download
#
#  Design notes
#  ────────────
#  Word stores paragraph text across multiple "runs", each with its own
#  character formatting (bold, italic, font size, colour, etc.).  A single
#  visible placeholder like "{{TAILORED_EXPERIENCE}}" can therefore be
#  fragmented across several runs, making naive string replacement fail.
#
#  The strategy used here:
#    1. Reconstruct the full paragraph text by joining all run texts.
#    2. Check whether the placeholder appears in that joined string.
#    3. If it does, rebuild the paragraph:
#       a. Keep the *first* run (inheriting its character style / font) and
#          put the replacement text there.
#       b. Zero-out every subsequent run so the paragraph contains no
#          stray text.
#    4. For multi-line replacement text (e.g. a 3-paragraph cover letter),
#       insert additional XML paragraph nodes *after* the placeholder
#       paragraph, each cloned from the placeholder paragraph so they share
#       the same paragraph-level style (indent, spacing, etc.).
#
#  Scope: body paragraphs, table cells, and headers/footers are all scanned.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import copy
import io
from typing import Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


# ─────────────────────────────────────────────────────────────────────────────
#  Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_docx(file_like) -> Document:
    """
    Load a python-docx ``Document`` from either:
      • An ``io.BytesIO`` object (preferred – always seekable), or
      • A Streamlit ``UploadedFile`` (legacy path – less reliable on cloud).

    The caller should always prefer passing ``io.BytesIO(cached_bytes)`` to
    avoid Streamlit's UploadedFile buffer exhaustion on cloud deployments.

    Parameters
    ----------
    file_like : io.BytesIO | streamlit.runtime.uploaded_file_manager.UploadedFile

    Returns
    -------
    docx.Document
    """
    if isinstance(file_like, io.BytesIO):
        # Already a proper in-memory buffer — just rewind and open.
        file_like.seek(0)
        return Document(file_like)

    # UploadedFile path (fallback) — seek before reading to guard against
    # partially-consumed buffers, then wrap in a fresh BytesIO so python-docx
    # gets a guaranteed-seekable stream.
    try:
        file_like.seek(0)
    except Exception:
        pass  # Some UploadedFile implementations raise on seek — ignore safely
    raw = file_like.read()
    return Document(io.BytesIO(raw))


def extract_resume_text(doc: Document) -> str:
    """
    Extract all human-readable text from a ``.docx`` resume, including text
    inside tables (common for two-column resume layouts).

    Paragraphs and table cells are separated by newlines so the AI model
    receives a coherent block of text.

    Parameters
    ----------
    doc : docx.Document

    Returns
    -------
    str
        Full plain-text content of the document.
    """
    lines: list[str] = []

    # ── Body paragraphs ───────────────────────────────────────────────────────
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            lines.append(text)

    # ── Table cells ──────────────────────────────────────────────────────────
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = para.text.strip()
                    if text:
                        lines.append(text)

    return "\n".join(lines)


def replace_placeholder(
    doc: Document,
    placeholder: str,
    replacement_text: str,
) -> int:
    """
    Find every occurrence of ``placeholder`` (e.g. ``{{COVER_LETTER_BODY}}``)
    throughout the document and replace it with ``replacement_text``.

    Multi-line replacement text is handled by cloning the placeholder
    paragraph and inserting one new paragraph per line directly after the
    original, then deleting the original placeholder paragraph.

    Parameters
    ----------
    doc : docx.Document
        The template document (mutated in place).
    placeholder : str
        The exact placeholder string to search for, e.g. ``"{{TAILORED_EXPERIENCE}}"``.
    replacement_text : str
        The AI-generated text to insert.  May contain ``\\n`` line breaks.

    Returns
    -------
    int
        The number of paragraphs in which the placeholder was found and replaced.
    """
    count = 0

    # ── Body paragraphs ───────────────────────────────────────────────────────
    # Iterate over a snapshot because we may insert paragraphs during iteration
    for para in list(doc.paragraphs):
        if _paragraph_contains(para, placeholder):
            _replace_multiline(para, placeholder, replacement_text)
            count += 1

    # ── Table cells ──────────────────────────────────────────────────────────
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in list(cell.paragraphs):
                    if _paragraph_contains(para, placeholder):
                        _replace_multiline(para, placeholder, replacement_text)
                        count += 1

    # ── Headers ──────────────────────────────────────────────────────────────
    for section in doc.sections:
        for para in list(section.header.paragraphs):
            if _paragraph_contains(para, placeholder):
                _replace_single_line(para, placeholder, replacement_text)
                count += 1

    # ── Footers ──────────────────────────────────────────────────────────────
        for para in list(section.footer.paragraphs):
            if _paragraph_contains(para, placeholder):
                _replace_single_line(para, placeholder, replacement_text)
                count += 1

    return count


def save_docx_to_bytes(doc: Document) -> bytes:
    """
    Serialise a ``Document`` into raw bytes suitable for ``st.download_button``.

    Parameters
    ----------
    doc : docx.Document

    Returns
    -------
    bytes
    """
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
#  Internal / private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_paragraph_text(para) -> str:
    """Return the full visible text of a paragraph by joining all run texts."""
    return "".join(run.text for run in para.runs)


def _paragraph_contains(para, placeholder: str) -> bool:
    """Return True if the reconstructed paragraph text contains the placeholder."""
    return placeholder in _get_paragraph_text(para)


def _replace_single_line(para, placeholder: str, replacement: str) -> None:
    """
    In-place single-line replacement: put the whole replacement into the first
    run and zero out every other run.

    This preserves the character formatting (font, size, bold, colour) of the
    first run that was part of the placeholder.
    """
    full_text = _get_paragraph_text(para)
    new_text = full_text.replace(placeholder, replacement)

    if not para.runs:
        # Edge case: no runs – add one with the new text
        para.add_run(new_text)
        return

    # Put all new text in the first run; silence every subsequent run
    para.runs[0].text = new_text
    for run in para.runs[1:]:
        run.text = ""


def _replace_multiline(para, placeholder: str, replacement_text: str) -> None:
    """
    Replace a placeholder with (potentially multi-line) text.

    Algorithm
    ─────────
    1.  Split ``replacement_text`` on newlines to get individual lines.
    2.  Filter out completely blank lines (collapse them into a single blank
        paragraph for readability).
    3.  The first non-empty line replaces the placeholder text inside the
        *existing* paragraph (preserving its paragraph-level style).
    4.  Each additional line is inserted as a *new* paragraph immediately
        after the previous one, cloned from the placeholder paragraph so it
        inherits indentation, spacing, and paragraph style.

    This approach keeps the template's formatting hierarchy intact.
    """
    lines = replacement_text.split("\n")

    # Remove leading/trailing empty lines but keep internal blank lines
    # so paragraph spacing in the output mirrors the AI's structure
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        # Nothing to insert – just clear the placeholder
        _replace_single_line(para, placeholder, "")
        return

    # ── Step 1: replace the placeholder paragraph with the first line ─────────
    _replace_single_line(para, placeholder, lines[0])

    # ── Step 2: insert remaining lines as sibling paragraphs ─────────────────
    # We keep track of the "anchor" paragraph so each new paragraph is inserted
    # *after* the previous one, maintaining correct document order.
    anchor = para
    for line in lines[1:]:
        new_para_element = _clone_paragraph_element(anchor, line)
        # Insert the new XML element directly after the anchor element
        anchor._element.addnext(new_para_element)
        # Advance the anchor to the newly inserted paragraph's wrapper
        # (We work through the raw XML element; python-docx re-wraps on access)
        anchor._element = new_para_element


def _clone_paragraph_element(source_para, text: str):
    """
    Deep-clone the XML element of ``source_para`` and set its text content to
    ``text``.  All paragraph-level properties (``<w:pPr>``: style, indentation,
    spacing) are preserved; run-level properties (``<w:rPr>``) are kept on the
    first run.

    Parameters
    ----------
    source_para : docx.text.paragraph.Paragraph
        The paragraph whose XML structure we clone.
    text : str
        The text to place into the cloned paragraph's first (and only) run.

    Returns
    -------
    lxml.etree._Element
        The new ``<w:p>`` XML element ready for insertion into the document body.
    """
    # Deep-copy preserves all child XML nodes (pPr, rPr, etc.)
    new_p = copy.deepcopy(source_para._element)

    # ── Remove all existing runs from the clone ───────────────────────────────
    for r in new_p.findall(qn("w:r")):
        new_p.remove(r)

    # ── Build a fresh <w:r> run with the target text ──────────────────────────
    new_r = OxmlElement("w:r")

    # Carry over run properties (<w:rPr>) from the first original run if present
    original_runs = source_para._element.findall(qn("w:r"))
    if original_runs:
        original_rpr = original_runs[0].find(qn("w:rPr"))
        if original_rpr is not None:
            new_r.append(copy.deepcopy(original_rpr))

    # Create the text node
    new_t = OxmlElement("w:t")
    new_t.text = text
    # Preserve leading/trailing spaces (Word strips them otherwise)
    if text != text.strip():
        new_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    new_r.append(new_t)
    new_p.append(new_r)

    return new_p