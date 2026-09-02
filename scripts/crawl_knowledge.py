"""
历史数据源抓取：真实史源（古诗文网 古籍原文 + 中文维基百科）→ 知识库。

数据源选择（聚焦 97 人不抓全量《二十四史》）：
  - 人物 → 典籍篇/卷 的映射见 data/sources/character_sources.json（每人 1-3 条
    候选古籍章 + 维基条目名）；
  - 古诗文网（gushiwen.cn，默认古籍原文源）：公版二十四史原文，ctext.org 被
    封锁时的替代源。书页→章节 GUID 由 data/sources/gushiwen_books.json 缓存，
    (book, chapter) → 章节 URL 由 data/sources/gushiwen_resolution.json 解析
    （脚本生成，含合传/合卷/方伎/后妃等复合映射），未覆盖条目跳过（persona 兜底）；
  - ctext.org（中国哲学书电子化计划）：仅 --sources ctext 显式启用（开发环境
    403 封锁，网络策略放开后可用）；
  - 中文维基百科：覆盖宋元明清/民国，条目自带参考资料标注（部分网络不通）；
  - 百度百科：仅 --include-baidu 时作为兜底通道（保留历史逻辑）。

输出：biography_<人物>_<来源>_<书>.txt（不带 `_内置` 后缀 → doc_type=historical，
见 src/retrievers/document_loader._infer_doc_type），front-matter 含
【朝代】【出处】《书》【篇卷】/【URL】；persona（内置摘要）由抓取器不碰。

离线约束：--dry-run 只打印抓取计划（不联网）；在线抓取时某源不可达（403/超时）
会跳过并告警，不伪造产出。抓取器以 HTTP 200 + 正文长度双重校验。

用法：
  python scripts/crawl_knowledge.py --dry-run                     # 打印 97 人抓取计划
  python scripts/crawl_knowledge.py --dry-run --characters 李白,孔子   # 只打印指定人
  python scripts/crawl_knowledge.py --sources gushiwen            # 只抓古诗文网古籍原文
  python scripts/crawl_knowledge.py --sources all                 # 默认：古诗文网 + 维基
  python scripts/crawl_knowledge.py --sources ctext --characters 诸葛亮   # 显式走 ctext
"""
import os
import re
import sys
import time
import json
import random
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document

SOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "sources" / "character_sources.json"
GUSHIWEN_BOOKS_FILE = Path(__file__).resolve().parent.parent / "data" / "sources" / "gushiwen_books.json"
GUSHIWEN_RESOLUTION_FILE = Path(__file__).resolve().parent.parent / "data" / "sources" / "gushiwen_resolution.json"
WIKI_API = "https://zh.wikipedia.org/w/api.php"


@dataclass
class CrawlResult:
    """抓取结果"""
    title: str
    content: str
    source: str
    url: str
    character: str
    category: str
    dynasty: str = ""
    book: str = ""          # 出处（《史记》等，不带书名号，与映射表 book 一致）
    chapter: str = ""       # 篇/卷（孔子世家）
    doc_type: str = "historical"
    baihua: str = ""        # 白话导读（取自人物 persona 摘要前两句，嵌入时的现代语锚点）


class _HttpMixin:
    """请求基础设施：多 UA / 重试 / 随机延迟 / crawl_cache.json 去重。"""

    def __init__(self, output_dir: str = "./data/knowledge", cache_file: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })
        # 去重缓存默认放 data/sources/（而非知识目录）：crawl_cache.json 是爬虫状态，
        # 若留在 data/knowledge/ 会被多格式加载器当 .json 知识文档误摄入。
        # cache_file 可注入：测试传 tmp_path 隔离，避免污染/依赖共享缓存。
        self.cache_file = (
            Path(cache_file) if cache_file
            else GUSHIWEN_RESOLUTION_FILE.parent / "crawl_cache.json"
        )
        self.crawled_urls = self._load_cache()

    def _load_cache(self) -> Dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.crawled_urls, f, ensure_ascii=False, indent=2)

    def _random_delay(self):
        time.sleep(random.uniform(2, 4))

    def get(self, url: str, timeout: int = 20, retries: int = 3) -> Optional[requests.Response]:
        """带 UA 轮换与重试的 GET；403 等失败重试，最终返回 None 或响应。"""
        for attempt in range(retries):
            try:
                self.session.headers["User-Agent"] = random.choice(self.user_agents)
                resp = self.session.get(url, timeout=timeout, allow_redirects=True)
                if resp.status_code == 403:
                    print(f"    [403] 被拦截，等待后重试...")
                    time.sleep(5)
                    continue
                if resp.status_code != 200:
                    continue
                return resp
            except Exception as e:
                print(f"    [错误] 尝试 {attempt + 1}/{retries}: {e}")
                time.sleep(3)
        return None

    # 移动端 UA：wapbaike 移动版页面反爬更宽松，桌面端 403 时的可靠回退通道
    MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                 "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                 "Mobile/15E148 Safari/604.1")

    def _baidu_get(self, url: str, timeout: int = 30, mobile: bool = False, retries: int = 4):
        """百度百科抓取专用 GET。

        实测：requests 的 TLS 指纹被百度 WAF 一律拦截（403）；curl_cffi 间歇被拦；
        **系统 curl 的 TLS 指纹稳定放行**（桌面端 302→200，移动端 wapbaike 200）。
        因此以 subprocess curl 为主通道（-L 跟随重定向）。
        返回带 content/text 的轻量响应对象，语义与 requests.Response 一致。
        """
        class _Resp:
            def __init__(self, content: bytes, status: int):
                self.content = content
                self.status_code = status

            @property
            def text(self):
                return self.content.decode("utf-8", errors="replace")

        ua = self.MOBILE_UA if mobile else random.choice(self.user_agents)
        for attempt in range(retries):
            try:
                cp = subprocess.run(
                    ["curl", "-s", "-L", "-A", ua,
                     "--max-time", str(timeout),
                     "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
                     "-H", "Referer: https://baike.baidu.com/",
                     "-w", "\n%{http_code}", url],
                    capture_output=True, text=True, timeout=timeout + 10)
                out = cp.stdout
                body, _, code = out.rpartition("\n")
                code = code.strip()
                if code == "200":
                    return _Resp(body.encode("utf-8"), 200)
                if cp.returncode != 0 or not code:
                    raise RuntimeError(f"curl 退出码 {cp.returncode}: {cp.stderr.strip()[:120]}")
                print(f"    [百度 {code}] 等待后重试（{attempt + 1}/4）...")
                time.sleep(5 + attempt * 4)
            except Exception as e:
                print(f"    [百度错误] 尝试 {attempt + 1}/4: {e}")
                time.sleep(5)
        return None


class CtextFetcher(_HttpMixin):
    """ctext.org 古籍原文抓取：剥离校注/疏注释后取原文段落。"""

    def fetch(self, url: str, character: str, book: str, chapter: str, dynasty: str) -> Optional[CrawlResult]:
        if url in self.crawled_urls:
            return None
        resp = self.get(url)
        if resp is None:
            print(f"    [失败] 无法访问 {url}（slug 可能需网络校验）")
            return None
        content = self._extract(resp.text)
        if len(content) < 30:
            print(f"    [失败] 原文过短({len(content)}字)或解析结构变化: {url}")
            return None
        self.crawled_urls[url] = {"time": time.strftime("%Y-%m-%d")}
        self._save_cache()
        return CrawlResult(
            title=f"{character}（{book}·{chapter}节选）",
            content=content[:4000],
            source="ctext.org（中国哲学书电子化计划）",
            url=url,
            character=character,
            category="biography",
            dynasty=dynasty,
            book=book,
            chapter=chapter,
            doc_type="historical",
        )

    def _extract(self, html: str) -> str:
        """从 ctext 章节页提取原文正文，剥离 sup/校注/疏 等旁注。

        ctext 原文容器为 div.ctext / div.ctext1 等；逐块去注释后拼接段落。
        选择器为按 ctext 现行页面的最佳努力推断——网络恢复后若解析为空，
        以真实 HTML 调整 _extract 即可（失败会打印"原文过短"告警，不静默丢）。
        """
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all(["sup", "script", "style"]):
            tag.decompose()
        # 校注/疏 标注：ctext 以 class~=annot / 含"注""疏"的 span 呈现
        for tag in soup.find_all("span", class_=lambda c: c and any(
                k in c for k in ("annot", "note", "comment"))):
            tag.decompose()

        blocks = soup.select(".ctext, .ctext1, .ctext2, #content5")
        paras = []
        for blk in blocks:
            text = blk.get_text(" ", strip=True)
            if text:
                # ctext 句间以 · 分隔：转成换行便于阅读与后续切分
                paras.append(text.replace("·", "\n"))
        if not paras:
            # 兜底：抓正文主容器文本
            main = soup.find("div", id="content5") or soup.find("div", class_="content")
            if main:
                paras.append(main.get_text(" ", strip=True))
        return "\n".join(paras)


class GushiwenFetcher(_HttpMixin):
    """古诗文网（gushiwen.cn）古籍原文抓取：ctext 被封锁时的公版原文替代源。

    页面结构（已实测）：书页 `.../guwen/book_<GUID>.aspx` 列出章节链接
    `.../guwen/bookv_<GUID>.aspx`，章节页原文正文在 `div.contson`（不含导航/译文）。
    (book, chapter) → 章节 URL 的解析表 data/sources/gushiwen_resolution.json
    由发现脚本生成（覆盖合传/合卷/方伎/后妃等复合命名），未覆盖条目跳过、由
    persona 兜底——绝不伪造内容。晋书等 gushiwen 无有效卷名的书解析不到，跳过。
    """

    def __init__(self, output_dir: str = "./data/knowledge", cache_file: Optional[str] = None):
        super().__init__(output_dir, cache_file=cache_file)
        self.resolution: Dict = {}
        if GUSHIWEN_RESOLUTION_FILE.exists():
            self.resolution = json.loads(
                GUSHIWEN_RESOLUTION_FILE.read_text(encoding="utf-8")
            )

    def resolve(self, book: str, chapter: str) -> Optional[str]:
        """(书, 篇) → gushiwen 章节 URL；解析表缺失返回 None。"""
        entry = self.resolution.get(f"{book}|{chapter}")
        return entry.get("url") if entry else None

    def fetch(self, book: str, chapter: str, character: str, dynasty: str) -> Optional[CrawlResult]:
        url = self.resolve(book, chapter)
        if not url:
            print(f"    [跳过] gushiwen 无 {book}·{chapter}（晋书等未收录，persona 兜底）")
            return None
        if url in self.crawled_urls:
            return None
        resp = self.get(url)
        if resp is None:
            print(f"    [失败] 无法访问 {url}")
            return None
        content = self._extract(resp.text)
        if len(content) < 30:
            print(f"    [失败] 原文过短({len(content)}字)或页面结构变化: {url}")
            return None
        self.crawled_urls[url] = {"time": time.strftime("%Y-%m-%d")}
        self._save_cache()
        return CrawlResult(
            title=f"{character}（{book}·{chapter}节选）",
            content=content[:4000],
            source="古诗文网（gushiwen.cn）",
            url=url,
            character=character,
            category="biography",
            dynasty=dynasty,
            book=book,
            chapter=chapter,
            doc_type="historical",
            baihua=self._persona_gloss(character),
        )

    def _persona_gloss(self, character: str) -> str:
        """从同人物 persona 摘要（biography_<人物>_内置.txt）取前两句作白话导读。

        古籍原文用词与今语有代差（如"通济渠"vs"大运河"），嵌入时若无现代语
        锚点，问今语会命中他书相近文段（如清史稿·漕运）。导读仅作检索锚点，
        标注"白话导读"非原文，正文仍是权威古籍原文（doc_type=historical）。
        """
        p = self.output_dir / f"biography_{character}_内置.txt"
        if not p.exists():
            return ""
        txt = p.read_text(encoding="utf-8")
        body = txt.split("---", 1)[1] if "---" in txt else txt
        body = re.sub(r"^#.*$", "", body, flags=re.M).strip()
        sents = [s for s in re.split(r"(?<=[。！？])", body) if s.strip()]
        # 合并为单行（front-matter 按行解析，内部换行会导致句号后内容丢失）
        gloss = re.sub(r"\s+", "", "".join(sents[:2]))
        return gloss[:80]

    def _extract(self, html: str) -> str:
        """章节页正文：div.contson 即干净原文容器（已实测）。"""
        soup = BeautifulSoup(html, "lxml")
        node = soup.select_one("div.contson")
        if node is None:
            return ""
        for tag in node.find_all(["sup", "script", "style"]):
            tag.decompose()
        text = node.get_text("\n", strip=True)
        # 防御：若容器混入 译文/注释/赏析 等附加区，只保留其前原文
        head = re.split(r"(译文|注释|赏析|参考资料)", text)[0]
        return head.strip()


class WikipediaFetcher(_HttpMixin):
    """中文维基百科抓取：extracts API 取条目引言/全文（二次文献，source=维基百科）。"""

    def fetch(self, title: str, character: str) -> Optional[CrawlResult]:
        url = f"{WIKI_API}?action=query&prop=extracts&explaintext=1&format=json&redirects=1&titles={title}"
        cache_key = f"wiki:{title}"
        if cache_key in self.crawled_urls:
            return None
        resp = self.get(url)
        if resp is None:
            print(f"    [失败] 维基条目不可达: {title}")
            return None
        try:
            pages = resp.json()["query"]["pages"]
            page = next(iter(pages.values()))
            extract = (page.get("extract") or "").strip()
        except Exception as e:
            print(f"    [失败] 维基解析异常 {title}: {e}")
            return None
        if len(extract) < 50:
            print(f"    [失败] 维基条目过短或不存在: {title}")
            return None
        self.crawled_urls[cache_key] = {"time": time.strftime("%Y-%m-%d")}
        self._save_cache()
        return CrawlResult(
            title=title,
            content=f"（中文维基百科条目，属二次文献，非古籍原文；正文为 API extracts）\n{extract[:4000]}",
            source="维基百科（zh.wikipedia.org）",
            url=f"https://zh.wikipedia.org/wiki/{title.replace(' ', '_')}",
            character=character,
            category="biography",
            dynasty="",
            book="",
            chapter="",
            doc_type="historical",
        )


class HistoryDataCrawler(_HttpMixin):
    """（保留）百度百科抓取：仅 --include-baidu 时使用，作为兜底通道。"""

    def crawl_baidu_baike(self, name: str, category: str = "biography") -> Optional[CrawlResult]:
        """百度百科抓取：桌面版优先，被 WAF 限流（403）时回退移动版 wapbaike。

        实测：桌面版 `item/{name}` 在持续抓取后会被按 IP 限流（连 curl 也 403）；
        wapbaike 移动版反爬宽松，稳定 200，是可靠回退通道。两版页面结构不同，
        各配独立解析器（_parse_baike_desktop / _parse_baike_wap）。
        """
        url = f"https://baike.baidu.com/item/{name}"
        if url in self.crawled_urls:
            return None
        # 桌面版限流时 403 快速失败（1 次尝试），立即回退 wap 移动版
        resp = self._baidu_get(url, retries=1)
        parsed = self._parse_baike_desktop(resp, name) if resp is not None else None
        if parsed is None:
            wap_url = f"https://wapbaike.baidu.com/item/{name}"
            wap_resp = self._baidu_get(wap_url, mobile=True, retries=4)
            parsed = self._parse_baike_wap(wap_resp, name) if wap_resp is not None else None
        if parsed is None:
            return None
        content, title = parsed
        self.crawled_urls[url] = {"title": title, "time": time.strftime("%Y-%m-%d")}
        self._save_cache()
        return CrawlResult(
            title=title, content=content[:5000], source="百度百科", url=url,
            character=name, category=category, doc_type="historical",
        )

    def _parse_baike_desktop(self, resp, name):
        """桌面版：正文容器 div.J-lemma-content（旧 main-content/lemma-summary 已失效）。
        返回 (content, title) 或 None。"""
        if resp is None:
            return None
        soup = BeautifulSoup(resp.content, "lxml")
        title_elem = soup.find("h1") or soup.find("dd", class_="lemmaWgt-lemmaTitle-title")
        title = title_elem.get_text(strip=True) if title_elem else name
        content_div = (soup.select_one("div.J-lemma-content")
                       or soup.find("div", class_="main-content")
                       or soup.find("div", class_="lemma-summary"))
        if not content_div:
            return None
        # 注意：百度百科把专名（人名/地名/书名）包在 <a> 链接里，链接即内容，
        # 不能像 ctext/gushiwen 那样 decompose("a")（否则专名被删、正文残缺）。
        for tag in content_div.find_all(
                ["script", "style", "sup", "svg", "path", "button", "i", "img"]):
            tag.decompose()
        # 按 h2/h3 小节标题分块取正文（扁平 span 文本 + 分节标题结构），
        # 连续重复块（图片说明重复渲染）去重
        sections, cur_buf = [], []
        for el in content_div.find_all(["h2", "h3", "div", "p"]):
            if el.name in ("h2", "h3"):
                t = "".join(cur_buf)
                if len(re.sub(r"\s+", "", t)) >= 20:
                    sections.append(re.sub(r"\s+", "", t))
                cur_buf = []
            else:
                t = el.get_text(strip=True)
                if t and len(t) > 10:
                    cur_buf.append(t)
        t = "".join(cur_buf)
        if len(re.sub(r"\s+", "", t)) >= 20:
            sections.append(re.sub(r"\s+", "", t))
        deduped = []
        for blk in sections:
            if not deduped or deduped[-1] != blk:
                deduped.append(blk)
        content = "\n".join(deduped)
        if len(content) < 50:
            return None
        return content, title

    def _parse_baike_wap(self, resp, name):
        """移动版 wapbaike：取整个 index_pageContent 包裹文本（类名后缀随机，
        按前缀 index_pageContent__/index_pageWrapper__ 匹配），剥离图册/参考资料/
        讨论等旁枝与页脚噪声。返回 (content, title) 或 None。"""
        if resp is None:
            return None
        soup = BeautifulSoup(resp.content, "lxml")
        title_elem = soup.find("title")
        title = name
        if title_elem:
            t = title_elem.get_text(strip=True)
            title = re.sub(r"_百度百科.*$", "", t) if "_百度百科" in t else t
        for d in soup.find_all("div", class_=lambda c: c and any(
                k in " ".join(c) for k in ("index_reference", "lemmaAlbum",
                                           "Discussion", "discussion", "toggleFoldBtn",
                                           "index_lemmaTitle", "index_pro"))):
            d.decompose()
        main = (soup.select_one("div[class*=index_pageContent__]")
                or soup.select_one("div[class*=index_pageWrapper__]"))
        if not main:
            return None
        for tag in main.find_all(["script", "style", "sup", "svg", "path", "button", "i"]):
            tag.decompose()
        content = re.sub(r"\s+", "", main.get_text())
        for noise in ("搜词条", "其他20个同名词条", "词条图册", "概述图册",
                      "展开", "收起", "目录", "纠错", "分享编辑", "百度百科是免费编辑平台"):
            content = content.replace(noise, "")
        content = re.sub(r"(讨论|共\d+篇|词条贡献者.*$)", "", content)
        if len(content) < 50:
            return None
        return content, title


def _source_tag(source: str) -> str:
    """来源 → 输出文件名中的来源标签（前缀匹配，勿用切片等值）。"""
    if source.startswith("ctext.org"):
        return "ctext"
    if "古诗文网" in source:
        return "gushiwen"
    if "维基百科" in source:
        return "维基百科"
    if "百度百科" in source:
        return "百度百科"
    return "src"


def save_result(result: CrawlResult, output_dir: Path) -> str:
    """把抓取结果写成知识文件（不带 _内置 → doc_type=historical）。

    文件名：biography_<人物>_<来源标签>[_<书>].txt；front-matter 含朝代/出处/篇卷。
    """
    tag = _source_tag(result.source)
    book = result.book or ""
    suffix = f"_{book}" if book else ""
    filename = f"biography_{result.character}_{tag}{suffix}.txt"
    # 同名不同篇（同一人物同一书多章，如 唐太宗·旧唐书·太宗本纪/魏徵传）：
    # 已有同名文件且篇卷不同 → 追加篇卷消歧，避免后者覆盖前者
    fp = Path(output_dir) / filename
    if fp.exists() and result.chapter:
        existing = fp.read_text(encoding="utf-8")[:600]
        m = re.search(r"【篇卷】(.+)", existing)
        if not m or m.group(1).strip() != result.chapter:
            filename = re.sub(r"\.txt$", f"_{result.chapter}.txt", filename)
    filename = re.sub(r'[\\/:*?"<>|]', "_", filename)

    lines = [
        f"# {result.title}",
        f"【来源】{result.source}",
        f"【URL】{result.url}",
        "【分类】biography",
        f"【人物】{result.character}",
    ]
    if getattr(result, "baihua", ""):
        lines.append(f"【白话】{result.baihua}")
    if result.dynasty:
        lines.append(f"【朝代】{result.dynasty}")
    if result.book:
        lines.append(f"【出处】《{result.book}》")
    if result.chapter:
        lines.append(f"【篇卷】{result.chapter}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(result.content)
    lines.append("")

    filepath = output_dir / filename
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


def load_character_sources() -> Dict:
    if not SOURCES_FILE.exists():
        raise SystemExit(f"缺少数据源映射表: {SOURCES_FILE}（运行生成脚本或先建表）")
    return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))


def fetch_sources(
    sources: List[str],
    characters: Optional[List[str]] = None,
    dry_run: bool = False,
    include_baidu: bool = False,
    output_dir: str = "./data/knowledge",
):
    """按映射表抓取指定人物的数据源。dry_run 只打印计划，不联网。"""
    if "all" in sources:
        # 默认源：古诗文网古籍原文（ctext 封锁时的替代）+ 维基（补宋元明清/民国）
        sources = ["gushiwen", "wiki"]
    mapping = load_character_sources()
    names = characters or list(mapping.keys())
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ctext = CtextFetcher(output_dir)
    gushiwen = GushiwenFetcher(output_dir)
    wiki = WikipediaFetcher(output_dir)
    baidu = HistoryDataCrawler(output_dir) if include_baidu else None

    print(f"== 数据源抓取 | sources={','.join(sources)} | {len(names)} 人 | "
          f"dry_run={dry_run} | include_baidu={include_baidu} ==")
    n_plan = 0
    for i, name in enumerate(names, 1):
        entry = mapping.get(name)
        if not entry:
            print(f"  [{i}/{len(names)}] {name}: 映射表缺失，跳过")
            continue
        print(f"  [{i}/{len(names)}] {name} ({entry['dynasty']})")
        if "gushiwen" in sources:
            for b in entry["books"]:
                n_plan += 1
                gw_url = gushiwen.resolve(b["book"], b["chapter"])
                print(f"    [gushiwen] {b['book']}·{b['chapter']}  {gw_url or '(未解析，persona 兜底)'}"
                      + ("" if dry_run else ""))
                if not dry_run:
                    r = gushiwen.fetch(b["book"], b["chapter"], name, entry["dynasty"])
                    if r:
                        fp = save_result(r, out)
                        print(f"      ✓ {len(r.content)} 字 → {Path(fp).name}")
                    else:
                        print(f"      ✗ 跳过（解析缺失或抓取失败，persona 兜底）")
                    gushiwen._random_delay()
        if "ctext" in sources:
            for b in entry["books"]:
                n_plan += 1
                print(f"    [ctext] {b['book']}·{b['chapter']}  {b['ctext']}"
                      + ("" if dry_run else ""))
                if not dry_run:
                    r = ctext.fetch(b["ctext"], name, b["book"], b["chapter"], entry["dynasty"])
                    if r:
                        fp = save_result(r, out)
                        print(f"      ✓ {len(r.content)} 字 → {Path(fp).name}")
                    else:
                        print(f"      ✗ 抓取失败（跳过）")
                    ctext._random_delay()
        if "wiki" in sources:
            title = entry.get("wikipedia") or name
            n_plan += 1
            print(f"    [维基] {title}  https://zh.wikipedia.org/wiki/{title}"
                  + ("" if dry_run else ""))
            if not dry_run:
                r = wiki.fetch(title, name)
                if r:
                    fp = save_result(r, out)
                    print(f"      ✓ {len(r.content)} 字 → {Path(fp).name}")
                else:
                    print(f"      ✗ 维基条目不可达")
                wiki._random_delay()
        if include_baidu and baidu is not None:
            n_plan += 1
            print(f"    [百度] {name}  https://baike.baidu.com/item/{name}")
            if not dry_run:
                r = baidu.crawl_baidu_baike(name)
                if r:
                    fp = save_result(r, out)
                    print(f"      ✓ {len(r.content)} 字 → {Path(fp).name}")
                baidu._random_delay()

    if dry_run:
        print(f"\n== 抓取计划（dry-run，未联网）：{n_plan} 个抓取任务 ==")
        print("== 网络恢复后，去掉 --dry-run 运行同一条命令即全量抓取 ==")
    else:
        print(f"\n== 抓取完成：{n_plan} 个任务执行完毕 ==")


def main():
    ap = argparse.ArgumentParser(description="历史数据源抓取（ctext 古籍原文 + 中文维基）")
    ap.add_argument("--sources", choices=["ctext", "wiki", "gushiwen", "all"], default="all",
                    help="抓取哪些数据源（默认 all=gushiwen+wiki；ctext 被封时用 gushiwen 古籍原文）")
    ap.add_argument("--characters", default="",
                    help="只抓指定人物，逗号分隔（默认全部 97 人）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印抓取计划（URL 清单），不联网")
    ap.add_argument("--include-baidu", action="store_true",
                    help="额外启用百度百科兜底通道（默认不启用）")
    ap.add_argument("--out", default="./data/knowledge", help="输出目录")
    args = ap.parse_args()

    chars = [c.strip() for c in args.characters.split(",") if c.strip()] or None
    # 注意：不在这里把 all 展开成具体源——"all 默认抓哪些源"的唯一权威定义在
    # fetch_sources（gushiwen+wiki，ctext 封锁时的替代源）。若此处按旧逻辑展开成
    # ctext+wiki，会与文档/--help 的"all=gushiwen+wiki"相悖且跳过默认源。
    sources = [args.sources]
    fetch_sources(
        sources=sources, characters=chars, dry_run=args.dry_run,
        include_baidu=args.include_baidu, output_dir=args.out,
    )


if __name__ == "__main__":
    main()
