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
        采用后台异步加载 (Async Background Loading)，启动即开始加载，不阻塞主界面。
        """
        import threading
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        
        # 内部状态
        self.model = None
        self.client = None
        self.collection = None
        
        # 线程同步控制
        self._init_event = threading.Event()
        self._init_error = None
        
        # 启动后台加载线程
        print("🚀 [VectorService] 启动后台加载线程...")
        loader_thread = threading.Thread(target=self._background_loader, daemon=True)
        loader_thread.start()

    def _background_loader(self):
        """
        后台线程：默默地把模型和数据库加载好
        """
        try:
            print("⏳ [VectorService] 后台正在加载 Embedding 模型...")
            # 1. 加载模型
            self.model = SentenceTransformer(self.model_name)
            
            print("⏳ [VectorService] 后台正在连接 ChromaDB...")
            # 2. 连接数据库
            self.client = chromadb.PersistentClient(path=str(self.db_path))
            self.collection = self.client.get_or_create_collection(name="sales_knowledge")
            
            print("✅ [VectorService] 向量引擎后台加载完成！")
        except Exception as e:
            print(f"❌ [VectorService] 初始化失败: {e}")
            self._init_error = e
        finally:
            # 无论成功失败，都要通知主线程（避免死锁）
            self._init_event.set()

    def _ensure_initialized(self):
        """
        确保已初始化。如果还在加载，就等一会儿。
        """
        if not self._init_event.is_set():
            print("⚠️ [VectorService] 请求过早，正在等待引擎就绪...")
            self._init_event.wait() # <--- 只有这里会阻塞
        
        if self._init_error:
            raise RuntimeError(f"VectorService failed to initialize: {self._init_error}")

    def status(self):
        if self._init_error:
            return "Error"
        return "Ready" if self._init_event.is_set() else "Loading..."

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
        self._ensure_initialized() # <--- 确保就绪
        content_text = self._format_record(record_data)
        embedding = self.model.encode(content_text).tolist()
        
        # --- 虎哥升级：元数据拆解 (Metadata Extraction) ---
        # 把关键字段拆出来单独存，方便以后做精确筛选 (Where Filter)
        # 注意：Chroma的metadata只支持 str, int, float, bool
        
        # 获取项目名称 (兼容多层级)
        p_name = record_data.get("project_opportunity", {}).get("project_name")
        if not p_name: p_name = record_data.get("project_name", "未命名")
        
        # 获取阶段 (兼容多层级)
        stage = record_data.get("opportunity_stage")
        if not stage: stage = record_data.get("project_opportunity", {}).get("opportunity_stage", "")
        
        meta = {
            "json_data": json.dumps(record_data, ensure_ascii=False),
            "sales_rep": str(record_data.get("sales_rep", "未知")),  # 销售专栏
            "record_type": str(record_data.get("record_type", "商机")), # 类型
            "project_name": str(p_name), # 项目名
            "stage": str(stage) # 阶段
        }

        # 使用 upsert，如果 ID 存在就更新，不存在就新增
        self.collection.upsert(
            embeddings=[embedding],
            documents=[content_text],
            metadatas=[meta],
            ids=[str(record_id)]
        )

    def delete_record(self, record_id: str):
        """
        从向量库中彻底删除指定 ID 的记录。
        """
        self._ensure_initialized()
        try:
            self.collection.delete(ids=[str(record_id)])
            return True
        except Exception as e:
            # 咱也不吱声，就在心里记个过
            # print(f"Vector delete warning: {e}")
            return False

    def reset_db(self):
        """
        🔥 删库跑路...啊不是，清空重置！
        慎用！这会把所有存进去的向量全干掉。
        """
        self._ensure_initialized()
        try:
            self.client.delete_collection("sales_knowledge")
            self.collection = self.client.get_or_create_collection(name="sales_knowledge")
            return True
        except Exception as e:
            print(f"Reset failed: {e}")
            return False

    def search(self, query: str, top_k=5, where_filter: dict = None):
        """
        语义搜索 + 字段过滤
        where_filter: 比如 {"sales_rep": "张三"}，让它只在张三的记录里找。
        """
        self._ensure_initialized() # <--- 确保就绪
        query_embedding = self.model.encode(query).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter  # <--- 加上这句，精准制导！
        )
        
        history_snippets = []
        if results and "metadatas" in results:
            for meta_list in results["metadatas"]:
                for meta in meta_list:
                    history_snippets.append(json.loads(meta["json_data"]))
        return history_snippets

    def search_projects(self, project_name: str, top_k=3, threshold=1.2):
        """
        专门搜索相似的项目名。
        返回格式: [{"id": "...", "project_name": "...", "score": 0.85}, ...]
        threshold: 距离阈值 (L2距离)，越小越相似。默认 1.2，超过这个值的丢弃。
        """
        self._ensure_initialized() # <--- 确保就绪
        query_embedding = self.model.encode(project_name).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        
        matches = []
        if results and "metadatas" in results:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            # Chroma 默认 L2 距离：0是完全一样，2是完全相反。
            # 一般来说，< 1.0 是比较相关的，> 1.5 基本就是瞎猜了。
            distances = results["distances"][0] if "distances" in results else [0]*len(ids)
            
            for rid, meta, dist in zip(ids, metadatas, distances):
                # 核心过滤：距离太远的一脚踢开
                if dist > threshold:
                    continue

                try:
                    data = json.loads(meta["json_data"])
                    p_name = data.get("project_opportunity", {}).get("project_name")
                    if not p_name: p_name = data.get("project_name", "未知项目")
                    
                    # 简单去重逻辑可以在 controller 做，这里只管吐数据
                    matches.append({
                        "id": rid,
                        "project_name": p_name,
                        "distance": dist
                    })
                except: pass
        return matches