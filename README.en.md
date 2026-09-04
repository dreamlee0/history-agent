# 🏛️ History Character Chat（history-rag-chat）

English | [中文](README.md)

> A **LangChain + RAG** based history-character chat system: immersive, traceable multi-turn conversations with Chinese historical figures.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-1.2-green.svg)](https://langchain.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📸 Screenshots

### 🎭 Character Selection

<div align="center">
  <img src="images/人物选择.png" alt="Character selection UI" width="800"/>
</div>

### 💬 Conversation View

<div align="center">
  <img src="images/对话展示.png" alt="Conversation view" width="800"/>
</div>

### 🖥️ Chat Interface

<div align="center">
  <img src="images/chat界面.png" alt="Chat interface" width="800"/>
</div>

## ✨ Features

- 🎭 **Role play** · 97 historical figures across 21 dynasties (Three Kingdoms split into Shu Han / Eastern Wu / Cao Wei), with persona-matched tone
- 📚 **RAG-grounded answers** · based on real historical sources, with verifiable citations
- 💬 **Multi-turn memory** · persisted in SQLite, survives refresh
- 📤 **Conversation export** · Markdown / PDF
- 📏 **Built-in evaluation** · labeled eval set + hit@k / MRR / threshold calibration, making cross-figure pollution prevention measurable

## 🚀 Quick Start

Try it live: [history-rag-chat.streamlit.app](https://history-rag-chat.streamlit.app/)

```bash
git clone https://github.com/dreamlee0/history-rag-chat.git
cd history-rag-chat
pip install -r requirements.txt
cp .env.example .env          # set LLM_API_KEY (DeepSeek or any OpenAI-compatible endpoint)
streamlit run web/app.py
```

## 🧩 Tech Stack

| Component | Description |
|---|---|
| LangChain + Chroma | RAG retrieval |
| DeepSeek deepseek-v4-flash | LLM (OpenAI-compatible) |
| BAAI/bge-small-zh-v1.5 | Local embeddings (free, no API key) |
| SQLite + Streamlit | Persistence / Web UI |

## 📁 Project Structure

```
history-rag-chat/
├── config/                  # Configuration
│   └── settings.py
├── data/
│   ├── characters/          # 97 character profiles (YAML)
│   │   ├── shanggu/         # Antiquity
│   │   ├── shang/           # Shang
│   │   ├── xizhou/          # Western Zhou
│   │   ├── chunqiu/         # Spring & Autumn
│   │   ├── zhanguo/         # Warring States
│   │   ├── qin/             # Qin
│   │   ├── xihan/           # Western Han
│   │   ├── donghan/         # Eastern Han
│   │   ├── sanguo/          # Three Kingdoms
│   │   ├── dongjin/         # Eastern Jin
│   │   ├── sui/             # Sui
│   │   ├── tang/            # Tang
│   │   ├── beisong/         # Northern Song
│   │   ├── nansong/         # Southern Song
│   │   ├── yuan/            # Yuan
│   │   ├── ming/            # Ming
│   │   ├── qing/            # Qing
│   │   ├── wudai/           # Five Dynasties
│   │   └── minguo/          # Republic of China
│   ├── knowledge/           # Dual-track corpus: 99 persona + 107 historical (gushiwen/baike/ctext)
│   ├── eval/                # Labeled eval set
│   └── vector_db/           # Chroma vector DB
├── scripts/                 # Utility scripts
├── src/
│   ├── agents/              # Chat orchestration / RAG
│   ├── characters/          # Character manager
│   ├── database/            # SQLite database
│   ├── memory/              # Conversation memory
│   └── retrievers/          # Vector retrieval
├── web/
│   ├── app.py               # Main app
│   ├── styles.py            # Ink-wash CSS style
│   └── export_utils.py      # Export utilities
├── images/                  # Screenshots
└── requirements.txt
```

## 📚 Historical Figures（97）

| Dynasty | Figures |
|---------|---------|
| **Antiquity** | 黄帝、炎帝、尧、舜、禹 |
| **Shang** | 商汤 |
| **Western Zhou** | 周文王、周武王、周公、姜子牙 |
| **Spring & Autumn** | 老子、孔子、孙武、墨子、范蠡 |
| **Warring States** | 商鞅、屈原、蔺相如、白起 |
| **Qin** | 秦始皇、李斯、蒙恬 |
| **Western Han** | 刘邦、张良、韩信、萧何、卫青、霍去病、张骞、司马迁、汉武帝 |
| **Eastern Han** | 曹操 |
| **Three Kingdoms** | 刘备、关羽、张飞、赵云、周瑜、孙权、司马懿、诸葛亮 |
| **Eastern Jin** | 王羲之、陶渊明 |
| **Sui** | 隋文帝、隋炀帝 |
| **Tang** | 唐太宗、武则天、李白、杜甫、白居易、王维、韩愈、颜真卿、玄奘、李商隐、杜牧 |
| **Northern Song** | 赵匡胤、范仲淹、欧阳修、王安石、司马光、苏轼 |
| **Southern Song** | 辛弃疾、陆游、文天祥、岳飞 |
| **Yuan** | 成吉思汗、忽必烈、关汉卿 |
| **Ming** | 朱元璋、朱棣、郑和、于谦、海瑞、戚继光、李时珍、徐霞客、王阳明、张居正 |
| **Qing** | 康熙、雍正、乾隆、纪晓岚、和珅、林则徐、曾国藩、左宗棠、李鸿章、张之洞、曹雪芹、郑板桥、慈禧 |
| **Five Dynasties** | 李煜、柴荣 |
| **Republic of China** | 孙中山、鲁迅、蔡元培、梁启超 |

## 💡 Usage Examples

```
# Talking with Li Bai
User: Master Li Bai, which of your poems is the most famous?
Li Bai: Hahaha! I have written countless poems in my life; if we speak of my finest, it must be Invitation to Wine (《将进酒》)!

# Talking with Zhuge Liang
User: Master Zhuge Liang, do you think the Northern Expeditions can succeed?
Zhuge Liang: I have thought long and hard about the Northern Expeditions. Though I know it is difficult, restoring the Han dynasty was the late Emperor's last wish...

# Talking with Confucius
User: Master Confucius, how can one become a junzi (a person of virtue)?
Confucius: The way of the junzi lies in cultivating oneself, harmonizing the family, governing the state, and bringing peace to all under heaven. First comes self-cultivation...
```

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| LLM_API_KEY | DeepSeek API key (or any OpenAI-compatible key) | - |
| LLM_BASE_URL | LLM endpoint | https://api.deepseek.com |
| LLM_MODEL | Model name | deepseek-v4-flash |
| LLM_MAX_TOKENS | Max generation tokens (deepseek-v4-flash's reasoning_content eats the budget; without a cap the reply can come back empty — 1024 verified stable in online eval) | 1024 |
| EMBEDDING_MODEL | Embedding model (local HuggingFace) | BAAI/bge-small-zh-v1.5 |
| VECTOR_DB_PATH | Vector DB path | ./data/vector_db |
| DB_PATH | Chat DB path | ./data/history_chat.db |
| MAX_HISTORY | History turns injected into the LLM context | 10 |
| FILTERED_SCORE_RATIO | Cross-figure pollution-prevention threshold (calibrated on the 159-item train split, validated on holdout; 1.25 optimal) | 1.25 |
| RAG_TOP_K | Number of source passages returned to the LLM (`_retrieve_knowledge` default k) | 3 |
| MULTI_TOP_K | Passages returned by the multi-figure joint-retrieval branch (named ≥2 people or enumeration queries; covers 3-7 expected figures; eval multi subset measures Recall at this k) | 7 |
| RETRIEVAL_MODE | Retrieval mode: `similarity` (dense) \| `hybrid` (dense + BM25 lexical RRF fusion recall, see "Evaluation") | similarity |
| HYBRID_BM25_K | BM25 candidate count on the lexical side of hybrid retrieval | 30 |
| HYBRID_RRF_K | Hybrid retrieval RRF fusion constant (same convention as the reranker) | 60 |
| CONVERSATION_RETENTION_DAYS | Conversation retention days; purged by `scripts/cleanup_db.py` beyond this; 0=never | 0 |
| RERANK_MODE | Rerank mode: `hybrid` (jieba+TF-IDF lexical × dense RRF fusion, fully offline) \| `cross_encoder` (bge-reranker, requires local cache) \| `none` | hybrid |
| RERANK_K_FETCH | Candidate-pool size before rerank (retrieve k_fetch, then rerank to top-k) | 15 |
| STRONG_GLOBAL_THRESHOLD | Decision gate 1: strong-global relevance threshold | 0.70 |
| GAP_THRESHOLD | Decision gate 1: distance-gap threshold for "filtered clearly worse than global" | 0.10 |
| PERSONA_FALLBACK | Dual-track switch: `true` (default) persona is retrievable but labeled "built-in summary · non-authoritative" and real sources take priority; `false` (strict mode) persona is fully removed from historical retrieval — only real sources are retrievable/citable | true |
| LLM_PRICE_IN / LLM_PRICE_OUT | LLM pricing (¥/1M tokens, used only by the offline cost-estimation script, not real billing) | 1.0 / 2.0 |

## 📜 Data Sources（Dual-track corpus）

The knowledge base is a **dual-track data source** (see [DATA_SOURCES.md](DATA_SOURCES.md) for details):

- **Real historical sources (`doc_type=historical`)** — excerpts of classical-text originals from
  gushiwen.cn (the primary source, fully ingested), ctext.org, and **Baidu Baike** (21 articles covering
  figures with no mapped official-history chapter; tertiary source, labeled as such). Annotated with
  **dynasty · book · chapter** (e.g. 春秋·《史记·孔子世家》); these are citable as grounding for answers.
  **All 97 figures now have a historical file** (107 historical + 99 persona);
- **Persona (`doc_type=persona`)** — built-in LLM-generated summaries (99 files with `_内置` suffix),
  used only as language-style reference / role setting, **not as factual basis**; citations are labeled
  "（内置摘要·非权威史源）" (built-in summary · non-authoritative).

Citation format: the source block header shows `出处: 春秋·《史记·孔子世家》 - 古诗文网（gushiwen.cn）`,
the footer `【参考史料】[1]《史记·孔子世家》- 春秋·古诗文网（gushiwen.cn)`; with `PERSONA_FALLBACK=off`,
persona is fully excluded from historical retrieval. The 97-figure → source mapping table lives in
`data/sources/character_sources.json` (focused on the 97 figures, not the whole 二十四史). Network reality
check: ctext.org is blocked (403 anti-crawling) and Chinese Wikipedia is unreachable, so the primary
classical-text source was switched to **gushiwen.cn** (see DATA_SOURCES.md「网络实测与源切换」).

```bash
# Print the crawl plan offline (URL list, no network); drop --dry-run to crawl for real
python scripts/crawl_knowledge.py --dry-run
python scripts/crawl_knowledge.py --sources all      # gushiwen originals + Chinese Wikipedia
python scripts/crawl_knowledge.py --sources gushiwen # gushiwen originals only (verified in this env)
python scripts/crawl_knowledge.py --characters 李白,孔子
```

## 📏 Evaluation（A "ruler" for retrieval）

Two labeled eval sets (**198 items**, stratified into train/holdout) + retrieval / latency / end-to-end / online-generation scripts:

```bash
# Basic set (26 items: ask-about-self / ask-about-others / ask-about-events,
# including "the figure's own bio is a trap" cases)
python scripts/evaluate_retrieval.py          # hit@1/hit@3/MRR + pollution-gate decision accuracy
python scripts/evaluate_retrieval.py --sweep  # threshold sweep (FILTERED_SCORE_RATIO=1.25 calibrated here)
python scripts/evaluate_retrieval.py --llm-grounding 5   # optional: real-LLM citation grounding check (paid)

# Extended set (198 items: 145 single-relevant / 31 multi-relevant enumeration / 22 out-of-KB negatives; train 159 / holdout 39)
python scripts/evaluate_retrieval_full.py          # hit@k / MRR / decision accuracy / multi-relevant Recall@7 / RAGAS context metrics / out-of-KB rejection rate
python scripts/evaluate_retrieval_full.py --split train      # eval on the train split only (threshold recalibration)
python scripts/evaluate_retrieval_full.py --split holdout    # generalization metrics reported here only
python scripts/evaluate_retrieval_full.py --sweep --split train  # threshold sweep (calibrated on train)
RETRIEVAL_MODE=hybrid python scripts/evaluate_retrieval_full.py  # hybrid retrieval (BM25×dense) comparison

# Latency / cost profiling (offline): per-stage p50/p90/mean (retrieval/rerank/LLM estimate/one-time cost)
python scripts/benchmark_retrieval.py --limit 20
python scripts/benchmark_retrieval.py --limit 20 --out bench.json   # dump results to file

# End-to-end evaluation: Mock LLM runs the full chat() pipeline offline (routing / citation grounding / latency); --llm live calls the real model (verified, see RAG_EVALUATION_REPORT_FINAL.md §3.4)
python scripts/evaluate_end_to_end.py
python scripts/evaluate_end_to_end.py --bad-cite   # verify out-of-range citations are dropped
python scripts/evaluate_end_to_end.py --llm live   # real model (requires DeepSeek key in .env)

# Online generation eval (RAGAS-style, real LLM, requires .env DeepSeek key; --cache resumes incrementally)
python scripts/evaluate_generation.py --limit 8 --cache /tmp/gen_cache.json   # smoke test
python scripts/evaluate_generation.py --cache /tmp/gen_cache.json             # full 198 items
python scripts/evaluate_generation.py --split holdout --cache ...             # holdout only
# Reports Faithfulness / Answer Relevancy / Citation Accuracy / citation coverage / JSON parse-failure rate
```

**Current results (retrieval deterministic & offline; generation on real DeepSeek-v4-flash)**:
- Retrieval: Multi-relevant Recall@7 **0.745**; out-of-KB rejection **22/22**, self-bio injection 0/22; single-relevant hit@1 0.897 / MRR 0.933 / decision accuracy 0.986; unit tests 114/114;
- Generation (50-item stratified sample): Faithfulness **0.636** (non-negative **0.723**) / Answer Relevancy 0.604 / Citation Accuracy 0.735 / citation coverage 0.880;
- e2e live structured citation: 【参考史料】citations **18/20 (90%)**, 0 out-of-range dropped, routing 20/20.

Full metrics, methodology and optimization details:
[RAG_EVALUATION_REPORT_FINAL.md](RAG_EVALUATION_REPORT_FINAL.md).

### 📄 Multi-format Document Parsing

The knowledge base no longer accepts only `*.txt`: `src/retrievers/document_loader.py` parses
**txt / md / html / pdf / docx / xml / json / csv / tsv / xlsx** uniformly into `Document`
(front-matter `【来源】【URL】【人物】【分类】` plus source annotations `【朝代】【出处】【篇卷】` +
`---` body separator, character inferred from filename, alias completion, automatic `doc_type`
persona/historical detection, dynasty backfilled from the character profile — same semantics as the
legacy txt path). Scanned PDFs (no text layer) and unknown extensions are skipped (no OCR). Ingesting
new knowledge:

```bash
# Incremental: only add new docs (dedup by file metadata, idempotent)
python scripts/ingest_documents.py --src data/documents_sample
# Full rebuild (clear, then rebuild from data/knowledge in all formats)
python scripts/ingest_documents.py --src data/knowledge --mode rebuild
```

Sample corpus in `data/documents_sample/` (md / html / json / csv, out-of-KB figure "张衡").

## ✅ Verifiable Citations（Hardened grounding）

When sources are retrieved, the model is required to output structured JSON `{"reply": ..., "cited_sources": [indices]}`.
The code validates that each index falls within the current retrieval set before rendering it as 【参考史料】;
out-of-range citations are dropped. On parse failure it falls back to plain text without blocking the conversation.
Citations pointing to nonexistent sources therefore never reach rendering or the database
(see `_parse_structured_reply` / `_validate_cited` in `src/agents/history_agent.py`).

## ⚠️ Deployment Notes

- **No authentication by default** — for personal / intranet demos only. For public deployment, add your own auth and keep `enableXsrfProtection` enabled.
- Cold start loads local embeddings (downloaded on first run, then cached locally).
- After changing the embedding model, delete `data/vector_db` and rebuild with `scripts/build_vector_db.py`.
- Conversations can be purged by retention days with `scripts/cleanup_db.py` (recommend scheduling via cron).

## 📄 License

MIT © 2024 Dreamlee0
