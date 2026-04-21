"""
测试脚本 - 验证各模块功能
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 50)
print("历史人物对话Agent - 功能测试")
print("=" * 50)

# 1. 测试配置加载
print("\n[1] 测试配置加载...")
try:
    from config import get_settings
    settings = get_settings()
    print(f"✓ API Key: {settings.openai_api_key[:20]}...")
    print(f"✓ Model: {settings.openai_model}")
    print(f"✓ API Base: {settings.openai_api_base}")
except Exception as e:
    print(f"✗ 配置加载失败: {e}")
    sys.exit(1)

# 2. 测试人物管理器
print("\n[2] 测试人物管理器...")
try:
    from src.characters import character_manager
    characters = character_manager.get_all_characters()
    print(f"✓ 加载了 {len(characters)} 位历史人物:")
    for char in characters:
        print(f"  - {char.avatar} {char.name} ({char.dynasty})")
except Exception as e:
    print(f"✗ 人物管理器失败: {e}")
    sys.exit(1)

# 3. 测试人物Prompt生成
print("\n[3] 测试Prompt生成...")
try:
    char = character_manager.get_character("秦始皇")
    prompt = char.get_system_prompt()
    print(f"✓ 秦始皇的Prompt长度: {len(prompt)} 字符")
    print(f"  前100字: {prompt[:100]}...")
except Exception as e:
    print(f"✗ Prompt生成失败: {e}")
    sys.exit(1)

# 4. 测试LLM连接
print("\n[4] 测试LLM连接...")
try:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_api_base,
    )
    response = llm.invoke("你好，请用一句话介绍自己")
    print(f"✓ LLM响应: {response.content[:50]}...")
except Exception as e:
    print(f"✗ LLM连接失败: {e}")
    sys.exit(1)

# 5. 测试Agent对话
print("\n[5] 测试Agent对话...")
try:
    from src.agents import HistoryCharacterAgent
    char = character_manager.get_character("李白")
    agent = HistoryCharacterAgent(char)
    response = agent.chat("你好，请自我介绍一下", session_id="test")
    print(f"✓ 李白回复: {response[:100]}...")
except Exception as e:
    print(f"✗ Agent对话失败: {e}")
    sys.exit(1)

# 6. 测试向量库（可选）
print("\n[6] 测试向量库...")
try:
    from src.retrievers import VectorStoreManager
    vs = VectorStoreManager()
    count = vs.get_document_count()
    print(f"✓ 向量库文档数: {count}")
except Exception as e:
    print(f"⚠ 向量库测试跳过: {e}")

print("\n" + "=" * 50)
print("✓ 所有测试通过！项目可以正常运行")
print("=" * 50)
print("\n启动Web应用: streamlit run web/app.py")
