"""
法律智能助手 - RAG 检索服务
负责文档分块、向量存储和检索
使用 bge-base-zh 中文专用 Embedding + Chroma 向量库
"""

import os
import re
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


# 向量数据库存储路径
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME = "legal_knowledge"

# 使用中文专用 Embedding 模型
# 从 HuggingFace 镜像下载，对中文法律术语理解能力远强于默认模型
EMBEDDING_MODEL = "BAAI/bge-base-zh-v1.5"



def _extract_article_metadata(text: str) -> dict:
    """从条文文本中提取结构化元数据
    
    条文格式示例：
    《中华人民共和国劳动合同法》第三十八条：用人单位有下列情形之一的...
    
    提取结果：
    {"law_name": "中华人民共和国劳动合同法", "article": "第三十八条", "category": "劳动合同法"}
    """
    metadata = {"law_name": "", "article": "", "category": ""}
    
    # 提取法律名称：《...》
    law_match = re.search(r'《([^》]+)》', text)
    if law_match:
        full_name = law_match.group(1)
        metadata["law_name"] = full_name
        # 从法律名称推导分类（取核心关键词）
        if "劳动合同法" in full_name:
            metadata["category"] = "劳动合同法"
        elif "民法典" in full_name:
            metadata["category"] = "民法典"
        elif "刑法" in full_name:
            metadata["category"] = "刑法"
        else:
            metadata["category"] = full_name
    
    # 提取条款号：第X条 / 第X款 / 第X章 等
    article_match = re.search(r'第[一二三四五六七八九十百千零〇\d]+[条款项章节编]', text)
    if article_match:
        metadata["article"] = article_match.group()
    
    return metadata


def get_embedding_function():
    """获取中文 Embedding 模型
    
    使用 BAAI/bge-base-zh-v1.5 —— 目前中文 Embedding 的标杆模型
    优点：对中文法律术语、法条编号的理解能力强
    """
    # 镜像由启动命令的环境变量 HF_ENDPOINT 设置
    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    return embedding_fn


def get_client():
    """获取 Chroma 客户端"""
    return chromadb.PersistentClient(path=CHROMA_DIR)


def create_vectorstore(documents: list):
    """创建向量数据库
    
    参数：documents - 文档片段列表（字符串）
    返回：Chroma collection 实例
    """
    client = get_client()
    embedding_fn = get_embedding_function()
    
    # 获取或创建 collection
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "法律知识库"}
    )
    
    # 给每个文档生成唯一 ID，并提取元数据
    ids = [f"doc_{i}" for i in range(len(documents))]
    
    # 为每个文档提取结构化元数据（法律名称、条款号、分类）
    metadatas = []
    for doc in documents:
        meta = _extract_article_metadata(doc)
        # Chroma 要求 metadata 值必须是 str/int/float/bool
        metadatas.append({
            "law_name": meta["law_name"],
            "article": meta["article"],
            "category": meta["category"]
        })
    
    # 存入 Chroma（带元数据）
    collection.add(
        documents=documents,
        ids=ids,
        metadatas=metadatas
    )
    
    print(f"💾 向量库已保存到：{CHROMA_DIR}")
    return collection


def retrieve_documents(query: str, top_k: int = 3) -> list:
    """从向量库中检索与问题最相关的文档片段
    
    参数：
        query - 用户问题
        top_k - 返回最相关的几段（默认3段）
    返回：文档片段字符串列表
    """
    if not os.path.exists(CHROMA_DIR):
        print("⚠️ 向量库不存在，请先导入法律文档！")
        return []
    
    try:
        client = get_client()
        embedding_fn = get_embedding_function()
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn
        )
        
        # 检索最相关的片段
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        if results and results["documents"]:
            docs = results["documents"][0]
            # Chroma 返回格式：metadatas 是二维列表 [[meta1, meta2, ...]]，需要取 [0]
            raw_metas = results.get("metadatas")
            metas = raw_metas[0] if raw_metas and len(raw_metas) > 0 else [{}] * len(docs)
            # 返回带元数据的字典列表
            return [{"text": doc, "metadata": meta} for doc, meta in zip(docs, metas)]
        return []
    
    except Exception as e:
        print(f"❌ 检索失败：{e}")
        return []


def load_sample_legal_data():
    """加载法律知识库（从外部文件读取）
    
    扫描 legal_docs/ 目录下的所有 .txt 和 .md 文件，
    按双换行符分割为独立条文，导入向量库。
    
    补充法律知识：只需将新的 .txt/.md 文件放入 legal_docs/ 目录，重启服务即可自动加载。
    """
    # 法律文件目录
    legal_docs_dir = os.path.join(os.path.dirname(__file__), "..", "data", "legal_docs")
    
    if not os.path.exists(legal_docs_dir):
        print(f"⚠️ 法律文件目录不存在：{legal_docs_dir}，请创建并放入法律文件")
        return None
    
    # 扫描所有 .txt 和 .md 文件
    all_laws = []
    supported_extensions = {'.txt', '.md'}
    
    for filename in sorted(os.listdir(legal_docs_dir)):
        filepath = os.path.join(legal_docs_dir, filename)
        
        # 跳过目录和非支持文件
        if not os.path.isfile(filepath):
            continue
        ext = os.path.splitext(filename)[1].lower()
        if ext not in supported_extensions:
            continue
        
        # 读取文件内容
        with open(filepath, "r", encoding="utf-8") as f:
            file_content = f.read().strip()
        
        if not file_content:
            continue
        
        # 按双换行符分割为独立条文（每个条文之间用空行隔开）
        chunks = [chunk.strip() for chunk in file_content.split("\n\n") if chunk.strip()]
        all_laws.extend(chunks)
        print(f"  📄 {filename}：{len(chunks)} 条")
    
    if not all_laws:
        print("⚠️ legal_docs/ 目录为空，没有法律知识被加载")
        return None
    
    print(f"\n📚 法律知识库加载完成：共 {len(all_laws)} 条（来自 {legal_docs_dir}）")
    
    # 先清空旧的 collection（重建向量库）
    try:
        client = get_client()
        try:
            client.delete_collection(COLLECTION_NAME)
        except:
            pass
    except:
        pass
    
    vectorstore = create_vectorstore(all_laws)
    print(f"✓ 已导入 {len(all_laws)} 条法律知识\n")
    return vectorstore
