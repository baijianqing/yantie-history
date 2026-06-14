"""Static plan data for Alpha gate checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoreBook:
    title: str
    aliases: tuple[str, ...]
    group: str
    stage: str


CORE_BOOKS: tuple[CoreBook, ...] = (
    CoreBook("论语", ("论语", "Analects"), "意图、价值与自我治理", "6-7"),
    CoreBook("庄子", ("庄子", "Zhuangzi"), "意图、价值与自我治理", "6-7"),
    CoreBook("传习录", ("传习录", "Instructions for Practical Living"), "意图、价值与自我治理", "6-7"),
    CoreBook("道德经", ("道德经", "老子", "Laozi", "Tao Te Ching", "Dao De Jing"), "意图、价值与自我治理", "6-7"),
    CoreBook("鬼谷子", ("鬼谷子", "Guiguzi"), "意图、价值与自我治理", "6-7"),
    CoreBook("黄帝内经", ("黄帝内经", "Huangdi Neijing", "Yellow Emperor's Inner Canon"), "意图、价值与自我治理", "6-7"),
    CoreBook("黄帝四经", ("黄帝四经", "Huangdi Sijing", "Four Classics of the Yellow Emperor"), "意图、价值与自我治理", "6-7"),
    CoreBook("阴符经", ("阴符经", "Yinfu Jing"), "意图、价值与自我治理", "6-7"),
    CoreBook("易经", ("易经", "周易", "I Ching", "Yijing", "Book of Changes"), "意图、价值与自我治理", "6-7"),
    CoreBook("资治通鉴", ("资治通鉴", "Zizhi Tongjian", "Comprehensive Mirror"), "意图、价值与自我治理", "6-7"),
    CoreBook("理想国", ("理想国", "Republic", "Plato's Republic", "柏拉图"), "意图、价值与自我治理", "6-7"),
    CoreBook("尼各马可伦理学", ("尼各马可伦理学", "Nicomachean Ethics"), "意图、价值与自我治理", "6-7"),
    CoreBook("心理学原理", ("心理学原理", "Principles of Psychology"), "注意力、元认知与认知控制", "8-9"),
    CoreBook("Know Thyself", ("Know Thyself", "Stephen Fleming"), "注意力、元认知与认知控制", "8-9"),
    CoreBook(
        "Rationality and the Reflective Mind",
        ("Rationality and the Reflective Mind", "Keith Stanovich"),
        "注意力、元认知与认知控制",
        "8-9",
    ),
    CoreBook("The Distracted Mind", ("The Distracted Mind", "Gazzaley", "Rosen"), "注意力、元认知与认知控制", "8-9"),
    CoreBook("人有人的用处", ("人有人的用处", "The Human Use of Human Beings", "Norbert Wiener"), "系统论、控制论与组织设计", "8-9"),
    CoreBook("人工科学", ("人工科学", "The Sciences of the Artificial", "Herbert Simon"), "系统论、控制论与组织设计", "8-9"),
    CoreBook("系统之美", ("系统之美", "Thinking in Systems", "Donella Meadows"), "系统论、控制论与组织设计", "4-5"),
    CoreBook("国家的视角", ("国家的视角", "Seeing Like a State", "James C. Scott"), "系统论、控制论与组织设计", "8-9"),
    CoreBook("娱乐至死", ("娱乐至死", "Amusing Ourselves to Death", "Neil Postman"), "注意力经济与媒介批判", "4-5"),
    CoreBook("浅薄", ("浅薄", "The Shallows", "Nicholas Carr"), "注意力经济与媒介批判", "4-5"),
    CoreBook("注意力商人", ("注意力商人", "The Attention Merchants", "Tim Wu"), "注意力经济与媒介批判", "4-5"),
    CoreBook("Stand Out of Our Light", ("Stand Out of Our Light", "James Williams"), "注意力经济与媒介批判", "4-5"),
    CoreBook("好战略，坏战略", ("好战略，坏战略", "Good Strategy Bad Strategy", "Good Strategy, Bad Strategy"), "战略、行动与组织执行", "10"),
    CoreBook("目标", ("目标", "The Goal", "Eliyahu Goldratt"), "战略、行动与组织执行", "10"),
    CoreBook("高产出管理", ("高产出管理", "High Output Management", "Andy Grove"), "战略、行动与组织执行", "10"),
    CoreBook("清单革命", ("清单革命", "The Checklist Manifesto", "Atul Gawande"), "战略、行动与组织执行", "4-5"),
    CoreBook("谈美", ("谈美", "朱光潜"), "艺术、审美与精神恢复", "11"),
    CoreBook("美学散步", ("美学散步", "宗白华"), "艺术、审美与精神恢复", "11"),
    CoreBook("人间词话", ("人间词话", "王国维"), "艺术、审美与精神恢复", "11"),
    CoreBook("为什么读经典", ("为什么读经典", "Why Read the Classics", "Italo Calvino"), "艺术、审美与精神恢复", "11"),
)


STAGE_RANK: dict[str, int] = {
    "0": 0,
    "1": 1,
    "2-3": 2,
    "4-5": 3,
    "6-7": 4,
    "8-9": 5,
    "10": 6,
    "11": 7,
    "12": 8,
    "all": 99,
}


BOOK_PROFILE_MARKERS: tuple[str, ...] = (
    "这本书在回答什么问题",
    "对 MetaOS 的作用",
    "MetaOS",
    "机制",
)

STRUCTURED_CARD_MARKERS: tuple[str, ...] = (
    "这本书在回答什么问题",
    "核心主张",
    "证据",
    "反对意见",
    "改变了我的什么判断",
    "转化成 MetaOS",
)

MECHANISM_MARKERS: tuple[str, ...] = (
    "机制卡",
    "产品机制",
    "行动规则",
    "转化成 MetaOS",
    "应转化成 MetaOS",
)

PERSONAL_PATH_MARKERS: tuple[str, ...] = (
    "00_metaos",
    "personal",
    "decisions",
    "failures",
    "self_evolution",
    "journal",
    "daily",
    "review",
    "attention",
)

PERSONAL_CONTENT_MARKERS: tuple[str, ...] = (
    "每日工作记录",
    "开发日志",
    "重要决策",
    "注意力漂移",
    "失败复盘",
    "未执行",
    "专家建议",
    "今日意图",
)

VIDEO_STAGE_BOOKS: tuple[str, ...] = (
    "娱乐至死",
    "浅薄",
    "注意力商人",
    "Stand Out of Our Light",
    "系统之美",
    "清单革命",
)
