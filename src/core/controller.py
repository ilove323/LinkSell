import configparser
import json
import datetime
import re
import os
import glob
from pathlib import Path
from src.services.llm_service import (
    polish_text, classify_intent, query_sales_data, summarize_text,
    architect_analyze
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
        self.note_buffer = [] # 笔记暂存区 (V3.0)
            
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

        # 3. 初始化数据目录
        self.data_dir = Path("data/opportunities")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 4. 初始化本地向量库
        try:
            self.vector_service = VectorService()
        except Exception as e:
            print(f"[yellow]警告：本地向量模型加载失败({{e}})锛�将回退到普通查询模式銆�[/yellow]")
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

    def identify_intent(self, text):
        """识别意图和内容，返回 {"intent": "...", "content": "..."}"""
        if not self.validate_llm_config():
            return {"intent": "RECORD", "content": text}
        
        # 调用 LLM 进行分类，期望返回 JSON 格式
        result = classify_intent(text, self.api_key, self.endpoint_id)
        
        # 尝试解析 JSON 响应
        try:
            if isinstance(result, dict):
                parsed = result
            else:
                # 如果 LLM 返回字符串，尝试解析
                parsed = json.loads(result) if isinstance(result, str) else {"intent": result}
            
            intent = parsed.get("intent", "RECORD").upper()
            content = parsed.get("content", text)
        except:
            # JSON 解析失败，降级为关键词判断 (V3.0 置换版)
            intent = "RECORD" # 默认归为笔记暂存
            content = text
            if any(k in text for k in ["保存"]): 
                intent = "SAVE"
            elif any(k in text for k in ["正式保存", "正式录入", "提交到", "创建项目", "新建项目", "存入商机"]): 
                intent = "CREATE"
            elif any(k in text for k in ["查", "找", "看", "哪些", "搜索", "列表"]): 
                intent = "LIST"
            elif any(k in text for k in ["删", "移除"]): 
                intent = "DELETE"
            elif any(k in text for k in ["改", "更新", "换"]): 
                intent = "REPLACE"
        
        # 严格规范化意图
        valid_intents = ["CREATE", "LIST", "GET", "REPLACE", "DELETE", "RECORD", "SAVE", "MERGE", "OTHER"]
        if intent not in valid_intents:
            intent = "RECORD"
        
        # OTHER 的人工复核：防止对业务指令的误杀 (V3.0 置换版)
        if intent == "OTHER":
            biz_keywords = ["项目", "商机", "单子", "客户", "聊", "谈", "预算", "进度", "跟进", "详情", "档案", "会议", "一期", "二期"]
            if len(text) > 8 or any(k in text for k in biz_keywords):
                intent = "RECORD"
        
        return {"intent": intent, "content": content}

    def extract_search_term(self, text):
        """
        使用 LLM 从用户指令中提取核心搜索词（项目名）。
        例如："查看沈阳轴承厂详情" -> "沈阳轴承厂"
        """
        from volcenginesdkarkruntime import Ark
        
        client = Ark(api_key=self.api_key)
        # 加载 prompt
        prompt_path = Path("config/prompts/extract_search_term.txt")
        if not prompt_path.exists(): return text # Fallback
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()

        try:
            completion = client.chat.completions.create(
                model=self.endpoint_id,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.1, 
            )
            term = completion.choices[0].message.content.strip()
            if "Unknown" in term: return text
            # 去除可能的引号和反引号，并且前后去空格，省得这小瘪犊子坑咱
            return term.replace('"', '').replace("'", "").replace("`", "").strip()
        except:
            return text

    def normalize_input(self, text, context_type="EMPTY_CHECK"):
        """
        规范化用户输入。
        context_type: EMPTY_CHECK (补全字段), SELECTION (选择题)
        返回: 规范化后的字符串，如果是无效输入则返回 ""
        """
        if not text or not text.strip(): return ""
        
        from volcenginesdkarkruntime import Ark
        client = Ark(api_key=self.api_key)
        prompt_path = Path("config/prompts/normalize_input.txt")
        if not prompt_path.exists(): return text
        
        with open(prompt_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()
            
        user_msg = f"Context Type: {context_type}\nUser Input: {text}"

        try:
            completion = client.chat.completions.create(
                model=self.endpoint_id,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
            )
            normalized = completion.choices[0].message.content.strip()
            if "[[NULL]]" in normalized:
                return ""
            return normalized
        except:
            return text

    def _get_safe_filename(self, project_name):
        """将项目名转换为安全的文件名"""
        # 替换掉 / \ : * ? " < > | 等非法字符
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', project_name)
        return self.data_dir / f"{safe_name}.json"

    def list_opportunities(self, filter_func=None):
        """
        获取符合条件的商机列表 (List 操作)
        filter_func: 一个函数，接收商机数据 dict，返回 bool。如果不传则返回所有。
        """
        all_data = self.get_all_opportunities()
        if not filter_func:
            return all_data
        
        filtered = []
        for item in all_data:
            if filter_func(item):
                filtered.append(item)
        return filtered

    def search_opportunities(self, keyword):
        """根据关键字模糊搜索已有的项目名称，返回 (项目名, 销售) 列表。"""
        # 使用 list_opportunities 实现
        def keyword_filter(data):
            p_name = data.get("project_opportunity", {}).get("project_name", "")
            if not p_name: p_name = data.get("project_name", "")
            # 双向包含：搜 "轴承" -> "沈阳轴承" (Keyword in Name)
            #           搜 "查看沈阳轴承" -> "沈阳轴承" (Name in Keyword)
            k_low = keyword.lower(); p_low = p_name.lower()
            return (k_low in p_low) or (len(p_name) > 2 and p_low in k_low)
            
        matches = []
        for p in self.list_opportunities(keyword_filter):
            p_name = p.get("project_opportunity", {}).get("project_name", "")
            if not p_name: p_name = p.get("project_name", "")
            matches.append({
                "name": p_name,
                "sales_rep": p.get("sales_rep", "未知"),
                "id": p.get("id")
            })
        return matches

    def find_potential_matches(self, project_name):
        """
        结合关键字和向量搜索，寻找疑似存在的项目。
        返回: [{"name": "项目A", "source": "keyword/vector", "id": "..."}]
        """
        candidates = {} # 用 name 做 key 去重

        # 1. 关键字搜索 (本地文件扫描)
        kw_matches = self.search_opportunities(project_name)
        for m in kw_matches:
            candidates[m["name"]] = {"name": m["name"], "source": "关键字匹配", "sales_rep": m["sales_rep"], "id": m["id"]}

        # 2. 向量搜索 (语义近似)
        if self.vector_service:
            vec_matches = self.vector_service.search_projects(project_name)
            for vm in vec_matches:
                p_name = vm["project_name"]
                # 只有当关键字没搜到，且名字不完全一样时才加进去（避免重复）
                if p_name not in candidates:
                    candidates[p_name] = {"name": p_name, "source": "语义相似", "sales_rep": "未知", "id": vm.get("id")} # 向量库暂未返回sales_rep，简化处理

        # --- [优化] 精确匹配优先策略 ---
        clean_search = project_name.strip().lower()
        exact_match = None
        contained_match = None
        max_len = 0
        
        for name, cand in candidates.items():
            c_name = name.strip().lower()
            
            # 1. 绝对精确匹配 (最高优先级)
            if c_name == clean_search:
                return [cand]
            
            # 2. 包含匹配 (Name in SearchTerm) - 处理提取不干净的情况
            # 例如 Search="商机沈阳机床", Name="沈阳机床"
            if len(c_name) > 2 and c_name in clean_search:
                # 贪婪匹配：如果有多个被包含的，取名字最长的那个
                # (防止搜 "A二期" 时匹配到 "A")
                if len(c_name) > max_len:
                    max_len = len(c_name)
                    contained_match = cand
        
        if contained_match:
            return [contained_match]

        return list(candidates.values())

    def handle_query(self, query_text):
        if not self.validate_llm_config():
            return "__ERROR_CONFIG__"
            
        if self.vector_service:
            history = self.vector_service.search(query_text, top_k=5)
        else:
            # 回退：读取最近修改的 10 个文件
            history = []
            files = sorted(self.data_dir.glob("*.json"), key=os.path.getmtime, reverse=True)[:10]
            for fp in files:
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        history.append(json.load(f))
                except: pass
        
        if not history:
            return "__EMPTY_DB__"
            
        return query_sales_data(query_text, history, self.api_key, self.endpoint_id)

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

    def merge(self, data: dict, note_content: str) -> dict:
        """
        MERGE 流程：智能合并笔记到商机
        
        逻辑：
        1. 解析笔记内容，提取结构化字段
        2. 对比原商机，逐字段更新（若解析后非空且与原不同）
        3. action_items 和 key_points 执行追加（不覆盖）
        4. 最后添加 record_log 记录本次笔记
        
        返回: 更新后的商机数据
        """
        from src.services.llm_service import architect_analyze
        import datetime
        now = datetime.datetime.now()
        
        # 步骤1：解析笔记，提取结构化数据
        parsed_data = architect_analyze(
            [note_content],
            self.api_key,
            self.endpoint_id,
            original_data=data,
            recorder=self.default_recorder
        )
        
        if not parsed_data:
            # 解析失败，只添加到 record_logs，不更新其他字段
            if "record_logs" not in data:
                data["record_logs"] = []
            new_log_entry = {
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "recorder": self.default_recorder,
                "content": note_content
            }
            data["record_logs"].append(new_log_entry)
            data["updated_at"] = now.isoformat()
            return data
        
        # 步骤2：对比并智能更新字段
        merged = data.copy()
        
        # 2.1 更新顶层字段（除了 project_opportunity）
        merge_fields = [
            "project_name", "summary", "customer_info", 
            "sentiment", "current_log_entry"
        ]
        
        for field in merge_fields:
            if field in parsed_data:
                new_val = parsed_data[field]
                # 检查：非空且与原数据不同，则更新
                if new_val and new_val != merged.get(field):
                    merged[field] = new_val
        
        # 2.1.1 特殊处理 opportunity_stage（必须在顶层，确保类型为整数）
        stage_val = None
        if "opportunity_stage" in parsed_data:
            stage_val = parsed_data["opportunity_stage"]
        elif "project_opportunity" in parsed_data and isinstance(parsed_data.get("project_opportunity"), dict) and "opportunity_stage" in parsed_data["project_opportunity"]:
            # 备选方案：如果在 project_opportunity 中，也提取出来
            stage_val = parsed_data["project_opportunity"]["opportunity_stage"]
        
        # 如果获取到新阶段值（类型转换为整数），且不同于原值，则更新顶层的 opportunity_stage
        if stage_val is not None:
            try:
                # 尝试转换为整数（如果是字符串"2"，转为2）
                if isinstance(stage_val, str):
                    stage_val = int(stage_val)
                current_stage = merged.get("opportunity_stage")
                if stage_val != current_stage:
                    merged["opportunity_stage"] = stage_val
                    # 同时更新 project_opportunity 中的 opportunity_stage（如果存在）以保持一致性
                    if "project_opportunity" in merged and isinstance(merged["project_opportunity"], dict):
                        merged["project_opportunity"]["opportunity_stage"] = stage_val
            except (ValueError, TypeError):
                # 如果转换失败，跳过该字段
                pass
        
        # 2.2 更新 project_opportunity（嵌套字段）
        if "project_opportunity" in parsed_data:
            if "project_opportunity" not in merged:
                merged["project_opportunity"] = {}
            
            parsed_opp = parsed_data["project_opportunity"]
            current_opp = merged["project_opportunity"]
            
            # 对 project_opportunity 中的字段进行更新（除了 action_items 和 key_points）
            opp_merge_fields = [
                "project_name", "budget", "timeline", "procurement_process",
                "payment_terms", "competitors", "technical_staff", "sentiment"
            ]
            
            for field in opp_merge_fields:
                if field in parsed_opp:
                    new_val = parsed_opp[field]
                    if new_val and new_val != current_opp.get(field):
                        current_opp[field] = new_val
            
            # 2.3 特殊处理：action_items 和 key_points 执行追加
            if "action_items" in parsed_opp and parsed_opp["action_items"]:
                if "action_items" not in current_opp:
                    current_opp["action_items"] = []
                # 去重后追加（避免重复）
                existing_items = set(current_opp["action_items"])
                for item in parsed_opp["action_items"]:
                    if item not in existing_items:
                        current_opp["action_items"].append(item)
            
            if "key_points" in parsed_opp and parsed_opp["key_points"]:
                if "key_points" not in current_opp:
                    current_opp["key_points"] = []
                # 去重后追加
                existing_points = set(current_opp["key_points"])
                for point in parsed_opp["key_points"]:
                    if point not in existing_points:
                        current_opp["key_points"].append(point)
        
        # 步骤3：添加 record_log 记录本次笔记
        if "record_logs" not in merged:
            merged["record_logs"] = []
        
        new_log_entry = {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "recorder": self.default_recorder,
            "content": note_content
        }
        merged["record_logs"].append(new_log_entry)
        merged["updated_at"] = now.isoformat()
        
        return merged

    def replace(self, data, instruction):
        """
        REPLACE 流程：修改商机数据 (V3.0 使用 Architect 引擎)
        """
        # 将单条指令视为一条笔记，利用 Architect 的合并能力
        updated_data = architect_analyze(
            [instruction], 
            self.api_key, 
            self.endpoint_id, 
            original_data=data, 
            recorder=self.default_recorder
        )
        
        if not updated_data:
            return data
            
        # --- 强一致性同步逻辑 (保留) ---
        new_opp = updated_data.get("project_opportunity", {})
        inner_name = new_opp.get("project_name")
        outer_name = updated_data.get("project_name")
        
        if inner_name and inner_name != outer_name:
            updated_data["project_name"] = inner_name
        elif outer_name and outer_name != inner_name:
            if "project_opportunity" not in updated_data: updated_data["project_opportunity"] = {}
            updated_data["project_opportunity"]["project_name"] = outer_name
            
        # --- 保留系统级元数据 (保留) ---
        meta_keys = ["id", "_file_path", "_temp_id", "created_at", "record_logs", "updated_at", "recorder"]
        for k in meta_keys:
            if k in data and k not in updated_data:
                updated_data[k] = data[k]
        
        # --- 为兼容性，确保 sales_rep 字段与 recorder 同步 ---
        # 优先级：LLM返回的sales_rep > recorder值
        if "sales_rep" not in updated_data:
            # 如果LLM没有提取sales_rep，使用recorder值保持一致
            if "recorder" in updated_data:
                updated_data["sales_rep"] = updated_data["recorder"]
            elif "recorder" in data:
                updated_data["sales_rep"] = data["recorder"]
        
        # 如果修改了sales_rep，也同步到recorder（保持一致性）
        if "sales_rep" in updated_data and "recorder" not in updated_data:
            updated_data["recorder"] = updated_data["sales_rep"]
        
        # --- [原子操作]：如果修改了商机名称，处理文件重命名 (保留) ---
        old_proj_name = data.get("project_opportunity", {}).get("project_name")
        new_proj_name = updated_data.get("project_opportunity", {}).get("project_name")
        
        if old_proj_name and new_proj_name and old_proj_name != new_proj_name:
            old_file_path = Path(data.get("_file_path", ""))
            new_file_path = self._get_safe_filename(new_proj_name)
            
            if old_file_path.resolve() != new_file_path.resolve():
                try:
                    save_data = updated_data.copy()
                    save_data.pop("_temp_id", None)
                    save_data.pop("_file_path", None)
                    save_data["updated_at"] = datetime.datetime.now().isoformat()
                    
                    new_file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(new_file_path, "w", encoding="utf-8") as f:
                        json.dump(save_data, f, ensure_ascii=False, indent=2)
                    
                    if old_file_path.exists():
                        os.remove(old_file_path)
                    
                    if self.vector_service:
                        real_id = updated_data.get("id")
                        if real_id:
                            self.vector_service.delete_record(real_id)
                            self.vector_service.add_record(real_id, save_data)
                    
                    updated_data["_file_path"] = str(new_file_path)
                    
                except Exception as e:
                    print(f"⚠️ 商机名称重命名失败: {e}")
            
        return updated_data

    def save(self, record, raw_content=""):
        """
        保存商机信息：每个商机一个独立 JSON 文件。
        V3.0：优先使用 current_log_entry 字段作为日志内容。
        """
        now = datetime.datetime.now()
        
        # 1. 确定日志内容
        # 优先从 Architect 生成的 current_log_entry 中获取
        final_log_content = record.pop("current_log_entry", None)
        
        if not final_log_content:
            # Fallback 1: 传入的原始文本
            polished_text = raw_content if raw_content else record.get("summary", "")
            # 核心逻辑：如果文本太长，则生成摘要；否则直接用
            if polished_text and len(polished_text) > 500:
                final_log_content = summarize_text(polished_text, self.api_key, self.endpoint_id)
            else:
                final_log_content = polished_text or "无详细小记"

        # 2. 准备小记条目
        new_log_entry = {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "recorder": self.default_recorder,
            "content": final_log_content
        }

        proj_info = record.get("project_opportunity", {})
        proj_name = proj_info.get("project_name", record.get("project_name", "未命名项目"))
        
        # 3. 确定文件路径
        file_path = self._get_safe_filename(proj_name)
        
        # 4. 读取现有文件或初始化新结构
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                try: target_proj = json.load(f)
                except: target_proj = {}
        else:
            target_proj = {
                "id": record.get("id") or str(int(now.timestamp())),
                "created_at": now.isoformat(),
                "record_logs": []
            }

        # 5. 更新核心数据
        # 排除掉不需要在持久化 JSON 中重复出现的元数据
        record.pop("_temp_id", None)
        record.pop("_file_path", None)
        
        target_proj.update(record) 
        if "project_opportunity" not in target_proj: target_proj["project_opportunity"] = {}
        target_proj["project_opportunity"].update(proj_info)
        
        if "customer_info" not in target_proj: target_proj["customer_info"] = {}
        target_proj["customer_info"].update(record.get("customer_info", {}))
        
        # 6. 追加日志
        if "record_logs" not in target_proj: target_proj["record_logs"] = []
        target_proj["record_logs"].append(new_log_entry)
        
        target_proj["updated_at"] = now.isoformat()
        
        # 7. 写回文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(target_proj, f, ensure_ascii=False, indent=2)
            
        record_id = target_proj.get("id")

        # 8. 向量库同步
        if self.vector_service:
            try:
                self.vector_service.add_record(record_id, target_proj)
            except: pass
            
        return record_id, str(file_path)

    def get_all_opportunities(self):
        """获取所有商机记录 (扫描 data/opportunities 目录)"""
        all_data = []
        # 按修改时间倒序排列
        files = sorted(self.data_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
        
        for idx, fp in enumerate(files):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 动态注入一个临时 ID，方便 CLI 列表选择 (1, 2, 3...)
                    # 注意：这个 temp_id 仅用于当前 session 的显示，不做持久化
                    data["_temp_id"] = str(idx + 1)
                    data["_file_path"] = str(fp)
                    all_data.append(data)
            except: pass
        return all_data

    def get_opportunity_by_id(self, record_id):
        """
        根据 ID 获取单条商机。
        由于现在是文件存储，且 ID 可能是持久化的 timestamp ID，也可能是 CLI 的临时 ID。
        这里做一个兼容逻辑。
        """
        all_data = self.get_all_opportunities()
        
        # 1. 先尝试匹配 _temp_id (CLI 输入的 1, 2, 3)
        for item in all_data:
            if str(item.get("_temp_id")) == str(record_id):
                return item
        
        # 2. 如果没匹配到，尝试匹配真实的 id
        for item in all_data:
            if str(item.get("id")) == str(record_id):
                return item
                
        return None

    def query(self, sales_data, query_text: str):
        """
        GET/LIST: 根据销售数据和查询问题，生成专业回答
        
        Args:
            sales_data: 单个商机 JSON 或商机列表
            query_text: 用户的查询问题（从 extracted_content 获取）
            
        Returns:
            纯文本答案
        """
        if not self.validate_llm_config():
            return "配置错误，无法查询。"
        
        # 将 sales_data 转换为列表（便于统一处理）
        if isinstance(sales_data, dict):
            history_data = [sales_data]
        else:
            history_data = sales_data if isinstance(sales_data, list) else []
        
        return query_sales_data(query_text, history_data, self.api_key, self.endpoint_id)

    def generate_delete_warning(self, sales_data: dict) -> str:
        """
        DELETE: 在删除前生成友好但严肃的二次确认提示
        
        Args:
            sales_data: 要删除的商机 JSON
            
        Returns:
            纯文本的删除确认提示
        """
        if not self.validate_llm_config():
            # fallback: 直接返回基础提示
            proj_name = sales_data.get("project_opportunity", {}).get("project_name", "该商机")
            return f"您确定要删除商机 **{proj_name}** 吗？\n⚠️ 此操作不可逆，请谨慎确认。"
        
        # 调用 LLM 生成更自然的确认提示
        from volcenginesdkarkruntime import Ark
        from src.services.llm_service import load_prompt
        
        client = Ark(api_key=self.api_key)
        system_prompt = load_prompt("delete_confirmation")
        
        try:
            completion = client.chat.completions.create(
                model=self.endpoint_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(sales_data, ensure_ascii=False)},
                ],
                temperature=0.3,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            # 如果 LLM 调用失败，返回基础提示
            proj_name = sales_data.get("project_opportunity", {}).get("project_name", "该商机")
            return f"您确定要删除商机 **{proj_name}** 吗？\n⚠️ 此操作不可逆，请谨慎确认。"

    def delete_opportunity(self, record_id):
        """根据 ID 删除商机"""
        target = self.get_opportunity_by_id(record_id)
        if not target: return False
        
        file_path = Path(target.get("_file_path", ""))
        real_id = target.get("id")
        
        if file_path.exists():
            try:
                os.remove(file_path)
                # 向量库删除
                if self.vector_service and real_id:
                    self.vector_service.delete_record(real_id)
                return True
            except Exception as e:
                print(f"Delete error: {{e}}")
                return False
        return False

    def merge_draft_into_old(self, old_data: dict, draft_data: dict) -> dict:
        """
        [合并逻辑] 将笔记草稿合并到现有商机
        
        用于: 用户通过笔记(RECORD)最后执行CREATE，系统发现笔记涉及现有商机时触发
        流程: RECORD → handle_record() → (笔记积累) → CREATE → handle_create() 
             → process_commit_request() 检测到 linked → 调用本方法合并
        
        返回: 合并后的完整商机数据
        """
        merged = old_data.copy()
        
        # 逐字段合并，draft 优先级高（新数据覆盖旧数据）
        # 但保留 old_data 的关键字段（id, _file_path, created_at 等）
        for key, value in draft_data.items():
            if key not in ["id", "_file_path", "_temp_id", "created_at"]:
                merged[key] = value
        
        # 特殊处理嵌套的 project_opportunity 字段
        if "project_opportunity" in draft_data:
            if "project_opportunity" not in merged:
                merged["project_opportunity"] = {}
            merged["project_opportunity"].update(draft_data["project_opportunity"])
        
        return merged

    def overwrite_opportunity(self, new_data):
        """
        覆盖更新商机 (编辑模式)
        处理重命名逻辑：如果项目名变了，文件名也得跟着变。
        """
        old_file_path_str = new_data.get("_file_path")
        proj_name = new_data.get("project_opportunity", {}).get("project_name")
        if not proj_name: 
            return False
            
        new_file_path = self._get_safe_filename(proj_name)
        
        # 清理临时字段
        save_data = new_data.copy()
        save_data.pop("_temp_id", None)
        save_data.pop("_file_path", None)
        
        # --- 兼容性处理：确保 sales_rep 与 recorder 同步 ---
        if "sales_rep" in save_data and "recorder" not in save_data:
            # 如果修改了sales_rep，也同步到recorder
            save_data["recorder"] = save_data["sales_rep"]
        elif "recorder" in save_data and "sales_rep" not in save_data:
            # 反向：如果有recorder，确保sales_rep存在
            save_data["sales_rep"] = save_data["recorder"]
        
        save_data["updated_at"] = datetime.datetime.now().isoformat()
        
        try:
            # 1. 写入新文件
            with open(new_file_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            # 2. 如果文件名变了，把旧文件删了
            if old_file_path_str and Path(old_file_path_str).exists():
                old_file_path = Path(old_file_path_str)
                if old_file_path.resolve() != new_file_path.resolve():
                    os.remove(old_file_path)
            
            # 3. 向量库同步 (ID 保持不变，内容覆盖)
            if self.vector_service:
                self.vector_service.add_record(save_data.get("id"), save_data)
            return True
        except Exception as e:
            print(f"Update error: {e}")
            return False

    def judge_user_affirmative(self, text):
        """
        通用布尔意图判断器。
        判断用户是否表达了【肯定/同意/确认】的态度。
        """
        if not text: return False
        t = text.strip().lower()
        
        # 1. 否定快筛 (Fast Negative) - 只要沾边就拒，省流
        neg_kw = ["不", "否", "别", "取消", "no", "n", "cancel", "算了", "放弃"]
        # 如果是短语且包含否定词，直接 False
        if len(t) < 10 and any(k in t for k in neg_kw):
            return False

        # 2. 肯定快筛 (Fast Positive)
        aff_kw = ["是", "改", "覆盖", "对", "yes", "y", "ok", "确认", "好", "嗯", "妥", "存", "关联", "新建"]
        if len(t) < 10 and any(k in t for k in aff_kw):
            return True

        # 3. 复杂情况交给 LLM (AI 仲裁)
        from src.services.llm_service import judge_affirmative
        return judge_affirmative(text, self.api_key, self.endpoint_id)

    def detect_data_conflicts(self, old_data, new_data):
        """
        对比新旧数据，检测字段冲突。
        返回: list of (category, key, field_name, old_val, new_val)
        """
        conflicts = []
        
        # 字段名称映射 (用于显示)
        field_labels = {
            "budget": "预算金额",
            "opportunity_stage": "商机阶段",
            "timeline": "时间节点",
            "procurement_process": "采购流程",
            "payment_terms": "付款方式",
            "name": "客户姓名",
            "company": "客户公司",
            "role": "客户职位",
            "contact": "联系方式"
        }

        # 1. 检查 project_opportunity
        old_opp = old_data.get("project_opportunity", {})
        new_opp = new_data.get("project_opportunity", {})
        
        for k, v_new in new_opp.items():
            # 忽略非业务字段
            if k in ["is_new_project", "project_name"]: continue
            # 如果新值为空，不视为冲突（不覆盖）
            if not v_new or v_new == "null": continue
            
            v_old = old_opp.get(k)
            # 转字符串比较，忽略类型差异
            if str(v_new) != str(v_old) and v_old:
                label = field_labels.get(k, k)
                conflicts.append(("project_opportunity", k, label, v_old, v_new))

        # 2. 检查 customer_info
        old_cust = old_data.get("customer_info", {})
        new_cust = new_data.get("customer_info", {})
        
        for k, v_new in new_cust.items():
            if not v_new: continue
            v_old = old_cust.get(k)
            if str(v_new) != str(v_old) and v_old:
                label = field_labels.get(k, k)
                conflicts.append(("customer_info", k, label, v_old, v_new))

        return conflicts

    def resolve_target_interactive(self, content, current_context_id=None):
        """
        [核心业务逻辑] 目标解析流程
        统一封装 CLI/GUI 的查找逻辑：提取 -> 上下文检查 -> 搜索 -> 结果判定
        
        Returns:
            (target_obj, candidates_list, status_code)
            status_code: "found_by_context", "found_exact", "ambiguous", "not_found"
        """
        search_term = self.extract_search_term(content)
        
        # 1. 上下文模糊检查 (Vague Check)
        is_vague = not search_term or any(k in search_term.lower() for k in ["unknown", "记录", "项目", "修改", "更新", "内容"])
        
        if is_vague and current_context_id:
            target = self.get_opportunity_by_id(current_context_id)
            if target:
                return target, [], "found_by_context"
        
        # 2. 严格搜索
        final_term = search_term if search_term else content
        candidates = self.find_potential_matches(final_term)
        
        if not candidates:
            return None, [], "not_found"
            
        if len(candidates) == 1:
            target = self.get_opportunity_by_id(candidates[0]["id"])
            if target:
                return target, [], "found_exact"
        
        # 3. 多结果歧义
        return None, candidates, "ambiguous"

    def process_list_request(self, content):
        """
        [核心业务逻辑] 处理商机列表查询
        """
        search_term = self.extract_search_term(content) or ""
        clean_term = search_term.upper().replace("`", "").replace("'", "").replace('"', "")
        
        is_full_list = not clean_term or clean_term in ["ALL", "未知", "UNKNOWN", "商机", "项目", "列表", "全部", "所有"]
        
        if is_full_list:
            results = self.list_opportunities()
        else:
            def simple_filter(data): 
                return search_term.lower() in json.dumps(data, ensure_ascii=False).lower()
            results = self.list_opportunities(simple_filter)
            
        return {
            "results": results,
            "message": f"📋 找到 {len(results)} 条商机" if results else "暂未找到相关商机。",
            "search_term": search_term if not is_full_list else "全部"
        }

    def get_missing_fields_notification(self, data):
        """
        [统一话术逻辑] 生成缺失字段的通知文本
        """
        missing = self.get_missing_fields(data)
        if not missing:
            return "✅ 信息完整。确认无误请执行保存。"
            
        names = [v[0] for v in missing.values()]
        return f"⚠️ 当前草稿缺失关键信息：**{', '.join(names)}**。\n您可以直接在对话框输入补充（如“预算50万”），或直接执行保存。"

    # --- V3.0 笔记暂存与提交逻辑 ---

    def add_to_note_buffer(self, content):
        """将一段录入内容添加到笔记暂存区"""
        polished = self.polish(content)
        self.note_buffer.append(polished)
        return polished

    def clear_note_buffer(self):
        """清空笔记暂存区"""
        self.note_buffer = []

    def process_commit_request(self, project_name_hint=None):
        """
        [核心业务逻辑] 将暂存区的笔记正式提交到商机。
        1. 尝试锁定目标商机 (根据 hint 或笔记内容)
        2. 调用 Architect Analyze 进行结构化提取/合并
        3. 返回结果包
        """
        if not self.note_buffer:
            return {"status": "error", "message": "笔记暂存区为空，请先录入一些内容。"}

        # 1. 锁定目标
        target_obj = None
        if project_name_hint:
            # 这里的 hint 可能是从意图识别里拿出来的 "RECORD" content
            res_target, candidates, status = self.resolve_target_interactive(project_name_hint)
            if status in ["found_exact", "found_by_context"]:
                target_obj = res_target

        # 2. 如果没锁定，先做一次初步分析看看笔记里提到了哪个项目
        if not target_obj:
            # 临时生成一个草稿来探探路 (取前 3 条笔记)
            preview = architect_analyze(self.note_buffer[:3], self.api_key, self.endpoint_id, recorder=self.default_recorder)
            if preview:
                extracted_name = preview.get("project_opportunity", {}).get("project_name")
                if extracted_name:
                    res_target, candidates, status = self.resolve_target_interactive(extracted_name)
                    if status in ["found_exact", "found_by_context"]:
                        target_obj = res_target

        # 3. 调用销售架构师进行最终处理
        # 传入 target_obj (如果有) 进行合并，否则为新建
        result_json = architect_analyze(
            self.note_buffer, 
            self.api_key, 
            self.endpoint_id, 
            original_data=target_obj, 
            recorder=self.default_recorder
        )

        if not result_json:
            return {"status": "error", "message": "AI 提交处理失败。"}

        # 4. 查重判定 (如果是新建模式，可能还需要检查是否有同名项目)
        status = "new"
        linked_target = None
        if target_obj:
            status = "linked"
            linked_target = {"id": target_obj["id"], "name": target_obj.get("project_name", "未知")}
        else:
            # 即使 architect 没拿到 original_json，它可能输出了一个已存在的项目名
            # 这里再做最后一层保险
            p_name = result_json.get("project_opportunity", {}).get("project_name")
            if p_name:
                matches = self.find_potential_matches(p_name)
                for m in matches:
                    if m["name"].strip().lower() == p_name.strip().lower():
                        linked_target = m
                        status = "linked"
                        result_json["id"] = m["id"]
                        break

        return {
            "status": status,
            "draft": result_json,
            "linked_target": linked_target,
            "missing_fields": self.get_missing_fields(result_json)
        }