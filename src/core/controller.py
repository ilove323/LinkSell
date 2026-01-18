import configparser
import json
import datetime
import re
from pathlib import Path
from src.services.llm_service import analyze_text, refine_sales_data, polish_text, update_sales_data
from src.services.asr_service import transcribe_audio

class LinkSellController:
    def __init__(self, config_path="config/config.ini"):
        self.config = configparser.ConfigParser()
        self.config_path = Path(config_path)
        if self.config_path.exists():
            self.config.read(self.config_path)
        
        self.api_key = self.config.get("doubao", "api_key", fallback=None)
        self.endpoint_id = self.config.get("doubao", "analyze_endpoint", fallback=None)
        
        # ASR Config
        self.asr_app_id = self.config.get("asr", "app_id", fallback=None)
        self.asr_token = self.config.get("asr", "access_token", fallback=None)
        self.asr_resource = self.config.get("asr", "resource_id", fallback="volc.seedasr.auc")
        if self.asr_resource == "volc.bigasr.sauc.duration":
             self.asr_resource = "volc.seedasr.auc"

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

    def get_missing_fields(self, data):
        """
        Identify missing required fields in the sales data.
        Returns a dict: {field_key: (display_name, parent_key)}
        """
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
            if parent_key:
                target_dict = data.get(parent_key, {})
            else:
                target_dict = data
            
            val = target_dict.get(field_key)
            is_missing = False
            if val is None:
                is_missing = True
            elif isinstance(val, str) and (not val.strip() or val in ["未知", "未指定", "N/A"]):
                is_missing = True
            elif isinstance(val, list) and not val:
                is_missing = True
            
            if is_missing:
                missing[field_key] = (field_name, parent_key)
                
        return missing

    def refine(self, data, supplements):
        return refine_sales_data(data, supplements, self.api_key, self.endpoint_id)

    def update(self, data, instruction):
        return update_sales_data(data, instruction, self.api_key, self.endpoint_id)

    def save(self, record):
        """
        Save to DB and backup file. Returns (record_id, backup_file_path).
        """
        data_file_path = Path(self.config.get("storage", "data_file", fallback="data/sales_data.json"))
        
        # 1. Main DB
        if data_file_path.exists():
            with open(data_file_path, "r", encoding="utf-8") as f:
                try:
                    db_data = json.load(f)
                except json.JSONDecodeError:
                    db_data = []
        else:
            db_data = []
            data_file_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        record["created_at"] = now.isoformat()
        record["id"] = len(db_data) + 1
        
        db_data.append(record)
        
        with open(data_file_path, "w", encoding="utf-8") as f:
            json.dump(db_data, f, ensure_ascii=False, indent=2)
            
        # 2. Backup File
        proj_name = record.get("project_opportunity", {}).get("project_name", "未命名项目")
        if not proj_name: proj_name = "未命名项目"
        
        safe_proj_name = re.sub(r'[\\/*?:",<>|]', "", proj_name).strip().replace(" ", "_")
        time_str = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_proj_name}-{time_str}.json"
        
        records_dir = data_file_path.parent / "records"
        records_dir.mkdir(parents=True, exist_ok=True)
        record_path = records_dir / filename
        
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            
        return record["id"], str(record_path)
