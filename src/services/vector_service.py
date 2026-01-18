import os

# --- 核心拦截：必须在所有 sentence_transformers 导入之前设置 ---
# 这要是再不灵，老大哥直接去沈阳大街跳大绳！
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path
import json

class VectorService:
    def __init__(self, db_path="data/vector_db", model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        """
        本地向量服务：集成了 Embedding 生成和 ChromaDB 存储。
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化本地 Embedding 模型
        # 由于上面设置了环境变量，这里会强制走镜像站
        self.model = SentenceTransformer(model_name)
        
        # 初始化 ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.collection = self.client.get_or_create_collection(name="sales_knowledge")

    def _format_record(self, record: dict) -> str:
        cust = record.get("customer_info", {})
        opp = record.get("project_opportunity", {})
        
        text = f"记录类型: {record.get('record_type')}; "
        text += f"销售: {record.get('sales_rep')}; "
        text += f"摘要: {record.get('summary')}; "
        text += f"客户: {cust.get('name')} 来自 {cust.get('company')}; "
        text += f"项目: {opp.get('project_name')} 预算 {opp.get('budget')} 阶段 {opp.get('stage')}; "
        text += f"关键点: {', '.join(record.get('key_points', []))}"
        return text

    def add_record(self, record_id: int, record_data: dict):
        content_text = self._format_record(record_data)
        embedding = self.model.encode(content_text).tolist()
        
        self.collection.add(
            embeddings=[embedding],
            documents=[content_text],
            metadatas=[{"json_data": json.dumps(record_data, ensure_ascii=False)}],
            ids=[str(record_id)]
        )

    def delete_record(self, record_id: str):
        """
        从向量库中彻底删除指定 ID 的记录。
        """
        try:
            self.collection.delete(ids=[str(record_id)])
            return True
        except Exception as e:
            # 咱也不吱声，就在心里记个过
            # print(f"Vector delete warning: {e}")
            return False

    def search(self, query: str, top_k=5):
        query_embedding = self.model.encode(query).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        history_snippets = []
        if results and "metadatas" in results:
            for meta_list in results["metadatas"]:
                for meta in meta_list:
                    history_snippets.append(json.loads(meta["json_data"]))
        return history_snippets