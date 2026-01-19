import json
import os
from pathlib import Path
from volcenginesdkarkruntime import Ark

def load_prompt(prompt_name: str, fallback: str = None) -> str:
    """
    从 config/prompts 目录加载提示词
    支持 fallback 机制：如果主文件不存在，尝试使用备选文件
    """
    # 允许传入带有 .txt 后缀或不带后缀的文件名
    if not prompt_name.endswith(".txt"):
        prompt_name += ".txt"
        
    prompt_path = Path("config") / "prompts" / prompt_name
    
    # 如果主文件存在，直接使用
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    
    # 如果指定了 fallback，尝试使用 fallback
    if fallback:
        if not fallback.endswith(".txt"):
            fallback += ".txt"
        fallback_path = Path("config") / "prompts" / fallback
        if fallback_path.exists():
            with open(fallback_path, "r", encoding="utf-8") as f:
                return f.read().strip()
    
    # 两个都找不到，抛出错误
    raise FileNotFoundError(f"【架构禁忌】: 严禁在代码中硬编码 Prompt！请创建文件: {prompt_path}" + 
                           (f" 或 fallback {fallback_path}" if fallback else ""))

def polish_text(content: str, api_key: str, endpoint_id: str) -> str:
    """
    使用 LLM 将口语化/杂乱文本转换为规范的书面文本。
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
            temperature=0.2,
        )
        return completion.choices[0].message.content.strip()
    except:
        return content

def update_sales_data(original_data: dict, user_instruction: str, api_key: str, endpoint_id: str) -> dict:
    """
    使用 LLM 根据用户的自然语言指令修改销售记录 JSON。
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
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
             raw_content = raw_content.split("```")[1].split("```")[0].strip()
        return json.loads(raw_content)
    except:
        return original_data

def judge_affirmative(user_input: str, api_key: str, endpoint_id: str) -> bool:
    """
    使用 LLM 判断用户的输入是否表达了“肯定/同意”的意图。
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
    将超长文本提炼为 500 字以内的摘要。
    """
    client = Ark(api_key=api_key)
    system_prompt_template = load_prompt("summarize_note")
    
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
        # 如果报错，截断返回
        return content[:500] + "..."

def classify_intent(text: str, api_key: str, endpoint_id: str) -> dict:
    """
    判断用户的意图并提取内容，返回 {"intent": "...", "content": "..."}。
    意图可以是：CREATE, LIST, GET, UPDATE, DELETE, 或 OTHER。
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
        # LLM 应该返回 JSON 格式
        response = completion.choices[0].message.content.strip()
        
        # 尝试解析 JSON
        try:
            result = json.loads(response)
            # 确保意图是大写
            if isinstance(result, dict):
                intent = result.get("intent", "RECORD").upper()
                content = result.get("content", text)
                return {"intent": intent, "content": content}
        except:
            pass
        
        # 如果 JSON 解析失败，尝试从纯文本提取 (V3.0 置换版)
        response_upper = response.upper()
        intent = "RECORD"  # 默认值改为记录暂存
        for keyword in ["CREATE", "RECORD", "LIST", "GET", "UPDATE", "DELETE", "OTHER"]:
            if keyword in response_upper:
                intent = keyword
                break
        
        return {"intent": intent, "content": text}
        
    except Exception as e:
        # 默认走记录暂存逻辑比较保险
        return {"intent": "RECORD", "content": text}

def query_sales_data(query: str, history_data: list, api_key: str, endpoint_id: str) -> str:
    """
    根据历史数据回答用户的查询。
    """
    client = Ark(api_key=api_key)
    system_prompt_template = load_prompt("query_sales")
    
    # 将 JSON 历史数据截断或处理，防止 Token 溢出（暂时简单处理）
    context = json.dumps(history_data[-10:], ensure_ascii=False, indent=2) # 取最近10条
    
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
    [V3.0 核心] 使用销售架构师 Prompt 处理笔记。
    支持新建或基于已有数据的追加更新。
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("sales_architect")
    
    if not current_time:
        import datetime
        current_time = datetime.datetime.now().isoformat()

    payload = {
        "original_json": original_data,
        "raw_notes": raw_notes,
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
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
             raw_content = raw_content.split("```")[1].split("```")[0].strip()
             
        return json.loads(raw_content)
    except Exception as e:
        print(f"LLM Architect Error: {e}")
        return None
