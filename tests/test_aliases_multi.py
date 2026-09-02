"""别名 97-扩展 与 多人物联合检索检测（阶段3）测试。

覆盖两类修复：
  - aliases.py 97-extension：resolve_characters_in_text 覆盖无别名的 97 人名
    （李鸿章/乾隆 等），不再只认别名表里的人；
  - 库外人名检测：显式名单兜底 jieba 漏标人名，且对朝代/时代词（春秋战国/
    唐宋八大家/西汉时期）不误报；
  - _detect_multi：点名式（≥2 人）与枚举式（分类名词）检出，单点名他人
    （cross_trap）与库外负面不误触发。
"""
from src.knowledge.aliases import (
    normalize_name,
    resolve_characters_in_text,
    has_out_of_kb_entity,
)
from src.agents.history_agent import _detect_multi


def test_resolve_finds_alias_less_canonical():
    """97-扩展：无别名的规范名（李鸿章/乾隆）也能被 resolve 检出"""
    assert "李鸿章" in resolve_characters_in_text("李鸿章在洋务运动中的主要作为有哪些")
    assert "乾隆" in resolve_characters_in_text("乾隆盛世的主要成就表现在哪些方面")


def test_resolve_still_finds_aliased_canonical():
    """回归：别名归一化不受影响（李世民→唐太宗）"""
    assert "唐太宗" in resolve_characters_in_text("李世民有哪些功绩")


def test_normalize_accepts_alias_less_canonical():
    """97-扩展：normalize_name 认无别名的规范名"""
    assert normalize_name("李鸿章") == "李鸿章"
    assert normalize_name("李世民") == "唐太宗"


def test_out_of_kb_explicit_list():
    """显式库外人名名单命中（jieba 可能漏标的人名）"""
    for q in ("钟南山有哪些主要成就和贡献", "甘地有哪些主要成就和贡献",
              "哥伦布有哪些主要成就和贡献", "钱学森为中国航天事业做出了哪些贡献"):
        assert has_out_of_kb_entity(q), f"应检出库外人名: {q}"


def test_out_of_kb_not_fire_on_era_words():
    """朝代/时代词不误报（旧版把 春秋战国/唐宋八大家/西汉时期 当库外专名）"""
    for q in ("春秋战国时期有哪些重要的思想家", "唐宋八大家中哪些是宋代人",
              "西汉时期有哪些著名的将领"):
        assert not has_out_of_kb_entity(q), f"不应误报朝代词: {q}"


def test_detect_multi_named_two_plus():
    """点名式：查询点名 ≥2 位库内他人 → 返回名单"""
    assert set(_detect_multi("曹操、刘备、孙权谁更胜一筹", "诸葛亮")) == {"曹操", "刘备", "孙权"}


def test_detect_multi_enumeration():
    """枚举式：分类名词 + 枚举词 → 返回空名单（走多样性全局池）"""
    assert _detect_multi("唐朝有哪些著名的诗人", "苏轼") == []


def test_detect_multi_era_context_single_name():
    """枚举式 + 时代上下文点名（汉武帝时期）→ 仍走 multi"""
    assert _detect_multi("汉武帝时期有哪些抗击匈奴的名将", "霍去病") == []


def test_detect_multi_single_target_not_multi():
    """单点名他人（cross_trap 口径）→ 不走 multi（交 named_other 门）"""
    assert _detect_multi("张飞的性格特点和主要战绩有哪些", "关羽") is None
    assert _detect_multi("李鸿章在洋务运动中的主要作为有哪些", "左宗棠") is None


def test_detect_multi_self_referential_not_multi():
    """自指枚举题（问本人）→ 不走 multi"""
    assert _detect_multi("你抗击金军的主要事迹有哪些", "岳飞") is None


def test_detect_multi_negative_not_multi():
    """库外负面（X有哪些成就，无分类名词）→ 不走 multi"""
    assert _detect_multi("钟南山有哪些主要成就和贡献", "司马迁") is None
