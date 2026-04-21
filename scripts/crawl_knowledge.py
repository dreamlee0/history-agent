"""
历史资料爬虫 - 爬取历史人物资料构建知识库
使用更完善的请求头和重试机制
"""
import os
import sys
import time
import json
import re
import random
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document


@dataclass
class CrawlResult:
    """爬取结果"""
    title: str
    content: str
    source: str
    url: str
    character: str
    category: str


class HistoryDataCrawler:
    """历史数据爬虫"""

    def __init__(self, output_dir: str = "./data/knowledge"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 多个User-Agent
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]

        self.session = requests.Session()
        self._set_headers()

        self.cache_file = self.output_dir / "crawl_cache.json"
        self.crawled_urls = self._load_cache()

    def _set_headers(self):
        """设置请求头"""
        self.session.headers.update({
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

    def _load_cache(self) -> Dict:
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.crawled_urls, f, ensure_ascii=False, indent=2)

    def _random_delay(self):
        """随机延迟"""
        time.sleep(random.uniform(2, 4))

    def crawl_baidu_baike(self, name: str, category: str = "biography") -> Optional[CrawlResult]:
        """爬取百度百科"""
        url = f"https://baike.baidu.com/item/{name}"

        if url in self.crawled_urls:
            return None

        for attempt in range(3):
            try:
                # 每次请求更换User-Agent
                self.session.headers["User-Agent"] = random.choice(self.user_agents)

                resp = self.session.get(url, timeout=20, allow_redirects=True)

                if resp.status_code == 403:
                    print(f"    [403] 被拦截，等待后重试...")
                    time.sleep(5)
                    continue

                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.content, "lxml")

                # 获取标题
                title_elem = soup.find("h1") or soup.find("dd", class_="lemmaWgt-lemmaTitle-title")
                title = title_elem.get_text(strip=True) if title_elem else name

                # 获取正文
                content_div = soup.find("div", class_="main-content")
                if not content_div:
                    content_div = soup.find("div", class_="lemma-summary")
                if not content_div:
                    content_div = soup.find("div", class_="para")

                if not content_div:
                    return None

                # 清理
                for tag in content_div.find_all(["script", "style", "sup", "a"]):
                    tag.decompose()

                paragraphs = content_div.find_all("p")
                if not paragraphs:
                    paragraphs = [content_div]

                content = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

                if len(content) < 50:
                    return None

                self.crawled_urls[url] = {"title": title, "time": time.strftime("%Y-%m-%d")}
                self._save_cache()

                return CrawlResult(
                    title=title,
                    content=content[:5000],
                    source="百度百科",
                    url=url,
                    character=name,
                    category=category
                )

            except Exception as e:
                print(f"    [错误] 尝试 {attempt+1}/3: {e}")
                time.sleep(3)

        return None

    def save_result(self, result: CrawlResult) -> str:
        """保存结果"""
        filename = f"{result.category}_{result.character}_{result.source}.txt"
        filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        filepath = self.output_dir / filename

        content = f"""# {result.title}

【来源】{result.source}
【URL】{result.url}
【分类】{result.category}
【人物】{result.character}

---

{result.content}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return str(filepath)

    def to_document(self, result: CrawlResult) -> Document:
        return Document(
            page_content=result.content,
            metadata={
                "title": result.title,
                "source": result.source,
                "url": result.url,
                "character": result.character,
                "category": result.category
            }
        )


def crawl_all_characters():
    """爬取所有历史人物资料"""
    from src.characters import character_manager

    crawler = HistoryDataCrawler()
    documents = []

    characters = character_manager.get_all_characters()
    total = len(characters)
    success = 0

    print(f"开始爬取 {total} 位历史人物资料...\n")

    for i, char in enumerate(characters, 1):
        print(f"[{i}/{total}] {char.name} ({char.dynasty})")

        result = crawler.crawl_baidu_baike(char.name)
        if result:
            filepath = crawler.save_result(result)
            documents.append(crawler.to_document(result))
            print(f"  ✓ 成功: {len(result.content)} 字")
            success += 1
        else:
            print(f"  ✗ 失败")

        crawler._random_delay()

        # 每10个保存缓存
        if i % 10 == 0:
            crawler._save_cache()
            print(f"  --- 进度: {success}/{i} 成功 ---")

    crawler._save_cache()

    print(f"\n爬取完成！成功: {success}/{total}")
    return documents


def main():
    print("=" * 60)
    print("历史知识库数据爬取")
    print("=" * 60)

    docs = crawl_all_characters()

    print(f"\n共获取 {len(docs)} 篇文档")
    print(f"知识库目录: ./data/knowledge")


if __name__ == "__main__":
    main()
