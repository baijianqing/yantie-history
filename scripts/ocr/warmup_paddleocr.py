from paddleocr import PaddleOCR

print("开始初始化 PaddleOCR...")

ocr = PaddleOCR(
    lang="ch",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

print("PaddleOCR 初始化完成。")