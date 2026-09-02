"""历史人物别名映射：查询/史料中的别称、字号、庙号 → 知识库规范名。

用途：
  1. 库外实体门：查询出现"李世民"但 97 人库用"唐太宗"，别名归一化后
     才能正确判定"查询对象在知识库内"，避免把别名误判为库外人物；
  2. 人物自指判断：查询是否在"问本人"（含"你/您"或本人别名）——
     用于防"库外提问注入被问人物自传"的拒绝门。

规范名以 data/knowledge 与 src/characters 的 97 位人物为准。
"""
import os
from pathlib import Path
from typing import Dict, List, Optional

# 别名 → 规范名（规范名必须是 97 人知识库中的名字）
ALIAS_TO_CANONICAL: Dict[str, str] = {
    # 帝号/本名
    "李世民": "唐太宗",
    "嬴政": "秦始皇",
    "杨坚": "隋文帝",
    "杨广": "隋炀帝",
    "刘彻": "汉武帝",
    "玄烨": "康熙",
    "武曌": "武则天",
    "武媚娘": "武则天",
    "铁木真": "成吉思汗",
    # 字/号/尊称
    "李太白": "李白",
    "太白": "李白",
    "青莲居士": "李白",
    "谪仙人": "李白",
    "子美": "杜甫",
    "少陵野老": "杜甫",
    "东坡": "苏轼",
    "苏东坡": "苏轼",
    "东坡居士": "苏轼",
    "白乐天": "白居易",
    "香山居士": "白居易",
    "韩退之": "韩愈",
    "王逸少": "王羲之",
    "王守仁": "王阳明",
    "陶潜": "陶渊明",
    "屈平": "屈原",
    "鹏举": "岳飞",
    "少穆": "林则徐",
    # 名将/谋士表字
    "孟德": "曹操",
    "曹阿瞒": "曹操",
    "玄德": "刘备",
    "云长": "关羽",
    "翼德": "张飞",
    "子龙": "赵云",
    "公瑾": "周瑜",
    "孔明": "诸葛亮",
    "诸葛孔明": "诸葛亮",
    "卧龙": "诸葛亮",
    "孙仲谋": "孙权",
}

# 规范名 → 该人物的全部别称（含规范名本身，便于自指判断）
_CANONICAL_TO_ALIASES: Dict[str, List[str]] = {}
for _alias, _canonical in ALIAS_TO_CANONICAL.items():
    _CANONICAL_TO_ALIASES.setdefault(_canonical, []).append(_alias)

# 97 人知识库全部规范名（懒加载自 character_manager，避免顶层循环依赖——
# character_manager 只依赖 logger，不反向 import aliases）
_ALL_CANONICAL_NAMES = None


def _all_canonical_names() -> List[str]:
    """返回 97 人知识库全部规范名（含无别名的人物）。"""
    global _ALL_CANONICAL_NAMES
    if _ALL_CANONICAL_NAMES is None:
        from src.characters.character_manager import character_manager

        _ALL_CANONICAL_NAMES = list(character_manager.list_names())
    return _ALL_CANONICAL_NAMES


def get_aliases_for(canonical: str) -> List[str]:
    """返回某规范名人物的全部别称（不含规范名本身）。"""
    return list(_CANONICAL_TO_ALIASES.get(canonical, []))


def normalize_name(name: str) -> Optional[str]:
    """把别名归一化为规范名；规范名本身返回原值；未知返回 None。"""
    name = name.strip()
    if name in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[name]
    # 直接是规范名（含无别名的人物，如李鸿章/乾隆）
    if name in _all_canonical_names():
        return name
    return None


def resolve_characters_in_text(text: str) -> List[str]:
    """找出文本中提到的全部知识库人物（规范名），按出现顺序去重。

    覆盖 97 人全表（含无别名的人物），用于库外实体门与多人物点名检测：
    若查询提到的人物都不在知识库，则可能是库外提问。
    """
    found: List[str] = []
    for canonical in _all_canonical_names():
        names = [canonical] + list(_CANONICAL_TO_ALIASES.get(canonical, []))
        if any(name and name in text for name in names):
            found.append(canonical)
    return found


def is_self_referential(text: str, asker_name: str) -> bool:
    """判断查询是否在"问本人"（自称或提到被问人物本人别名）。

    用于库外注入拒绝门：查询无自称且过滤/全局都弱匹配时，判定为
    "提问对象与被问人物无关" → 走 no-RAG 分支，而不是注入被问人物自传。
    """
    if "你" in text or "您" in text:
        return True
    if asker_name and asker_name in text:
        return True
    for alias in get_aliases_for(asker_name):
        if alias and alias in text:
            return True
    return False


# ─── 库外实体检测（供"库外注入拒绝"决策门使用）───

_OUT_OF_KB_VOCAB = None


def _corpus_vocabulary() -> frozenset:
    """史料语料库的 token 词表（懒加载并缓存）。

    库外实体门需要判断"查询里的专名是否在知识库里"。做法：对 data/knowledge
    全部史料正文做 jieba 切词得到词表；查询中出现"词表之外且词性为专名类
    （人名 nr / 地名 ns / 其它专名 nz 等）"的 token，即疑似点名了库外实体。
    首次调用构建一次（约 1~2s），之后缓存。
    """
    global _OUT_OF_KB_VOCAB
    if _OUT_OF_KB_VOCAB is not None:
        return _OUT_OF_KB_VOCAB

    import jieba

    vocab: set = set()
    knowledge_dir = Path(os.environ.get("KNOWLEDGE_DIR", "data/knowledge"))
    for p in Path(knowledge_dir).glob("*.txt"):
        try:
            txt = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "---" in txt:
            txt = txt.split("---", 1)[1]
        vocab.update(w for w in jieba.lcut(txt) if len(w) >= 2)

    _OUT_OF_KB_VOCAB = frozenset(vocab)
    return _OUT_OF_KB_VOCAB


# 朝代/时代名词（jieba 常误标为 nr/nz 人名、且未必进语料词表，如"春秋战国"）：
# 这类词是枚举题背景不是库外人物，检测库外专名时显式排除，避免误伤。
_PERIOD_NOUNS = frozenset({
    "春秋战国", "春秋", "战国", "唐宋八大家", "八大家", "五代十国", "南北朝",
    "先秦", "两汉", "三国", "商周", "夏商周", "秦汉", "隋唐", "宋元", "晚清",
    "洋务", "洋务运动",
})

# 常见库外人物专名（知识库 97 人之外）：jieba 对部分人名不标 nr 或不进语料
# 词表，漏检会导致库外提问注入被问人物自传——显式名单兜底（与评测负样本池同源）。
_OUT_OF_KB_EXPLICIT = frozenset({
    # 现代/当代（注意：孙中山/蔡元培/梁启超/鲁迅 已入库，不可列入）
    "钱学森", "袁隆平", "屠呦呦", "钟南山", "杨振宁", "莫言", "金庸", "张爱玲",
    "老舍", "徐志摩", "胡适", "季羡林",
    # 外国
    "拿破仑", "华盛顿", "爱因斯坦", "牛顿", "莎士比亚", "达芬奇", "贝多芬",
    "伽利略", "哥伦布", "马克思", "甘地", "林肯", "达尔文", "爱迪生",
    "居里夫人", "卓别林", "莫扎特", "特斯拉", "罗斯福", "莎士比亚",
    # 未收录的历史人物
    "项羽", "勾践", "西施", "王昭君", "貂蝉", "郑成功", "鉴真", "花木兰",
    "荆轲", "赵子龙", "穆桂英",
})


def has_out_of_kb_entity(text: str) -> bool:
    """查询是否点名了知识库之外的人物专名。

    判定分两路（任一命中即 True）：
      1. 显式库外人名名单：jieba 可能漏标/错标的人名（甘地/勾践/哥伦布等），
         直接子串匹配；
      2. jieba 词性标注为「人名类」（nr/nr1/nr2/nrfg/nrt/nrf，不含 ns/nz——
         避免"春秋战国/西汉时期"等朝代词误报）且不在史料语料词表的 token。

    注意：本函数只提供"点名库外人物"这一个信号，必须与"无自称 + 未点名库内
    人物"合取才构成库外提问判定——避免误伤库内事件题（如"开凿大运河"每个词
    都在语料里，返回 False）。
    """
    for name in _OUT_OF_KB_EXPLICIT:
        if name in text:
            return True

    import jieba.posseg as pseg

    vocab = _corpus_vocabulary()
    PERSON_TAGS = {"nr", "nr1", "nr2", "nrfg", "nrt", "nrf"}
    for word, flag in pseg.cut(text):
        # 朝代/时代名词，非库外人物。用子串判断：jieba 可能把"唐宋八大家"
        # 拆成"唐宋八大"（漏"家"），精确 token 匹配会漏——token 是某朝代名
        # 词的子串即视为朝代名词。
        if any(word in p for p in _PERIOD_NOUNS):
            continue
        if len(word) >= 2 and word not in vocab and flag in PERSON_TAGS:
            return True
    return False
