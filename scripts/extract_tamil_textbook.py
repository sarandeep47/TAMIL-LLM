"""
extract_tamil_textbook.py
-------------------------
Extracts text from a Tamil Nadu Class 1 Term I PDF textbook using PyMuPDF
(fitz).  Produces a UTF-8 text file with page markers, preserves Tamil Unicode
and paragraph breaks, and reports detailed extraction statistics.

Usage:
    python scripts/extract_tamil_textbook.py [--pdf PATH] [--out PATH]

Defaults:
    --pdf  data/raw/1st_Tamil_Term_I - www.tntextbooks.in.pdf
    --out  data/processed/tamil_textbook.txt
"""

import argparse
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency check with a helpful message
# ---------------------------------------------------------------------------
try:
    import fitz  # PyMuPDF
except ImportError:
    print(
        "[ERROR] PyMuPDF is not installed.\n"
        "Install it with:  pip install pymupdf\n"
        "Then re-run this script.",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PDF = (
    WORKSPACE_ROOT
    / "data"
    / "raw"
    / "1st_Tamil_Term_I - www.tntextbooks.in.pdf"
)
DEFAULT_OUT = WORKSPACE_ROOT / "data" / "processed" / "tamil_textbook.txt"

# A page is considered "suspiciously sparse" if it has fewer than this many
# non-whitespace characters (after extracting text).  Adjust as needed.
SPARSE_THRESHOLD = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_tamil_char(ch: str) -> bool:
    """Return True if the Unicode character belongs to the Tamil block."""
    try:
        name = unicodedata.name(ch, "")
        return name.startswith("TAMIL")
    except Exception:
        return False


def extract_page_text(page: "fitz.Page") -> str:
    """
    Extract text from a single page, preserving paragraph breaks.

    PyMuPDF's 'text' flag keeps the original layout with real newlines
    between blocks/paragraphs.  We use that directly so Tamil Unicode is
    never mangled.
    """
    # Using "text" (default) mode: plain text, line-break preserved
    raw = page.get_text("text")
    # Normalise Windows-style line endings, keep double newlines as paragraph breaks
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    return text


def build_page_marker(page_num: int) -> str:
    """Return a clearly visible page delimiter line."""
    return f"\n--- Page {page_num} ---\n"


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

def extract_textbook(pdf_path: Path, out_path: Path) -> None:
    # ---- guard: PDF must exist ----
    if not pdf_path.exists():
        print(
            f"[ERROR] PDF not found: {pdf_path}\n"
            f"Make sure the file exists at that path and try again.\n"
            f"Expected location: {pdf_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ---- ensure output directory exists ----
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Opening PDF : {pdf_path}")
    print(f"Output file : {out_path}")
    print()

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    pages_with_text: list[int] = []
    empty_pages: list[int] = []
    sparse_pages: list[int] = []
    total_chars = 0

    output_parts: list[str] = []

    # ---- header comment in the output file ----
    output_parts.append(
        f"# Extracted from: {pdf_path.name}\n"
        f"# Total pages   : {total_pages}\n"
        f"# Encoding      : UTF-8\n"
        f"# Tool          : PyMuPDF (fitz) v{fitz.version[0]}\n\n"
    )

    for page_index in range(total_pages):
        page_num = page_index + 1  # 1-based for human-readable markers
        page = doc.load_page(page_index)

        text = extract_page_text(page)
        stripped = text.strip()
        non_ws_chars = sum(1 for ch in text if not ch.isspace())

        # ---- categorise the page ----
        if not stripped:
            empty_pages.append(page_num)
        else:
            pages_with_text.append(page_num)
            total_chars += len(text)

            if non_ws_chars < SPARSE_THRESHOLD:
                sparse_pages.append(page_num)

        # ---- write page marker always (even for empty pages) ----
        output_parts.append(build_page_marker(page_num))

        if stripped:
            output_parts.append(text)
        else:
            # Explicitly note an empty page so nothing is silently discarded
            output_parts.append("[[ EMPTY PAGE — no text layer found ]]\n")

    doc.close()

    # ---- write UTF-8 output ----
    full_output = "".join(output_parts)
    out_path.write_text(full_output, encoding="utf-8")

    # ---- report ----
    print("=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"  Total pages      : {total_pages}")
    print(f"  Pages with text  : {len(pages_with_text)}")
    print(f"  Empty pages      : {len(empty_pages)}")
    print(f"  Total characters : {total_chars:,}")
    print(f"  Output size      : {out_path.stat().st_size:,} bytes")

    if empty_pages:
        print(f"\n  Empty page numbers  : {empty_pages}")

    if sparse_pages:
        print(
            f"\n  ⚠  SPARSE PAGES (< {SPARSE_THRESHOLD} non-whitespace chars) — "
            f"check manually:\n"
            f"     {sparse_pages}"
        )
    else:
        print("\n  ✓  No suspiciously sparse pages detected.")

    # Quick Tamil Unicode check
    tamil_char_count = sum(1 for ch in full_output if is_tamil_char(ch))
    print(f"\n  Tamil Unicode chars: {tamil_char_count:,}")
    if tamil_char_count == 0:
        print(
            "  ⚠  WARNING: Zero Tamil characters found.\n"
            "     The PDF may use embedded images for text instead of a\n"
            "     Unicode text layer.  Consider OCR (e.g. Tesseract + Tamil\n"
            "     language data) as an alternative extraction method."
        )
    else:
        print("  ✓  Tamil Unicode text confirmed in output.")

    print()
    print(f"Output written to: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Tamil textbook PDF to UTF-8 text."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help=f"Path to the source PDF (default: {DEFAULT_PDF})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Path for the output text file (default: {DEFAULT_OUT})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    extract_textbook(args.pdf, args.out)
