from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import re
import time


ROOT = Path("library/03_business")

BOOKS = [
    {
        "slug": "lean_startup",
        "category": "startup",
        "title_cn": "精益创业",
        "title_en": "The Lean Startup",
        "author": "Eric Ries",
        "role": "创业验证、MVP、快速迭代",
        "official_urls": [
            "https://theleanstartup.com/",
        ],
        "notes": "适合作为 MetaOS 商机验证、MVP 设计、快速实验方法论的基础材料。",
    },
    {
        "slug": "zero_to_one",
        "category": "startup",
        "title_cn": "从0到1",
        "title_en": "Zero to One",
        "author": "Peter Thiel, Blake Masters",
        "role": "垄断、创新、反共识创业",
        "official_urls": [
            "https://www.penguinrandomhouse.com/books/234730/zero-to-one-by-peter-thiel-with-blake-masters/",
            "https://www.penguin.co.in/book/zero-to-one/",
        ],
        "notes": "适合作为 MetaOS 分析反共识机会、垂直垄断、创业方向选择的基础材料。",
    },
    {
        "slug": "innovators_dilemma",
        "category": "strategy",
        "title_cn": "创新者的窘境",
        "title_en": "The Innovator's Dilemma",
        "author": "Clayton M. Christensen",
        "role": "颠覆式创新、 incumbents 失效机制",
        "official_urls": [
            "https://www.hbs.edu/faculty/Pages/item.aspx?num=46",
        ],
        "notes": "适合作为 MetaOS 研究技术替代、产业颠覆、AI 创业机会窗口的基础材料。",
    },
    {
        "slug": "crossing_the_chasm",
        "category": "startup",
        "title_cn": "跨越鸿沟",
        "title_en": "Crossing the Chasm",
        "author": "Geoffrey A. Moore",
        "role": "技术产品从早期采用者进入主流市场",
        "official_urls": [
            "https://www.harpercollins.com/products/crossing-the-chasm-3rd-edition-geoffrey-a-moore",
        ],
        "notes": "适合作为 MetaOS 分析早期用户、滩头市场、B2B 产品进入策略的基础材料。",
    },
    {
        "slug": "business_model_generation",
        "category": "business_model",
        "title_cn": "商业模式新生代",
        "title_en": "Business Model Generation",
        "author": "Alexander Osterwalder, Yves Pigneur",
        "role": "商业模式画布、价值主张、收入结构",
        "official_urls": [
            "https://www.wiley.com/en-ie/Business%2BModel%2BGeneration%3A%2BA%2BHandbook%2Bfor%2BVisionaries%2C%2BGame%2BChangers%2C%2Band%2BChallengers-p-9780470876411",
            "https://www.strategyzer.com/library/business-model-generation-book-summary",
        ],
        "notes": "适合作为 MetaOS 商业模式分析 Skill 的基础框架。",
    },
    {
        "slug": "positioning",
        "category": "strategy",
        "title_cn": "定位",
        "title_en": "Positioning: The Battle for Your Mind",
        "author": "Al Ries, Jack Trout",
        "role": "品牌定位、心智占位、差异化表达",
        "official_urls": [
            "https://www.alries.com/positioning",
            "https://books.google.com/books?id=_BHj1OYgF7wC&printsec=frontcover",
        ],
        "notes": "适合作为 MetaOS 产品定位、目标用户表达、市场心智分析的基础材料。",
    },
    {
        "slug": "good_strategy_bad_strategy",
        "category": "strategy",
        "title_cn": "好战略，坏战略",
        "title_en": "Good Strategy Bad Strategy",
        "author": "Richard Rumelt",
        "role": "战略诊断、关键挑战、连贯行动",
        "official_urls": [
            "https://www.penguinrandomhouse.com/books/208668/good-strategy-bad-strategy-by-richard-rumelt/",
        ],
        "notes": "适合作为 MetaOS 明鉴台输出战略建议、识别伪战略的基础材料。",
    },
    {
        "slug": "competitive_strategy",
        "category": "strategy",
        "title_cn": "竞争战略",
        "title_en": "Competitive Strategy",
        "author": "Michael E. Porter",
        "role": "五力模型、竞争定位、通用战略",
        "official_urls": [
            "https://www.simonandschuster.com/books/Competitive-Strategy/Michael-E-Porter/9780684841489",
        ],
        "notes": "适合作为 MetaOS 竞品分析、行业结构分析、商机评分的基础材料。",
    },
    {
        "slug": "blue_ocean_strategy",
        "category": "strategy",
        "title_cn": "蓝海战略",
        "title_en": "Blue Ocean Strategy",
        "author": "W. Chan Kim, Renée Mauborgne",
        "role": "创造新市场、价值创新、避开红海竞争",
        "official_urls": [
            "https://www.blueoceanstrategy.com/",
            "https://hbsp.harvard.edu/product/13892-HBK-ENG",
        ],
        "notes": "适合作为 MetaOS 机会发现、差异化战略、商机推荐榜单的基础材料。",
    },
    {
        "slug": "hacking_growth",
        "category": "growth",
        "title_cn": "增长黑客",
        "title_en": "Hacking Growth",
        "author": "Sean Ellis, Morgan Brown",
        "role": "增长实验、用户获取、留存、转化",
        "official_urls": [
            "https://www.penguinrandomhouse.com/books/545936/hacking-growth-by-sean-ellis-founder-of-growthhackerscom-and-morgan-brown/",
            "https://www.seanellis.me/books",
        ],
        "notes": "适合作为 MetaOS 增长策略、产品实验、获客路径分析的基础材料。",
    },
]


def safe_filename(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9_\\-]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def write_markdown_card(book: dict) -> Path:
    category_dir = ROOT / book["category"]
    category_dir.mkdir(parents=True, exist_ok=True)

    md_path = category_dir / f"{safe_filename(book['slug'])}.md"

    links = "\n".join(f"- {url}" for url in book["official_urls"])

    content = f"""# {book["title_cn"]}

## 基本信息

- 中文名：{book["title_cn"]}
- 英文名：{book["title_en"]}
- 作者：{book["author"]}
- 所属目录：`03_business/{book["category"]}`
- 在 MetaOS 中的作用：{book["role"]}

## 合法来源链接

{links}

## 入库说明

这是一张 MetaOS 种子知识库资料卡。

这些链接主要指向出版社、作者官网、官方方法论网站、Google Books 或合法摘要页面。  
如需全文入库，请使用你已经合法购买、授权或拥有使用权的电子书/文档。

## MetaOS 使用场景

{book["notes"]}

## 建议提取的问题

- 这本书解决什么核心问题？
- 它提供了哪些分析框架？
- 它适合支撑 MetaOS 的哪个 Agent 或 Skill？
- 它与其他商业/战略书籍的冲突点是什么？
- 它能否转化为商机分析师的评分维度？

"""
    md_path.write_text(content, encoding="utf-8")
    return md_path


def download_html_snapshot(book: dict) -> list[Path]:
    category_dir = ROOT / book["category"] / "_html_snapshots" / book["slug"]
    category_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []

    for idx, url in enumerate(book["official_urls"], start=1):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 MetaOSKnowledgeBot/0.1"
                },
            )
            with urlopen(req, timeout=20) as resp:
                html = resp.read()

            out_path = category_dir / f"source_{idx}.html"
            out_path.write_bytes(html)
            saved_files.append(out_path)

            print(f"[HTML] saved: {out_path}")

            time.sleep(1)

        except (HTTPError, URLError, TimeoutError) as e:
            print(f"[WARN] download failed: {url}")
            print(f"       reason: {e}")

    return saved_files


def main(download_html: bool = False):
    ROOT.mkdir(parents=True, exist_ok=True)

    print("Creating MetaOS business source cards...")
    print(f"Target root: {ROOT.resolve()}")

    for book in BOOKS:
        md_path = write_markdown_card(book)
        print(f"[MD] saved: {md_path}")

        if download_html:
            download_html_snapshot(book)

    print("\nDone.")
    print("说明：脚本只保存合法来源链接和官方页面快照，不下载盗版全文。")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed MetaOS business knowledge base with legal source cards."
    )
    parser.add_argument(
        "--download-html",
        action="store_true",
        help="Also download HTML snapshots of official/source pages.",
    )

    args = parser.parse_args()
    main(download_html=args.download_html)