import configparser
import json
import datetime
import re
import os
from pathlib import Path
from src.services.llm_service import (
    analyze_text, refine_sales_data, polish_text, 
    update_sales_data, is_sales_content, classify_intent, query_sales_data
)
from src.services.asr_service import transcribe_audio
from src.services.vector_service import VectorService

class LinkSellController:
    def __init__(self, config_path="config/config.ini"):
        self.config = configparser.ConfigParser()
        self.config_path = Path(config_path)
        if self.config_path.exists():
            self.config.read(self.config_path)
        
        # 1. 设置全局环境变量 (解决模型下载问题)
        hf_endpoint = self.config.get("global", "hf_endpoint", fallback=None)
        if hf_endpoint:
            os.environ["HF_ENDPOINT"] = hf_endpoint
            
        self.api_key = self.config.get("doubao", "api_key", fallback=None)
        self.endpoint_id = self.config.get("doubao", "analyze_endpoint", fallback=None)
        
        # ASR Config
        self.asr_app_id = self.config.get("asr", "app_id", fallback=None)
        self.asr_token = self.config.get("asr", "access_token", fallback=None)
        self.asr_resource = self.config.get("asr", "resource_id", fallback="volc.seedasr.auc")
        if self.asr_resource == "volc.bigasr.sauc.duration":
             self.asr_resource = "volc.seedasr.auc"

        # 2. 初始化本地向量库
        try:
            self.vector_service = VectorService()
        except Exception as e:
            print(f"[yellow]警告：本地向量模型加载失败({{e}})锛回退到普通查询模式。[/yellow]")
            self.vector_service = None

    def validate_llm_config(self):
        return bool(self.api_key and self.endpoint_id and "YOUR_" not in self.api_key)

    def validate_asr_config(self):
        return bool(self.asr_app_id and self.asr_token and "YOUR_" not in self.asr_token)

    def transcribe(self, audio_file, debug=False):
        if not self.validate_asr_config():
            raise ValueError("ASR Configuration Invalid")
        return transcribe_audio(audio_file, self.asr_app_id, self.asr_token, self.asr_resource, debug=debug)

    def polish(self, text):
        if not self.validate_llm_config():
            raise ValueError("LLM Configuration Invalid")
        return polish_text(text, self.api_key, self.endpoint_id)

    def analyze(self, text):
        if not self.validate_llm_config():
            raise ValueError("LLM Configuration Invalid")
        return analyze_text(text, self.api_key, self.endpoint_id)

    def get_intent(self, text):
        """判断意图：ANALYZE, QUERY, OTHER"""
        if not self.validate_llm_config():
            return "ANALYZE"
        return classify_intent(text, self.api_key, self.endpoint_id)

    def handle_query(self, query_text):
        """执行查询逻辑：先从向量库检索最相关的上下文，再由 LLM 回答。"""
        if not self.validate_llm_config():
            return "无法执行查询：配置无效。"
            
        if self.vector_service:
            # 语义搜索：薅出最相关的 5 条记录
            history = self.vector_service.search(query_text, top_k=5)
        else:
            # 回退模式：读取 JSON 库最后 10 条
            data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
            history = []
            if data_file_path.exists():
                with open(data_file_path, "r", encoding="utf-8") as f:
                    try:
                        full_db = json.load(f)
                        history = full_db[-10:]
                    except: pass
        
        if not history:
            return "目前数据库里还是空的，老大哥也没法凭空给你变出数据来啊！"
            
        return query_sales_data(query_text, history, self.api_key, self.endpoint_id)

    def check_is_sales(self, text):
        """判断内容是否为销售相关。"""
        if not self.validate_llm_config():
            return True
        return is_sales_content(text, self.api_key, self.endpoint_id)

    def get_missing_fields(self, data):
        """识别缺失的必填字段。"""
        if "project_opportunity" not in data:
            data["project_opportunity"] = {}

        required_config = {
            "sales_rep": ("👨‍💼 我方销售", None),
            "timeline": ("⏱️ 时间节点", "project_opportunity"),
            "budget": ("💰 预算金额", "project_opportunity"),
            "procurement_process": ("📝 采购流程", "project_opportunity"),
            "competitors": ("⚔️ 竞争对手", "project_opportunity"),
            "tech_stack": ("🛠️ 我方参与技术", "project_opportunity"),
            "payment_terms": ("💳 付款方式", "project_opportunity")
        }
        
        missing = {}
        for field_key, (field_name, parent_key) in required_config.items():
            target_dict = data.get(parent_key) if parent_key else data
            val = target_dict.get(field_key) if target_dict else None
            
            is_missing = False
            if val is None: is_missing = True
            elif isinstance(val, str) and (not val.strip() or val in ["未知", "未指定", "N/A"]): is_missing = True
            elif isinstance(val, list) and not val: is_missing = True
            
            if is_missing:
                missing[field_key] = (field_name, parent_key)
        return missing

    def refine(self, data, supplements):
        return refine_sales_data(data, supplements, self.api_key, self.endpoint_id)

    def update(self, data, instruction):
        return update_sales_data(data, instruction, self.api_key, self.endpoint_id)

    def save(self, record):
        """保存记录：双写模式 (JSON DB + Vector DB)。"""
        data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
        
        # 1. 存入 JSON 主库
        if data_file_path.exists():
            with open(data_file_path, "r", encoding="utf-8") as f:
                try: db_data = json.load(f)
                except: db_data = []
        else:
            db_data = []
            data_file_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        record["created_at"] = now.isoformat()
        record_id = len(db_data) + 1
        record["id"] = record_id
        db_data.append(record)
        
        with open(data_file_path, "w", encoding="utf-8") as f:
            json.dump(db_data, f, ensure_ascii=False, indent=2)
            
        # 2. 存入向量库
        if self.vector_service:
            try:
                self.vector_service.add_record(record_id, record)
            except Exception as e:
                print(f"[yellow]向量存入失败：{{e}}[/yellow]")
            
        # 3. 备份独立文件
        proj_name = record.get("project_opportunity", {}).get("project_name", "未命名项目")
        safe_proj_name = re.sub(r'[\\/*?:",<>|]', "", str(proj_name)).strip().replace(" ", "_")
        time_str = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_proj_name}-{time_str}.json"
        
        records_dir = data_file_path.parent / "records"
        records_dir.mkdir(parents=True, exist_ok=True)
        record_path = records_dir / filename
        
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            
        return record["id"], str(record_path)
