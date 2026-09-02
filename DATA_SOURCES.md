# 史料数据来源说明（Data Sources）

> **双轨数据源**：本项目知识库分两类文档——
> - **真实史源（`doc_type=historical`）**：古诗文网（gushiwen.cn）古籍原文节选、
>   ctext.org 古籍原文、中文维基百科等，带**朝代·书·篇卷**标注，可作为引用溯源依据；
> - **Persona（`doc_type=persona`）**：内置大模型生成摘要，仅作**语言风格参考/角色
>   设定**，**不作为事实依据**，引用时明确标注「（内置摘要·非权威史源）」。

## 目录结构

```
data/knowledge/
├── biography_<人物>_内置.txt        # 99 篇内置生成摘要（doc_type=persona）
├── event_<事件>_内置.txt            # 2 篇事件摘要（赤壁之战、官渡之战，persona）
├── biography_<人物>_gushiwen_<书>.txt # 真实史源：古诗文网古籍原文节选（historical，主源）
├── biography_<人物>_ctext_<书>.txt  # 真实史源：ctext 古籍原文节选（historical，手写样例）
├── biography_<人物>_百度百科.txt    # 真实史源：百度百科（historical，21 篇，补齐无正史章节/列传的人物）
├── biography_<人物>_维基百科.txt    # 真实史源：中文维基百科（historical，维基可达后抓取）
└── ../sources/
    ├── character_sources.json      # 97 人 → 数据源映射表（驱动抓取计划）
    ├── gushiwen_books.json         # 12 部正史章节目录缓存（抓取发现）
    ├── gushiwen_resolution.json    # 人物 → gushiwen 章节 URL 解析表（76 条，已核验）
    └── crawl_cache.json            # 爬虫去重缓存（已抓 URL 清单，放 sources/ 避免被当作 JSON 知识入库）
```

## 两类文档的判定（`doc_type`）

由 `src/retrievers/document_loader.py::_infer_doc_type` 自动判定，规则按优先级：

1. 前置头显式 `【doc_type】` → 直接采用；
2. 文件名含 `_内置` → `persona`；
3. 来源为「内置知识库」→ `persona`；
4. 否则 → `historical`（真实史源，抓取产物不带 `_内置` 后缀）。

朝代（`dynasty`）缺失时从人物配置（`data/characters/*.yaml`）自动补齐。

## 来源标注 schema（朝代·书·篇卷）

真实史源文件前置头示例（`biography_孔子_ctext_史记.txt`）：

```markdown
# 孔子（史记·孔子世家节选）
【来源】ctext.org（中国哲学书电子化计划）
【URL】https://ctext.org/shiji/kongzi-shi-jia/zh
【分类】biography
【人物】孔子
【朝代】春秋
【出处】《史记》
【篇卷】孔子世家

---                     ← 正文分隔线（上方为元数据头，下方为正文）

孔子长九尺有六寸……（节选，非全传）   ← 古籍原文正文
```

元数据键（`_finalize` 统一写入，结构文件 JSON/CSV/XLSX 亦支持）：

| 键 | 来源 | 示例 |
|---|---|---|
| `doc_type` | 自动判定 / 显式 | `historical` / `persona` |
| `dynasty` | 前置头或人物配置补齐 | `春秋` |
| `book` | 【出处】（自动去书名号） | `史记` |
| `chapter` | 【篇卷】 | `孔子世家` |
| `url` | 【URL】 | ctext 原文链接 |

检索与引用据此双轨分流（`src/agents/history_agent.py`）：
- 检索结果分区：真实史源按原序在前，persona 补位（有史源引史源、无史源才退摘要）；
- 引用标注：`[史料N] 出处: 春秋·《史记·孔子世家》 - ctext.org`；persona 标注
  「（内置摘要·非权威史源，仅风格参考）」；
- `PERSONA_FALLBACK=off`（严格模式）：persona 完全移出史实检索，仅真实史源可检索/引用
  （离线且史源未入库时检索退化为 no-RAG，属预期）。

## 数据源选择与 97 人映射表

聚焦 97 个人物、**不抓全量《二十四史》**。映射表 `data/sources/character_sources.json`
为每人指定朝代 + 1-3 条候选典籍篇/卷（ctext URL）+ 维基条目名：

- **先秦两汉**：《史记》《汉书》相应纪/传/世家；
- **三国**：《三国志》本传（含合传，如《关张马黄赵传》）；
- **隋唐**：《隋书》《旧唐书》《新唐书》相应纪/传（含方伎传，如玄奘）；
- **宋元明清**：《宋史》《元史》《明史》《清史稿》（公版）相应本纪/列传（多含
  多人同卷的合传/列传卷）；
- **无正史列传者**（关汉卿、曹雪芹、孙中山、鲁迅、蔡元培、梁启超等 6 人）：本以
  中文维基百科为主，维基不可达期间**以百度百科兜底**（2026-09 已入库）。

ctext 章节 URL 形如 `https://ctext.org/<书slug>/<章slug>/zh`（如
`https://ctext.org/shiji/kongzi-shi-jia/zh`），slug 为按 ctext 命名惯例的
**最佳努力推断**。

## 网络实测与源切换（gushiwen 回退）

2026-09 实测：**ctext.org 返回 403（反爬封锁 "Access unavailable"）、中文维基百科/
维基文库不可达**，而 **古诗文网（gushiwen.cn）可达**。据此切换古籍原文源：

- **`GushiwenFetcher`（默认）**：`data/sources/gushiwen_books.json` 缓存 12 部正史
  章节目录（史记 130 / 汉书 120 / 三国志 65 / 晋书 130 / 隋书 85 / 旧唐书 201 /
  新唐书 225 / 宋史 496 / 元史 210 / 明史 333 / 清史稿 530 / 新五代史 74 章），
  `data/sources/gushiwen_resolution.json` 为 76 个人物→章节 URL 的解析表（全书名/
  合传优先匹配 + 人工核验），章节页原文取自 `div.contson`；
- **`CtextFetcher`（显式 `--sources ctext`）**：保留，网络恢复/代理后可切换回；
- **`WikipediaFetcher`**：维基不可达时自然跳过（persona 兜底），恢复后补抓。

**资料补全（2026-09-02 五大问题整改，阶段1）**：原先 22 人 gushiwen 解析缺失 +
6 人无正史列传按设计走维基（维基不可达）→ 共 28 人仅 persona 兜底。本轮全部补齐：
- **A 类 7 人（原文已在库，重抓独立成文件）**：炎帝 / 尧 / 舜 / 周武王 / 霍去病 /
  张飞 / 赵云 —— 原文分别藏在 黄帝（五帝本纪）/ 周文王（周本纪）/ 卫青（卫将军
  骠骑列传）/ 关羽（关张马黄赵传）的 gushiwen 文件内，仅被 `crawl_cache.json` 去重
  跳过；清对应 URL 后重抓为 `biography_*_gushiwen_*.txt`；
- **B 类 15 人 + C 类 6 人 → 百度百科（21 篇）**：杜甫/白居易/王维/颜真卿/杜牧/
  李商隐/陆游/文天祥/郑和/徐霞客/纪晓岚/郑板桥/司马懿/王羲之/陶渊明 + 关汉卿/
  曹雪芹/孙中山/鲁迅/蔡元培/梁启超。百度百科为**三手资料**（非古籍原文、非正史），
  但 `doc_type=historical` 可作引用溯源；抓取时校验条目名（纪晓岚→纪昀、郑板桥→郑燮
  等重定向/歧义后缀）并抽查 front-matter 与正文非空。

**现状（2026-09-02 loader 口径实测）**：**97/97 人均有 `historical` 文件**（107 篇
historical = 79 原有 gushiwen/ctext + 21 百度百科 + 7 A 类重抓；另有 99 篇 persona）。
persona 彻底降级为纯语言风格参考。

## 抓取命令

```bash
# 离线打印 97 人抓取计划（URL 清单，不联网）
python scripts/crawl_knowledge.py --dry-run
python scripts/crawl_knowledge.py --dry-run --characters 李白,孔子,诸葛亮

# 全量抓取（默认 all=gushiwen 古籍原文 + 中文维基百科）
python scripts/crawl_knowledge.py --sources all
python scripts/crawl_knowledge.py --sources gushiwen   # 仅古诗文网原文（本环境已跑通）
python scripts/crawl_knowledge.py --sources ctext      # ctext（被封时跳过）
python scripts/crawl_knowledge.py --sources wiki       # 仅维基

# 只抓指定人物 / 额外启用百度百科兜底
python scripts/crawl_knowledge.py --characters 李白,孔子
python scripts/crawl_knowledge.py --include-baidu
```

抓取器复用同一套 Session / 多 UA 轮换 / 随机延迟（2-4s）/ `crawl_cache.json` 去重；
产出文件名 `biography_<人物>_gushiwen_<书>.txt` / `biography_<人物>_ctext_<书>.txt`
/ `biography_<人物>_维基百科.txt`（不带 `_内置` → 自动判定为 `historical`），
front-matter 写入朝代/出处/篇卷/URL。
维基条目经 `action=query&prop=extracts` API 取全文，正文声明「二次文献，非古籍原文」。

## 当前状态与诚实声明

- **99 篇内置摘要（persona）**在库：由 `scripts/generate_knowledge.py` 调用大模型生成
  的通俗化概述，仅作语言风格参考，非权威史源；
- **真实史源（gushiwen）已实际入库**：`--sources gushiwen` 全量抓取完成，产出
  `biography_<人物>_gushiwen_<书>.txt`（doc_type=historical，正文为**古诗文网古籍
  原文节选**）；另有 5 篇手写 `_ctext_` 样例（孔子/秦始皇/诸葛亮/唐太宗/李白）；
- **维基暂未入库**（本环境不可达），无正史章节/列传的人物以**百度百科 21 篇**补齐
  （2026-09-02，见上文"资料补全"）；**97/97 人均有 historical 文件**，无 persona-only
  兜底；
- 知识库重建：`python scripts/build_vector_db.py`（幂等，persona 与 historical 均入
  库，分别带 `doc_type=persona` / `historical` 元数据）。

## 对检索/生成质量的影响

- 人物覆盖面固定为 97 人，**库外人物提问**（如"钱学森""拿破仑"）经决策门 2
  （`out_of_kb_refusal`）判定后走 no-RAG 分支，不注入被问人物自传；
- persona 摘要经双轨分区排在真实史源之后，`PERSONA_FALLBACK=off` 时完全退出检索；
- 评测与效果说明详见 `RAG_EVALUATION_REPORT_FULL.md`。
