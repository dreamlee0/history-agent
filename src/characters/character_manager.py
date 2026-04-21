"""
历史人物管理器 - 支持按朝代分类
"""
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, field
import yaml


@dataclass
class HistoricalCharacter:
    """历史人物数据类"""
    name: str
    dynasty: str
    title: str
    years: str
    avatar: str
    personality: str
    speaking_style: str
    knowledge_focus: List[str] = field(default_factory=list)
    famous_quotes: List[str] = field(default_factory=list)

    def get_system_prompt(self) -> str:
        """生成系统提示词"""
        return f"""你现在扮演中国历史人物【{self.name}】。

## 人物信息
- 朝代：{self.dynasty}
- 身份：{self.title}
- 生卒年：{self.years}

## 人物性格
{self.personality}

## 说话风格
{self.speaking_style}

## 知识领域
你精通以下历史内容：
{chr(10).join(f'- {item}' for item in self.knowledge_focus)}

## 名言
{chr(10).join(f'"{quote}"' for quote in self.famous_quotes)}

## 回复要求
1. 始终以{self.name}的身份回答，不要跳出角色
2. 回答要符合历史事实，基于真实史料
3. 语言风格要符合你的身份和时代特点
4. 如果问到超出你知识范围的问题，可以表示不知，但要保持角色
5. 回答要有深度，展现历史人物的智慧和见解
"""


# 朝代顺序（用于排序显示）
DYNASTY_ORDER = [
    "上古", "商朝", "西周", "春秋", "战国", "秦朝",
    "西汉", "东汉末", "三国蜀汉", "三国东吴", "三国曹魏",
    "东晋", "隋朝", "唐朝", "北宋", "南宋", "元朝", "明朝", "清朝"
]


class CharacterManager:
    """人物管理器"""

    def __init__(self, characters_dir: str = "./data/characters"):
        self.characters_dir = Path(characters_dir)
        self._characters: Dict[str, HistoricalCharacter] = {}
        self._load_characters()

    def _load_characters(self):
        """加载所有人物配置（支持子目录）"""
        if not self.characters_dir.exists():
            return

        # 遍历所有yaml文件（包括子目录）
        for file_path in self.characters_dir.rglob("*.yaml"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    char = HistoricalCharacter(**data)
                    self._characters[char.name] = char
            except Exception as e:
                print(f"加载人物配置失败 {file_path}: {e}")

    def get_character(self, name: str) -> Optional[HistoricalCharacter]:
        """获取人物"""
        return self._characters.get(name)

    def get_all_characters(self) -> List[HistoricalCharacter]:
        """获取所有人物"""
        return list(self._characters.values())

    def get_characters_by_dynasty(self) -> Dict[str, List[HistoricalCharacter]]:
        """按朝代分组获取人物（按历史顺序排序）"""
        result = {}
        for char in self._characters.values():
            if char.dynasty not in result:
                result[char.dynasty] = []
            result[char.dynasty].append(char)

        # 按朝代顺序排序
        sorted_result = {}
        for dynasty in DYNASTY_ORDER:
            if dynasty in result:
                sorted_result[dynasty] = result[dynasty]

        # 添加未在顺序列表中的朝代
        for dynasty, chars in result.items():
            if dynasty not in sorted_result:
                sorted_result[dynasty] = chars

        return sorted_result

    def list_names(self) -> List[str]:
        """列出所有人物名称"""
        return list(self._characters.keys())

    def get_count(self) -> int:
        """获取人物总数"""
        return len(self._characters)


# 全局人物管理器
character_manager = CharacterManager()
