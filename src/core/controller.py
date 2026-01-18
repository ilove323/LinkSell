import configparser
import json
import datetime
import re
import os
from pathlib import Path
from src.services.llm_service import (
    analyze_text, refine_sales_data, polish_text, 
    update_sales_data, is_sales_content, classify_intent, query_sales_data, summarize_text
)
from src.services.asr_service import transcribe_audio
from src.services.vector_service import VectorService

class LinkSellController:
    def __init__(self, config_path="config/config.ini"):
        self.config = configparser.ConfigParser()
        self.config_path = Path(config_path)
        if self.config_path.exists():
            self.config.read(self.config_path)
        
        # 1. 设置全局环境变量与默认记录者
        hf_endpoint = self.config.get("global", "hf_endpoint", fallback=None)
        if hf_endpoint:
            os.environ["HF_ENDPOINT"] = hf_endpoint
        
        self.default_recorder = self.config.get("global", "default_recorder", fallback="陈一骏")
            
        self.api_key = self.config.get("doubao", "api_key", fallback=None)
        self.endpoint_id = self.config.get("doubao", "analyze_endpoint", fallback=None)
        
        # ASR Config
        self.asr_app_id = self.config.get("asr", "app_id", fallback=None)
        self.asr_token = self.config.get("asr", "access_token", fallback=None)
        self.asr_resource = self.config.get("asr", "resource_id", fallback="volc.seedasr.auc")
        if self.asr_resource == "volc.bigasr.sauc.duration":
             self.asr_resource = "volc.seedasr.auc"

        # 2. 加载商机阶段映射
        self.stage_map = {}
        if self.config.has_section("opportunity_stages"):
            self.stage_map = {k: v for k, v in self.config.items("opportunity_stages")}

        # 3. 初始化本地向量库
        try:
            self.vector_service = VectorService()
        except Exception as e:
            print(f"[yellow]警告：本地向量模型加载失败({e})，将回退到普通查询模式。[/yellow]")
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

    def identify_intent(self, text):
        """识别意图：ANALYZE, QUERY, OTHER"""
        if not self.validate_llm_config():
            return "ANALYZE"
        return classify_intent(text, self.api_key, self.endpoint_id)

    def search_opportunities(self, keyword):
        """根据关键字模糊搜索已有的项目名称，返回 (项目名, 销售) 列表。"""
        data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
        if not data_file_path.exists():
            return []
        
        with open(data_file_path, "r", encoding="utf-8") as f:
            try: db_data = json.load(f)
            except: db_data = []
        
        # 匹配结果：包含项目名和销售人
        matches = []
        for p in db_data:
            p_name = p.get("project_name", "")
            if keyword.lower() in p_name.lower():
                matches.append({
                    "name": p_name,
                    "sales_rep": p.get("sales_rep", "未知")
                })
        return matches

    def handle_query(self, query_text):
        if not self.validate_llm_config():
            return "__ERROR_CONFIG__"
            
        if self.vector_service:
            history = self.vector_service.search(query_text, top_k=5)
        else:
            data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
            history = []
            if data_file_path.exists():
                with open(data_file_path, "r", encoding="utf-8") as f:
                    try:
                        full_db = json.load(f)
                        history = full_db[-10:]
                    except: pass
        
        if not history:
            return "__EMPTY_DB__"
            
        return query_sales_data(query_text, history, self.api_key, self.endpoint_id)

    def check_is_sales(self, text):
        if not self.validate_llm_config():
            return True
        return is_sales_content(text, self.api_key, self.endpoint_id)

    def get_missing_fields(self, data):
        if "project_opportunity" not in data:
            data["project_opportunity"] = {}

        required_config = {
            "sales_rep": ("👨‍💼 我方销售", None),
            "opportunity_stage": ("📈 商机阶段 (1:需求确认 2:沟通交流 3:商务谈判 4:签订合同)", "project_opportunity"),
            "timeline": ("⏱️ 时间节点", "project_opportunity"),
            "budget": ("💰 预算金额", "project_opportunity"),
            "procurement_process": ("📝 采购流程", "project_opportunity"),
            "competitors": ("⚔️ 竞争对手", "project_opportunity"),
            "technical_staff": ("🧑‍💻 我方技术人员", "project_opportunity"),
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

    def save(self, record, raw_content=""):
        """
        保存商机信息：以项目名为唯一标识，聚合存储。
        raw_content: polish_text.txt 润色后的原始文字。
        """
        data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
        
        # 1. 文字提炼 (如果润色文本 > 500字则生成摘要)
        note_text = raw_content if raw_content else record.get("summary", "")
        if len(note_text) > 500:
            note_text = summarize_text(note_text, self.api_key, self.endpoint_id)

        # 2. 读取主库
        if data_file_path.exists():
            with open(data_file_path, "r", encoding="utf-8") as f:
                try: db_data = json.load(f)
                except: db_data = []
        else:
            db_data = []
            data_file_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        proj_info = record.get("project_opportunity", {})
        proj_name = proj_info.get("project_name", "未命名项目")
        
        # 3. 构造本次记录的小记 (含时间、记录者、精修文本)
        new_log_entry = {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "recorder": self.default_recorder,
            "content": note_text
        }

        # 4. 寻找或创建商机项
        target_proj = next((p for p in db_data if p.get("project_name") == proj_name), None)
        
        if target_proj:
            # 更新商机属性
            for key, val in proj_info.items():
                if val is not None and val != "":
                    target_proj[key] = val
            target_proj.setdefault("customer_info", {}).update(record.get("customer_info", {}))
            # 追加到记录志数组
            target_proj.setdefault("record_logs", []).append(new_log_entry)
            target_proj["updated_at"] = now.isoformat()
            record_id = target_proj.get("id", 0)
        else:
            # 新建商机
            new_proj = proj_info.copy()
            new_proj["project_name"] = proj_name
            new_proj["customer_info"] = record.get("customer_info", {})
            new_proj["record_logs"] = [new_log_entry]
            new_proj["created_at"] = now.isoformat()
            new_proj["updated_at"] = now.isoformat()
            record_id = len(db_data) + 1
            new_proj["id"] = record_id
            db_data.append(new_proj)
        
        with open(data_file_path, "w", encoding="utf-8") as f:
            json.dump(db_data, f, ensure_ascii=False, indent=2)
            
        # 5. 向量库同步
        if self.vector_service:
            try:
                self.vector_service.add_record(record_id, record)
            except: pass
            
        return record_id, "data/records/backup.json"

    def get_all_opportunities(self):
        """获取所有商机记录"""
        data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
        if not data_file_path.exists(): return []
        with open(data_file_path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []

    def get_opportunity_by_id(self, record_id):
        """根据 ID 获取单条商机"""
        all_data = self.get_all_opportunities()
        # JSON 中读取的 ID 可能是 int，传入的可能是 str，做个兼容
        return next((item for item in all_data if str(item.get("id")) == str(record_id)), None)

    def delete_opportunity(self, record_id):
        """根据 ID 删除商机"""
        all_data = self.get_all_opportunities()
        initial_len = len(all_data)
        all_data = [item for item in all_data if str(item.get("id")) != str(record_id)]
        
        if len(all_data) < initial_len:
            data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
            with open(data_file_path, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            
            # 补刀：把向量库里的幽灵也给灭了
            if self.vector_service:
                self.vector_service.delete_record(record_id)
            
            return True
        return False

    def overwrite_opportunity(self, new_data):
        """
        完全覆盖更新一个商机记录（用于编辑模式）。
        不同于 save 的“追加模式”，这是“重写模式”。
        """
        all_data = self.get_all_opportunities()
        record_id = new_data.get("id")
        
        if not record_id: return False
        
        updated = False
        for i, item in enumerate(all_data):
            if str(item.get("id")) == str(record_id):
                # 保持记录日志不丢失 (如果 new_data 里没有带回来 record_logs)
                if "record_logs" not in new_data and "record_logs" in item:
                    new_data["record_logs"] = item["record_logs"]
                
                # 更新时间戳
                new_data["updated_at"] = datetime.datetime.now().isoformat()
                
                all_data[i] = new_data
                updated = True
                break
        
        if updated:
            data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
            with open(data_file_path, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            
            # 同步更新向量库
            if self.vector_service:
                 try: self.vector_service.add_record(record_id, new_data)
                 except: pass
            return True
        return False
