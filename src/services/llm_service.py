"""
LinkSell LLM 服务 (LLM Service)

职责：
- 封装所有与大语言模型 (Doubao) 的交互接口
- 动态加载并管理 Prompt 模板
- 提供文本润色、意图识别、结构化提取、RAG 问答等原子能力

特点：
- **Prompt Management**: 统一从 config/prompts 目录加载模板，支持 fallback 机制
- **Structured Output**: 强依赖 JSON 输出格式，便于系统后续处理
- **Architect Mode**: 集成"销售架构师"模型，处理复杂的多轮笔记合并逻辑
"""

import json
import os
from pathlib import Path
from volcenginesdkarkruntime import Ark

def load_prompt(prompt_name: str, fallback: str = None) -> str:
    """
    [工具] 从 config/prompts 目录加载提示词
    
    参数:
    - prompt_name: 模板文件名 (无需后缀)
    - fallback: 备用文件名 (如果主文件缺失)
    """
    # 自动补全后缀
    if not prompt_name.endswith(".txt"):
        prompt_name += ".txt"
        
    prompt_path = Path("config") / "prompts" / prompt_name
    
    # 1. 尝试加载主 Prompt
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    
    # 2. 尝试加载备用 Prompt
    if fallback:
        if not fallback.endswith(".txt"):
            fallback += ".txt"
        fallback_path = Path("config") / "prompts" / fallback
        if fallback_path.exists():
            with open(fallback_path, "r", encoding="utf-8") as f:
                return f.read().strip()
    
    # 3. 严重错误：找不到任何 Prompt
    raise FileNotFoundError(f"【架构禁忌】: 严禁在代码中硬编码 Prompt！请创建文件: {prompt_path}" + 
                           (f" 或 fallback {fallback_path}" if fallback else ""))

def polish_text(content: str, api_key: str, endpoint_id: str) -> str:
    """
    [LLM] 文本润色
    将口语化/杂乱的语音转写文本转换为规范的书面文本。
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("polish_text")

    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=0.2, # 低随机性，保持语义准确
        )
        return completion.choices[0].message.content.strip()
    except:
        return content

def update_sales_data(original_data: dict, user_instruction: str, api_key: str, endpoint_id: str) -> dict:
    """
    [LLM] 智能修改
    根据用户的自然语言指令 (如"把预算改成50万") 修改销售记录 JSON。
    (注：V3.0 已更多采用 architect_analyze 进行统一处理，本函数保留用于简单场景)
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("update_sales")

    payload = {
        "original_json": original_data,
        "user_instruction": user_instruction
    }

    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.1,
        )
        raw_content = completion.choices[0].message.content
        
        # 清洗 Markdown 代码块标记
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
             raw_content = raw_content.split("```")[1].split("```")[0].strip()
        return json.loads(raw_content)
    except:
        return original_data

def judge_affirmative(user_input: str, api_key: str, endpoint_id: str) -> bool:
    """
    [LLM] 意图判断 (Yes/No)
    判断用户的输入是否表达了“肯定/同意”的意图。
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("judge_save")
    
    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.1, 
        )
        content = completion.choices[0].message.content.strip().upper()
        return "TRUE" in content
    except:
        return False

def summarize_text(content: str, api_key: str, endpoint_id: str) -> str:
    """
    [LLM] 文本摘要
    将超长文本提炼为 500 字以内的摘要，用于生成商机小记。
    """
    client = Ark(api_key=api_key)
    system_prompt_template = load_prompt("summarize_note")
    
    # 简单的模板替换
    system_prompt = system_prompt_template.replace("{{text}}", content)

    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请开始提炼。"},
            ],
            temperature=0.3,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        # 容错：如果报错，直接截断返回原始文本
        return content[:500] + "..."

def classify_intent(text: str, api_key: str, endpoint_id: str) -> dict:
    """
    [LLM] 意图分类
    判断用户的意图并提取内容，返回 {"intent": "...", "content": "..."}。
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("classify_intent")
    
    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.1, 
        )
        response = completion.choices[0].message.content.strip()
        
        # 1. 尝试解析 JSON
        try:
            result = json.loads(response)
            if isinstance(result, dict):
                intent = result.get("intent", "RECORD").upper()
                content = result.get("content", text)
                return {"intent": intent, "content": content}
        except:
            pass
        
        # 2. JSON 解析失败，尝试关键词匹配兜底
        response_upper = response.upper()
        intent = "RECORD"  # 默认值
        for keyword in ["CREATE", "RECORD", "LIST", "GET", "REPLACE", "MERGE", "DELETE", "OTHER"]:
            if keyword in response_upper:
                intent = keyword
                break
        
        return {"intent": intent, "content": text}
        
    except Exception as e:
        return {"intent": "RECORD", "content": text}

def query_sales_data(query: str, history_data: list, api_key: str, endpoint_id: str) -> str:
    """
    [LLM] 销售问答 (RAG)
    根据提供的历史商机数据回答用户的查询。
    """
    client = Ark(api_key=api_key)
    system_prompt_template = load_prompt("query_sales")
    
    # 注入上下文 (取最近 10 条防止 Context Window 溢出)
    context = json.dumps(history_data[-10:], ensure_ascii=False, indent=2)
    
    system_prompt = system_prompt_template.replace("{{context}}", context).replace("{{query}}", query)

    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"查询出错啦：{e}"

def architect_analyze(raw_notes: list, api_key: str, endpoint_id: str, original_data: dict = None, recorder: str = "未知", current_time: str = None) -> dict:
    """
    [核心逻辑] 销售架构师 (Sales Architect)
    LinkSell 的核心智能引擎。负责接收原始笔记，根据当前上下文 (original_data)，
    输出标准的结构化商机 JSON。支持新建、追加、更新等复杂逻辑。
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("sales_architect")
    
    if not current_time:
        import datetime
        current_time = datetime.datetime.now().isoformat()

    # 构建完整的上下文包
    payload = {
        "original_json": original_data, # 如果是新建，这里为 None
        "raw_notes": raw_notes,         # 用户的多条笔记片段
        "current_time": current_time,
        "recorder": recorder
    }

    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.1, 
        )
        
        raw_content = completion.choices[0].message.content
        
        # 鲁棒性处理：提取 Markdown 中的 JSON
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
             raw_content = raw_content.split("```")[1].split("```")[0].strip()
             
        return json.loads(raw_content)
    except Exception as e:
        print(f"LLM Architect Error: {e}")
        return None