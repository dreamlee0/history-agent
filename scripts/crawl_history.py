"""
爬取历史人物资料脚本
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bs4 import BeautifulSoup
from typing import List
from langchain_core.documents import Document
import time

from src.characters import character_manager


class HistoryDataCrawler:
    """历史数据爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def crawl_wikipedia(self, name: str) -> str:
        """爬取维基百科"""
        url = f"https://zh.wikipedia.org/wiki/{name}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "lxml")
                # 获取正文内容
                content_div = soup.find("div", {"class": "mw-parser-output"})
                if content_div:
                    paragraphs = content_div.find_all("p")
                    text = "\n".join([p.get_text(strip=True) for p in paragraphs])
                    return text
        except Exception as e:
            print(f"爬取维基百科失败 {name}: {e}")
        return ""

    def crawl_baike(self, name: str) -> str:
        """爬取百度百科"""
        url = f"https://baike.baidu.com/item/{name}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "lxml")
                # 获取正文内容
                content_div = soup.find("div", {"class": "main-content"})
                if content_div:
                    # 移除不需要的标签
                    for tag in content_div.find_all(["script", "style", "sup"]):
                        tag.decompose()
                    text = content_div.get_text(separator="\n", strip=True)
                    return text
        except Exception as e:
            print(f"爬取百度百科失败 {name}: {e}")
        return ""

    def crawl_character(self, name: str) -> List[Document]:
        """爬取单个历史人物资料"""
        documents = []

        # 尝试维基百科
        print(f"正在爬取 {name} 的维基百科资料...")
        wiki_text = self.crawl_wikipedia(name)
        if wiki_text:
            documents.append(Document(
                page_content=wiki_text,
                metadata={"source": f"维基百科-{name}", "character": name}
            ))

        time.sleep(1)  # 避免请求过快

        # 尝试百度百科
        print(f"正在爬取 {name} 的百度百科资料...")
        baike_text = self.crawl_baike(name)
        if baike_text:
            documents.append(Document(
                page_content=baike_text,
                metadata={"source": f"百度百科-{name}", "character": name}
            ))

        time.sleep(1)

        return documents

    def crawl_all_characters(self) -> List[Document]:
        """爬取所有历史人物资料"""
        all_documents = []
        characters = character_manager.get_all_characters()

        for char in characters:
            print(f"\n{'='*50}")
            print(f"爬取人物: {char.name} ({char.dynasty})")
            print(f"{'='*50}")

            docs = self.crawl_character(char.name)
            all_documents.extend(docs)

            print(f"获取到 {len(docs)} 篇文档")

        return all_documents


def main():
    """主函数"""
    print("开始爬取历史人物资料...")

    crawler = HistoryDataCrawler()
    documents = crawler.crawl_all_characters()

    print(f"\n爬取完成，共获取 {len(documents)} 篇文档")

    # 保存到文件
    output_dir = "./data/knowledge"
    os.makedirs(output_dir, exist_ok=True)

    for doc in documents:
        filename = f"{doc.metadata['source'].replace('/', '_')}.txt"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(doc.page_content)
        print(f"已保存: {filepath}")


if __name__ == "__main__":
    main()
