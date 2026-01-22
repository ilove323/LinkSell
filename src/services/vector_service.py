"""
LinkSell 向量数据库服务 (RAG Core)

职责：
- 管理本地向量数据库 (ChromaDB) 的生命周期
- 将非结构化商机数据转化为向量 (Embedding)
- 提供基于语义的模糊搜索与基于字段的精确过滤

特点：
- **Hybrid Search**: 支持"语义相似度 + 元数据过滤"的混合检索
- **Async Loading**: 采用后台线程加载模型，避免阻塞主程序启动
- **Metadata Extraction**: 自动拆分关键字段 (销售、阶段等) 用于精确筛选
"""

import os
import threading
import json
from pathlib import Path

# [环境配置] 必须在导入 sentence_transformers 之前设置
# 作用：强制使用 HF 国内镜像，防止下载模型时超时；清除代理防止连接错误
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""

import chromadb
from sentence_transformers import SentenceTransformer

class VectorService:
    def __init__(self, db_path="data/vector_db", model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        """
        [初始化] 启动后台加载线程
        
        参数:
        - db_path: 向量数据库的本地存储路径
        - model_name: 使用的 Embedding 模型名称 (默认多语言小模型)
        """
        
        # 确保数据目录存在
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        
        # [内部状态]
        self.model = None       # Embedding 模型实例
        self.client = None      # ChromaDB 客户端
        self.collection = None  # ChromaDB 集合 (Table)
        
        # [线程控制] 用于同步主线程和加载线程
        self._init_event = threading.Event()
        self._init_error = None
        
        # [启动后台线程]
        # 这样主程序可以立刻启动 UI，不用等模型加载完
        print("🚀 [VectorService] 启动后台加载线程...")
        loader_thread = threading.Thread(target=self._background_loader, daemon=True)
        loader_thread.start()

    def _background_loader(self):
        """
        [后台任务] 执行耗时的模型加载和数据库连接
        """
        try:
            print("⏳ [VectorService] 后台正在加载 Embedding 模型...")
            # 1. 加载 HuggingFace 模型 (第一次会下载，比较慢)
            self.model = SentenceTransformer(self.model_name)
            
            print("⏳ [VectorService] 后台正在连接 ChromaDB...")
            # 2. 初始化持久化向量数据库
            self.client = chromadb.PersistentClient(path=str(self.db_path))
            # 获取或创建名为 'sales_knowledge' 的集合
            self.collection = self.client.get_or_create_collection(name="sales_knowledge")
            
            print("✅ [VectorService] 向量引擎后台加载完成！")
        except Exception as e:
            print(f"❌ [VectorService] 初始化失败: {e}")
            self._init_error = e
        finally:
            # 无论成功失败，都设置 Event，通知主线程等待结束
            self._init_event.set()

    def _ensure_initialized(self, timeout: float = 30.0):
        """
        [状态守卫] 确保服务已就绪
        如果主线程在后台加载完成前调用了方法，这里会阻塞等待。

        参数:
        - timeout: 最大等待时间(秒)，防止无限阻塞
        """
        if not self._init_event.is_set():
            print(f"⚠️ [VectorService] 请求过早，正在等待最多 {timeout}s 引擎就绪...")
            if not self._init_event.wait(timeout=timeout):
                raise TimeoutError(f"VectorService 初始化超时 ({timeout}s)")

        if self._init_error:
            raise RuntimeError(f"VectorService failed to initialize: {self._init_error}")

    def status(self):
        """检查当前服务状态 (用于 UI 展示)"""
        if self._init_error:
            return "Error"
        return "Ready" if self._init_event.is_set() else "Loading..."

    def _format_record(self, record: dict) -> str:
        """
        [数据处理] 将 JSON 结构化数据转换为用于 Embedding 的纯文本
        这是 RAG 的关键：把分散的字段拼接成一段有意义的话。
        """
        cust = record.get("customer_info", {})
        opp = record.get("project_opportunity", {})
        
        text = f"记录类型: {record.get('record_type')}; "
        text += f"销售: {record.get('sales_rep')}; "
        text += f"摘要: {record.get('summary')}; "
        text += f"客户: {cust.get('name')} 来自 {cust.get('company')}; "
        text += f"项目: {opp.get('project_name')} 预算 {opp.get('budget')} 阶段 {opp.get('stage')}; "
        text += f"关键点: {', '.join(record.get('key_points', []))}"
        return text

    def add_record(self, record_id: int, record_data: dict, timeout: float = 30.0):
        """
        [核心功能] 添加或更新一条记录

        参数:
        - timeout: 初始化超时时间(秒)
        """
        self._ensure_initialized(timeout=timeout) # 确保就绪
        
        # 1. 生成内容向量
        content_text = self._format_record(record_data)
        embedding = self.model.encode(content_text).tolist()
        
        # 2. [元数据提取] (Metadata Extraction)
        # 将关键字段单独拆分存入 metadata，以便后续使用 where 语句进行精确过滤
        # 注意：Chroma 的 metadata 只能存简单类型 (str, int, float, bool)
        
        # 提取项目名 (兼容多层级)
        p_name = record_data.get("project_opportunity", {}).get("project_name")
        if not p_name: p_name = record_data.get("project_name", "未命名")
        
        # 提取阶段
        stage = record_data.get("opportunity_stage")
        if not stage: stage = record_data.get("project_opportunity", {}).get("opportunity_stage", "")
        
        meta = {
            "json_data": json.dumps(record_data, ensure_ascii=False), # 存完整 JSON 方便还原
            "sales_rep": str(record_data.get("sales_rep", "未知")),  # <--- 销售过滤的关键
            "record_type": str(record_data.get("record_type", "商机")),
            "project_name": str(p_name),
            "stage": str(stage)
        }

        # 3. 存入数据库 (Upsert: 存在则更新，不存在则插入)
        self.collection.upsert(
            embeddings=[embedding],
            documents=[content_text],
            metadatas=[meta],
            ids=[str(record_id)]
        )

    def delete_record(self, record_id: str, timeout: float = 30.0):
        """
        [核心功能] 删除指定记录

        参数:
        - timeout: 初始化超时时间(秒)
        """
        self._ensure_initialized(timeout=timeout)
        try:
            self.collection.delete(ids=[str(record_id)])
            return True
        except Exception as e:
            # 删除失败通常不影响主流程，记录即可
            return False

    def reset_db(self, timeout: float = 30.0):
        """
        [危险操作] 清空所有数据

        参数:
        - timeout: 初始化超时时间(秒)
        """
        self._ensure_initialized(timeout=timeout)
        try:
            self.client.delete_collection("sales_knowledge")
            self.collection = self.client.get_or_create_collection(name="sales_knowledge")
            return True
        except Exception as e:
            print(f"Reset failed: {e}")
            return False

    def search(self, query: str, top_k=5, where_filter: dict = None, timeout: float = 30.0):
        """
        [核心功能] 语义搜索

        参数:
        - query: 用户的问题或搜索词
        - top_k: 返回最相似的前 K 条
        - where_filter: 过滤条件 (例如 {"sales_rep": "张三"})
        - timeout: 初始化超时时间(秒)
        """
        self._ensure_initialized(timeout=timeout)
        
        # 1. 将查询词转换为向量
        query_embedding = self.model.encode(query).tolist()
        
        # 2. 在数据库中执行向量近邻搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter  # <--- 精确过滤条件
        )
        
        # 3. 解析结果，提取原始 JSON 数据
        history_snippets = []
        if results and "metadatas" in results:
            for meta_list in results["metadatas"]:
                for meta in meta_list:
                    # 从 metadata 中还原完整的 JSON 对象
                    history_snippets.append(json.loads(meta["json_data"]))
        return history_snippets

    def search_projects(self, project_name: str, top_k=3, threshold=1.2, timeout: float = 30.0):
        """
        [专用功能] 项目名相似度搜索
        用于检查项目是否已存在，或者根据模糊名称找项目。

        参数:
        - threshold: 距离阈值 (L2距离)。越小越相似，超过此值则丢弃。
        - timeout: 初始化超时时间(秒)
        """
        self._ensure_initialized(timeout=timeout)
        query_embedding = self.model.encode(project_name).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        
        matches = []
        if results and "metadatas" in results:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            # 获取距离 (0=完全一致)
            distances = results["distances"][0] if "distances" in results else [0]*len(ids)
            
            for rid, meta, dist in zip(ids, metadatas, distances):
                # 过滤掉距离太远的结果 (不相关)
                if dist > threshold:
                    continue

                try:
                    data = json.loads(meta["json_data"])
                    p_name = data.get("project_opportunity", {}).get("project_name")
                    if not p_name: p_name = data.get("project_name", "未知项目")
                    
                    matches.append({
                        "id": rid,
                        "project_name": p_name,
                        "sales_rep": data.get("sales_rep", "未知"),
                        "distance": dist
                    })
                except: pass
        return matches
