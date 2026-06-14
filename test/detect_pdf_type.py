from pathlib import Path
import argparse
import fitz  # PyMuPDF


def count_text_chars(text: str) -> int:
    """
    统计有效文字数量。
    去掉空白字符后计数。
    """
    if not text:
        return 0
    return len("".join(text.split()))


def bbox_area(bbox) -> float:
    """
    计算矩形面积。
    bbox = (x0, y0, x1, y1)
    """
    x0, y0, x1, y1 = bbox
    return max(0, x1 - x0) * max(0, y1 - y0)


def analyze_page(page, min_text_chars: int = 80, image_area_threshold: float = 0.60):
    """
    分析单页 PDF 类型。
    """
    page_width = page.rect.width
    page_height = page.rect.height
    page_area = page_width * page_height

    text = page.get_text("text") or ""
    text_chars = count_text_chars(text)

    page_dict = page.get_text("dict")
    image_area_total = 0.0

    for block in page_dict.get("blocks", []):
        # PyMuPDF 中 block type:
        # 0 = text
        # 1 = image
        if block.get("type") == 1:
            image_area_total += bbox_area(block.get("bbox", (0, 0, 0, 0)))

    image_area_ratio = image_area_total / page_area if page_area else 0

    if text_chars >= min_text_chars and image_area_ratio < image_area_threshold:
        page_type = "text"

    elif text_chars < min_text_chars and image_area_ratio >= image_area_threshold:
        page_type = "scanned"

    elif text_chars >= min_text_chars and image_area_ratio >= image_area_threshold:
        page_type = "mixed"

    else:
        page_type = "empty_or_unknown"

    return {
        "page_type": page_type,
        "text_chars": text_chars,
        "image_area_ratio": round(image_area_ratio, 3),
    }


def classify_pdf(pdf_path: Path):
    doc = fitz.open(pdf_path)

    results = []
    for i, page in enumerate(doc, start=1):
        info = analyze_page(page)
        info["page"] = i
        results.append(info)

    total = len(results)
    scanned_count = sum(1 for r in results if r["page_type"] == "scanned")
    text_count = sum(1 for r in results if r["page_type"] == "text")
    mixed_count = sum(1 for r in results if r["page_type"] == "mixed")
    unknown_count = sum(1 for r in results if r["page_type"] == "empty_or_unknown")

    scanned_ratio = scanned_count / total if total else 0
    text_ratio = text_count / total if total else 0
    mixed_ratio = mixed_count / total if total else 0

    if scanned_ratio >= 0.8:
        pdf_type = "scanned_pdf"
    elif text_ratio >= 0.8 and mixed_count == 0:
        pdf_type = "text_pdf"
    else:
        pdf_type = "mixed_pdf"

    return {
        "pdf_path": str(pdf_path),
        "pdf_type": pdf_type,
        "total_pages": total,
        "text_pages": text_count,
        "scanned_pages": scanned_count,
        "mixed_pages": mixed_count,
        "unknown_pages": unknown_count,
        "pages": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="PDF 文件路径")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    result = classify_pdf(pdf_path)

    print("=" * 60)
    print(f"PDF: {result['pdf_path']}")
    print(f"类型: {result['pdf_type']}")
    print(f"总页数: {result['total_pages']}")
    print(f"文本页: {result['text_pages']}")
    print(f"扫描页: {result['scanned_pages']}")
    print(f"混合页: {result['mixed_pages']}")
    print(f"未知页: {result['unknown_pages']}")
    print("=" * 60)

    for page in result["pages"]:
        print(
            f"Page {page['page']:>4} | "
            f"{page['page_type']:<16} | "
            f"text_chars={page['text_chars']:<5} | "
            f"image_ratio={page['image_area_ratio']}"
        )


if __name__ == "__main__":
    main()