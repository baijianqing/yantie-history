from __future__ import annotations

from pathlib import Path
import sys

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf


def split_first_pages(input_pdf: Path, output_pdf: Path, page_count: int = 10) -> None:
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input file is not a PDF: {input_pdf}")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    result = pymupdf.open()
    try:
        with pymupdf.open(str(input_pdf)) as source:
            if len(source) == 0:
                raise RuntimeError("Input PDF has no pages.")

            end_page = min(page_count, len(source))
            result.insert_pdf(source, from_page=0, to_page=end_page - 1)
            result.save(str(output_pdf))
    finally:
        result.close()

    print(f"Created: {output_pdf}")
    print(f"Pages: {end_page}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python split_first_10_pages.py input.pdf [output.pdf]")

    input_pdf = Path(sys.argv[1]).resolve()
    output_pdf = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) >= 3
        else input_pdf.with_name(f"{input_pdf.stem}_first10.pdf")
    )

    split_first_pages(input_pdf, output_pdf, page_count=10)


if __name__ == "__main__":
    main()
