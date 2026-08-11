"""人物配置与知识覆盖测试"""
from pathlib import Path

from src.characters import character_manager
from src.characters.character_manager import DYNASTY_ORDER

# 当前 YAML 人物总数（README 写的 96 与实际情况不一致，见 test_doc_consistency）
TOTAL_CHARACTERS = 97


def test_all_characters_load():
    assert character_manager.get_count() == TOTAL_CHARACTERS


def test_required_fields_present():
    """每个人物都必须具备全部必填字段"""
    for char in character_manager.get_all_characters():
        assert char.name, "name 缺失"
        assert char.dynasty, f"{char.name}: dynasty 缺失"
        assert char.title, f"{char.name}: title 缺失"
        assert char.years, f"{char.name}: years 缺失"
        assert char.avatar, f"{char.name}: avatar 缺失"
        assert char.personality, f"{char.name}: personality 缺失"
        assert char.speaking_style, f"{char.name}: speaking_style 缺失"
        assert char.knowledge_focus, f"{char.name}: knowledge_focus 缺失"
        assert char.famous_quotes, f"{char.name}: famous_quotes 缺失"


def test_dynasty_all_in_order():
    """朝代都应在 DYNASTY_ORDER 中，保证侧边栏排序正常"""
    dynasties = {c.dynasty for c in character_manager.get_all_characters()}
    assert dynasties <= set(DYNASTY_ORDER), f"未收录的朝代: {dynasties - set(DYNASTY_ORDER)}"


def test_every_character_has_knowledge_file():
    """回归：蒙恬/李斯曾缺知识文件导致按人物检索落空，现在必须全覆盖。

    否则聊天时 search_by_character 返回 0 条，只能靠全局兜底，
    会拉入无关人物史料。
    """
    missing = []
    for char in character_manager.get_all_characters():
        f = Path("data/knowledge") / f"biography_{char.name}_内置.txt"
        if not f.exists():
            missing.append(char.name)
    assert missing == [], f"缺少知识文件: {missing}"


def test_duplicate_names():
    """人物名不应重复"""
    names = [c.name for c in character_manager.get_all_characters()]
    assert len(names) == len(set(names)), "存在重名人物"
