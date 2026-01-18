import configparser
import json
import datetime
import re
import os
import glob
from pathlib import Path
from src.services.llm_service import (
    analyze_text, refine_sales_data, polish_text, 
    update_sales_data, classify_intent, query_sales_data, summarize_text
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

    def analyze(self, text):
        if not self.validate_llm_config():
            raise ValueError("LLM Configuration Invalid")
        return analyze_text(text, self.api_key, self.endpoint_id)

    def identify_intent(self, text):
        """识别意图：CREATE, LIST, GET, UPDATE, DELETE, OTHER"""
        if not self.validate_llm_config():
            return "CREATE"
        
        # 调用 LLM 进行分类
        intent = classify_intent(text, self.api_key, self.endpoint_id)
        
        # 严格规范化
        valid_intents = ["CREATE", "LIST", "GET", "UPDATE", "DELETE", "OTHER"]
        if intent not in valid_intents:
            # 尝试关键词补救
            if any(k in text for k in ["查", "找", "看", "哪些", "搜索"]): return "LIST"
            if any(k in text for k in ["删", "移除"]): return "DELETE"
            if any(k in text for k in ["改", "更新", "换"]): return "UPDATE"
            return "CREATE"
            
        # OTHER 的人工复核：防止对业务指令的误杀
        if intent == "OTHER":
            # 业务核心词汇列表
            biz_keywords = ["项目", "商机", "单子", "客户", "聊", "聊过", "谈", "预算", "进度", "跟进", "详情", "档案"]
            if len(text) > 8 or any(k in text for k in biz_keywords):
                # 如果包含业务词，默认转为查询意图 (LIST) 比较稳妥，让后续逻辑去搜
                return "LIST"
                
        return intent

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
            return keyword.lower() in p_name.lower()
            
        matches = []
        for p in self.list_opportunities(keyword_filter):
            p_name = p.get("project_opportunity", {}).get("project_name", "")
            if not p_name: p_name = p.get("project_name", "")
            matches.append({
                "name": p_name,
                "sales_rep": p.get("sales_rep", "未知")
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
            candidates[m["name"]] = {"name": m["name"], "source": "关键字匹配", "sales_rep": m["sales_rep"]}

        # 2. 向量搜索 (语义近似)
        if self.vector_service:
            vec_matches = self.vector_service.search_projects(project_name)
            for vm in vec_matches:
                p_name = vm["project_name"]
                # 只有当关键字没搜到，且名字不完全一样时才加进去（避免重复）
                if p_name not in candidates:
                    candidates[p_name] = {"name": p_name, "source": "语义相似", "sales_rep": "未知"} # 向量库暂未返回sales_rep，简化处理

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

    def refine(self, data, supplements):
        return refine_sales_data(data, supplements, self.api_key, self.endpoint_id)

    def update(self, data, instruction):
        updated_data = update_sales_data(data, instruction, self.api_key, self.endpoint_id)
        
        # --- 强一致性同步逻辑 ---
        # 确保 project_name 在各处保持一致
        new_opp = updated_data.get("project_opportunity", {})
        inner_name = new_opp.get("project_name")
        outer_name = updated_data.get("project_name")
        
        # 如果内部改了，同步到外部
        if inner_name and inner_name != outer_name:
            updated_data["project_name"] = inner_name
        # 如果外部改了（且内部没改或为空），同步到内部
        elif outer_name and outer_name != inner_name:
            if "project_opportunity" not in updated_data: updated_data["project_opportunity"] = {}
            updated_data["project_opportunity"]["project_name"] = outer_name
            
        # --- [关键修复]：保留系统级元数据 ---
        # LLM 返回的数据里没有这些私有字段，必须从原数据拷过来！
        meta_keys = ["id", "_file_path", "_temp_id", "created_at", "record_logs", "updated_at"]
        for k in meta_keys:
            if k in data and k not in updated_data:
                updated_data[k] = data[k]
            
        return updated_data

    def save(self, record, raw_content=""):
        """
        保存商机信息：每个商机一个独立 JSON 文件。
        raw_content: polish_text.txt 润色后的原始文字。
        """
        # 1. 准备内容：二选一原则
        polished_text = raw_content if raw_content else record.get("summary", "")
        
        # 核心逻辑：如果润色文本 > 500字，则生成摘要作为最终内容；否则直接用润色文本
        if len(polished_text) > 500:
            final_content = summarize_text(polished_text, self.api_key, self.endpoint_id)
        else:
            final_content = polished_text
        
        now = datetime.datetime.now()
        proj_info = record.get("project_opportunity", {})
        proj_name = proj_info.get("project_name", "未命名项目")
        
        # 2. 确定文件路径
        file_path = self._get_safe_filename(proj_name)
        
        # 3. 读取现有文件或创建新结构
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                try: target_proj = json.load(f)
                except: target_proj = {}
            is_new = False
        else:
            target_proj = {
                "id": str(int(datetime.datetime.now().timestamp())), # 临时生成唯一ID
                "created_at": now.isoformat(),
                "record_logs": []
            }
            is_new = True

        # 4. 构造本次记录的小记 (必须包含时间、记录者)
        new_log_entry = {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "recorder": self.default_recorder,
            "content": final_content  # 最终入库内容（摘要或原话）
        }

        # 5. 更新数据
        target_proj.update(record) 
        if "project_opportunity" not in target_proj: target_proj["project_opportunity"] = {}
        target_proj["project_opportunity"].update(proj_info)
        
        if "customer_info" not in target_proj: target_proj["customer_info"] = {}
        target_proj["customer_info"].update(record.get("customer_info", {}))
        
        if "record_logs" not in target_proj: target_proj["record_logs"] = []
        target_proj["record_logs"].append(new_log_entry)
        
        target_proj["updated_at"] = now.isoformat()
        
        # 6. 写回文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(target_proj, f, ensure_ascii=False, indent=2)
            
        record_id = target_proj.get("id")

        # 7. 向量库同步 (使用 upsert 确保是最新的)
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