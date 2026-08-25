#!/bin/bash

# 历史人物对话Agent启动脚本

echo "========================================"
echo "  历史人物对话 Agent"
echo "========================================"

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到.env文件，正在从模板创建..."
    cp .env.example .env
    echo "📝 已生成 .env，请编辑填入你的 API Key（LLM_API_KEY）"
    echo "    未配置 Key 时应用仍可启动，但对话功能需要 Key 才能使用"
fi

# 启动应用
echo "🚀 启动Web应用..."
streamlit run web/app.py
