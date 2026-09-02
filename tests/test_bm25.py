"""BM25 词法索引测试（纯逻辑，不依赖 embedding / 向量库）"""
from langchain_core.documents import Document

from src.retrievers.bm25 import BM25Index


def _docs():
    return [
        Document(page_content="徐霞客，名弘祖，明代地理学家、旅行家。", metadata={"character": "徐霞客"}),
        Document(page_content="徐霞客游历天下，著《徐霞客游记》。", metadata={"character": "徐霞客"}),
        Document(page_content="李白是唐代伟大的浪漫主义诗人，诗歌想象瑰丽。", metadata={"character": "李白"}),
        Document(page_content="杜甫与李白齐名，被称为诗圣。", metadata={"character": "杜甫"}),
        Document(page_content="张衡造候风地动仪，能测知地震方位。", metadata={"character": "张衡"}),
    ]


def test_build_and_search_recall():
    """精确词命中：查询词在文档中真实出现时应排在前面"""
    idx = BM25Index().build(_docs())
    res = idx.search("徐霞客游记", k=3)
    assert res, "不应为空"
    assert res[0][0].metadata["character"] == "徐霞客"
    assert res[0][1] > 0


def test_filter_char_restricts_docs():
    """filter_char 只在该人物 chunk 内排序"""
    idx = BM25Index().build(_docs())
    res = idx.search("诗歌", k=5, filter_char="李白")
    assert res
    for d, _s in res:
        assert d.metadata["character"] == "李白"


def test_filter_char_with_no_match():
    """filter_char 下无该人物文档 → 返回空列表（非崩溃）"""
    idx = BM25Index().build(_docs())
    assert idx.search("李白", k=5, filter_char="苏轼") == []


def test_filter_chars_multi_person_mask():
    """filter_chars（$in 联合检索）只在名单内人物 chunk 中排序，且覆盖两名人选"""
    idx = BM25Index().build(_docs())
    # "诗人" 命中李白文档、"诗圣" 命中杜甫文档，联合池应两名人选都覆盖
    res = idx.search("诗人 诗圣", k=5, filter_chars=["李白", "杜甫"])
    chars = [d.metadata["character"] for d, _s in res]
    assert chars, "联合池不应为空"
    assert set(chars) <= {"李白", "杜甫"}, f"越界人物混入: {chars}"
    assert {"李白", "杜甫"} <= set(chars), f"名单内人物未被覆盖: {chars}"


def test_filter_chars_union_never_crosses_roster():
    """多人物掩码与单人物掩码语义一致：名单外人物（张衡）绝不返回"""
    idx = BM25Index().build(_docs())
    res = idx.search("诗人", k=5, filter_chars=["李白", "杜甫"])
    assert all(d.metadata["character"] != "张衡" for d, _s in res)


def test_no_match_query_returns_empty():
    """查询词不在语料词表 → 无命中（得分为 0 不返回）"""
    idx = BM25Index().build(_docs())
    res = idx.search("量子力学熵增", k=5)
    assert res == []


def test_empty_index_and_query_safe():
    """空索引 / 空查询不崩溃"""
    assert BM25Index().build([]).search("李白") == []
    idx = BM25Index().build(_docs())
    assert idx.search("", k=5) == []


def test_scores_monotonic_by_relevance():
    """相关度更高（词频更高）的文档得分更高"""
    idx = BM25Index().build(_docs())
    a = idx.search("徐霞客 徐霞客", k=5)[0]
    b = idx.search("徐霞客", k=5)[0]
    assert a[1] >= b[1]
