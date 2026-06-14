from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf


OCR_MODES = ("fast", "default", "quality")


def create_ocr_engine(mode: str):
    start = time.perf_counter()
    from paddleocr import PaddleOCR

    if mode == "fast":
        engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    elif mode == "default":
        engine = PaddleOCR(lang="ch")
    elif mode == "quality":
        engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True,
        )
    else:
        raise ValueError(f"Unsupported OCR mode: {mode}")

    return engine, time.perf_counter() - start


def render_pdf_page(path: Path, page_number: int, output_path: Path, zoom: float) -> Path:
    with pymupdf.open(str(path)) as document:
        page = document.load_page(page_number - 1)
        matrix = pymupdf.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(str(output_path))
    return output_path


def ocr_image(path: Path, ocr) -> tuple[list[str], str]:
    try:
        result = ocr.predict(str(path))
        api = "predict"
    except Exception:
        result = ocr.ocr(str(path))
        api = "ocr"
    return extract_text_lines(result), api


def extract_text_lines(value: Any) -> list[str]:
    lines: list[str] = []
    collect_text(value, lines)
    deduped: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and (not deduped or deduped[-1] != stripped):
            deduped.append(stripped)
    return deduped


def collect_text(value: Any, lines: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        if value.strip():
            lines.append(value)
        return
    if isinstance(value, dict):
        for key in ("rec_texts", "texts", "text", "label", "transcription"):
            if key in value:
                collect_text(value[key], lines)
        for item in value.values():
            collect_text(item, lines)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            collect_text(item, lines)
        return
    for attr in ("json", "to_dict", "dict"):
        maybe = getattr(value, attr, None)
        if callable(maybe):
            try:
                collect_text(maybe(), lines)
                return
            except Exception:
                pass


def paddle_info() -> dict[str, Any]:
    try:
        import paddle

        info: dict[str, Any] = {
            "version": getattr(paddle, "__version__", "unknown"),
            "compiled_with_cuda": bool(paddle.device.is_compiled_with_cuda()),
        }
        try:
            info["device"] = paddle.device.get_device()
        except Exception as exc:
            info["device_error"] = repr(exc)
        return info
    except Exception as exc:
        return {"error": repr(exc)}


def benchmark_pdf(input_pdf: Path, *, mode: str, max_pages: int, zoom: float) -> dict[str, Any]:
    if not input_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"Input file is not a PDF: {input_pdf}")
    if max_pages <= 0:
        raise ValueError("--max-pages must be greater than 0")

    with pymupdf.open(str(input_pdf)) as document:
        page_count = len(document)
    pages_to_run = min(max_pages, page_count)
    if pages_to_run == 0:
        raise RuntimeError("Input PDF has no pages.")

    total_start = time.perf_counter()
    engine, engine_seconds = create_ocr_engine(mode)
    page_results: list[dict[str, Any]] = []

    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for page_number in range(1, pages_to_run + 1):
            image_path = tmp_dir / f"page_{page_number}.png"

            render_start = time.perf_counter()
            render_pdf_page(input_pdf, page_number, image_path, zoom)
            render_seconds = time.perf_counter() - render_start

            ocr_start = time.perf_counter()
            lines, api = ocr_image(image_path, engine)
            ocr_seconds = time.perf_counter() - ocr_start

            text = "\n".join(lines)
            page_results.append(
                {
                    "page": page_number,
                    "api": api,
                    "render_seconds": round(render_seconds, 3),
                    "ocr_seconds": round(ocr_seconds, 3),
                    "line_count": len(lines),
                    "char_count": len(text),
                    "text_preview": text[:160],
                }
            )
            print(
                f"page={page_number} render={render_seconds:.2f}s "
                f"ocr={ocr_seconds:.2f}s lines={len(lines)} chars={len(text)}",
                flush=True,
            )

    total_seconds = time.perf_counter() - total_start
    ocr_seconds_total = sum(page["ocr_seconds"] for page in page_results)
    render_seconds_total = sum(page["render_seconds"] for page in page_results)

    return {
        "input_pdf": str(input_pdf),
        "mode": mode,
        "zoom": zoom,
        "pdf_page_count": page_count,
        "benchmarked_pages": pages_to_run,
        "paddle": paddle_info(),
        "engine_load_seconds": round(engine_seconds, 3),
        "render_seconds_total": round(render_seconds_total, 3),
        "ocr_seconds_total": round(ocr_seconds_total, 3),
        "total_seconds": round(total_seconds, 3),
        "seconds_per_page": round(total_seconds / pages_to_run, 3),
        "pages": page_results,
    }


def default_output_path(input_pdf: Path, mode: str) -> Path:
    return input_pdf.with_name(f"{input_pdf.stem}_ocr_benchmark_{mode}.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark PaddleOCR on the first N pages of a PDF.")
    parser.add_argument("input_pdf", type=Path, help="PDF file to benchmark.")
    parser.add_argument("--mode", choices=OCR_MODES, default="default", help="OCR mode to benchmark.")
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum pages to benchmark.")
    parser.add_argument("--zoom", type=float, default=2.0, help="PDF render zoom before OCR.")
    parser.add_argument("--output", type=Path, default=None, help="JSON report path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_pdf = args.input_pdf.resolve()
    output = args.output.resolve() if args.output else default_output_path(input_pdf, args.mode)

    report = benchmark_pdf(
        input_pdf,
        mode=args.mode,
        max_pages=args.max_pages,
        zoom=args.zoom,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"Report: {output}")
    print(f"Total seconds: {report['total_seconds']}")
    print(f"Seconds per page: {report['seconds_per_page']}")


if __name__ == "__main__":
    main()
