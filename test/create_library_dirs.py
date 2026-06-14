from pathlib import Path

# MetaOS 知识库目录结构
DIRS = [
    "library/00_metaos/decisions",
    "library/00_metaos/failures",
    "library/00_metaos/roadmap",
    "library/00_metaos/self_evolution",

    "library/01_ai_stack/chroma",
    "library/01_ai_stack/onnxruntime",
    "library/01_ai_stack/langgraph",
    "library/01_ai_stack/mcp",
    "library/01_ai_stack/agents",

    "library/02_ai_market/ai_index",
    "library/02_ai_market/cbinsights",
    "library/02_ai_market/state_of_ai",
    "library/02_ai_market/policy",

    "library/03_business/startup",
    "library/03_business/strategy",
    "library/03_business/business_model",
    "library/03_business/growth",

    "library/04_product_user/product_management",
    "library/04_product_user/user_research",
    "library/04_product_user/jobs_to_be_done",

    "library/05_decision_strategy/chinese_classics",
    "library/05_decision_strategy/western_strategy",
    "library/05_decision_strategy/cognitive_bias",

    "library/06_mingjiantai/guiguzi",
    "library/06_mingjiantai/confucius",
    "library/06_mingjiantai/laozi",
    "library/06_mingjiantai/munger",
    "library/06_mingjiantai/thiel",

    "library/07_reference/competitors",
    "library/07_reference/products",
    "library/07_reference/pricing",
    "library/07_reference/feature_maps",
]


def main():
    root = Path.cwd()

    for dir_path in DIRS:
        path = root / dir_path
        path.mkdir(parents=True, exist_ok=True)

        # 保留空目录，方便 Git 提交目录结构
        gitkeep = path / ".gitkeep"
        gitkeep.touch(exist_ok=True)

    print("MetaOS library 目录结构创建完成。")
    print(f"根目录: {root / 'library'}")
    print(f"共创建/确认目录数量: {len(DIRS)}")


if __name__ == "__main__":
    main()