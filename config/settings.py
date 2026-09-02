"""
配置管理 - 支持 DeepSeek/智谱等 OpenAI 兼容接口
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # LLM (OpenAI兼容接口，可接智谱/DeepSeek/OpenAI等)
    llm_api_key: str = Field(default="", env="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.deepseek.com",
        env="LLM_BASE_URL",
    )
    llm_model: str = Field(default="deepseek-v4-flash", env="LLM_MODEL")
    # 生成最大 token 数：deepseek-v4-flash 等 reasoning 模型的 reasoning_content
    # 会吃掉 token 预算，不设上限时可能出现 content 为空（finish_reason=length）。
    # 在线评测（evaluate_generation）实测 max_tokens=1024 可稳定返回正文，故作为
    # 生产默认（经 LLM_MAX_TOKENS 覆盖）。
    llm_max_tokens: int = Field(default=1024, env="LLM_MAX_TOKENS")

    # Embedding配置 (本地 HuggingFace 模型，免费无需 API Key)
    embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5", env="EMBEDDING_MODEL"
    )

    # 向量数据库
    vector_db_path: str = Field(
        default="./data/vector_db",
        env="VECTOR_DB_PATH"
    )

    # Agent
    # temperature: 闲聊/无史料命中时使用；temperature_factual: RAG 命中史料时使用。
    # 史实问答需要低温度减少幻觉（默认 0.3），闲聊可保持较高的 0.8 更自然。
    temperature: float = 0.8
    temperature_factual: float = 0.3
    # 注入 LLM 上下文的历史消息条数上限（可经环境变量 MAX_HISTORY 覆盖）
    max_history: int = Field(default=10, env="MAX_HISTORY")
    verbose: bool = True

    # RAG配置
    rag_top_k: int = 3
    rag_enabled: bool = True
    # 人物过滤相关性阈值：按人物过滤的最优结果距离若明显劣于全局最优
    # （> 该倍数），判定问题与本人物无关，退回全局检索（防跨人物污染）。
    # 默认值 1.25 由 scripts/evaluate_retrieval_full.py 在 44 条扩展标注评测集
    # （data/eval/retrieval_eval_full.json）上阈值扫描重标定：gushiwen 古籍原文
    # 入库后跨人高相似陷阱加剧（3 例 ratio 恰落在 1.20 之下漏过，如"隋文帝问
    # 大运河"曾把文帝自传当史料注入），收紧为 1.25 后决策正确率 1.000
    # （详见 RAG_EVALUATION_REPORT_FULL.md §2.4/§13.2），可在 .env 覆盖重调。
    filtered_score_ratio: float = Field(default=1.25, env="FILTERED_SCORE_RATIO")

    # 检索模式："similarity"（纯相似度，默认）| "mmr"（最大边际相关重排）|
    # "hybrid"（稠密向量 + BM25 词法的 RRF 融合召回，见
    #  VectorStoreManager.hybrid_search_with_score）。默认保持纯相似度以不改变
    # 既有行为；hybrid 模式对精确人名/罕见词/多人物枚举查询的召回更稳。
    retrieval_mode: str = Field(default="similarity", env="RETRIEVAL_MODE")
    # 多人物联合检索（multi 分支）返回条数：枚举题（"唐朝有哪些诗人"）与点名题
    # （"曹操、刘备、孙权…"）走该分支，返回 top-multi_top_k 覆盖 3-7 个期望人物。
    # 评测 multi 子集按此口径计算 Recall@multi_top_k。
    multi_top_k: int = Field(default=7, env="MULTI_TOP_K")
    # hybrid 混合检索参数：稠密侧召回 fetch_k 条、BM25 侧召回 hybrid_bm25_k 条，
    # 两侧按 RRF（常数 hybrid_rrf_k）融合成候选池；路径决策仍基于稠密距离。
    hybrid_bm25_k: int = Field(default=30, env="HYBRID_BM25_K")
    hybrid_rrf_k: int = Field(default=60, env="HYBRID_RRF_K")
    # LLM 成本估算价格（¥ / 1M tokens）。仅供离线估算脚本 benchmark_retrieval.py
    # 使用，不参与任何真实调用。默认值按 DeepSeek deepseek-v4-flash 官价填写。
    llm_price_in: float = Field(default=1.0, env="LLM_PRICE_IN")
    llm_price_out: float = Field(default=2.0, env="LLM_PRICE_OUT")

    # ── 检索重排（Rerank）──
    # rerank_mode: "hybrid"（默认，jieba+TF-IDF 词法与稠密向量 RRF 融合，
    #   完全离线）| "cross_encoder"（bge-reranker，本地无模型时回退 hybrid）
    #   | "none"（关闭，保持纯相似度）。
    rerank_mode: str = Field(default="hybrid", env="RERANK_MODE")
    # 重排前的候选池大小：先召回 k_fetch 条再重排取 top-k。
    rerank_k_fetch: int = Field(default=15, env="RERANK_K_FETCH")
    # cross_encoder 模式使用的重排模型（需联网下载到本地 HF 缓存后生效）。
    rerank_cross_encoder_model: str = Field(
        default="BAAI/bge-reranker-v2-m3", env="RERANK_CROSS_ENCODER_MODEL"
    )

    # ── 检索决策门阈值（默认值由 44 条扩展评测集标定，可在 .env 覆盖）──
    # 决策门 1（强相关全局门）：全局最优是强相关（距离 < 该阈值）且过滤结果
    #   明显更差（绝对距离差 > gap_threshold）时，即使比值未超 filtered_score_ratio
    #   也退回全局——修"诸葛亮问曹操 ratio=1.192 未兜底"类自传陷阱题。
    strong_global_threshold: float = Field(default=0.70, env="STRONG_GLOBAL_THRESHOLD")
    gap_threshold: float = Field(default=0.10, env="GAP_THRESHOLD")
    # 决策门 2（库外注入拒绝）已改为纯人物名判据（无自称 + 未点名库内人 +
    # 点名库外专名），不再依赖距离阈值——原 weak_match_threshold 距离条件会让
    # 钟南山/郑成功等强相关误报漏过（best_global<0.90），已删除该配置。

    # ── 数据源双轨（真实史源 vs persona）──
    # persona_fallback=True（默认，过渡期）：persona（内置生成摘要）可参与检索、
    # 可被引用，但 block/footer 明确标注"（内置摘要·非权威史源，仅风格参考）"，
    # 且真实史源（doc_type=historical，ctext/维基/公版古籍）优先排序；
    # persona_fallback=False（严格模式）：persona 完全移出史实检索，只有真实史源
    # 才可检索/引用（离线且真实史源未入库时，检索会退化为 no-RAG）。
    persona_fallback: bool = Field(default=True, env="PERSONA_FALLBACK")

    # 数据库配置
    db_path: str = Field(default="./data/history_chat.db", env="DB_PATH")
    # 对话保留天数：超过该天数的对话由 scripts/cleanup_db.py 清理；
    # 0 表示不自动清理（默认，保持既有无限增长行为，由部署者显式开启）。
    conversation_retention_days: int = Field(
        default=0, env="CONVERSATION_RETENTION_DAYS"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
