import json
import os
from pathlib import Path
from volcenginesdkarkruntime import Ark

def load_prompt(prompt_name: str) -> str:
    """
    从 config/prompts 目录加载提示词
    """
    # 允许传入带有 .txt 后缀或不带后缀的文件名
    if not prompt_name.endswith(".txt"):
        prompt_name += ".txt"
        
    prompt_path = Path("config") / "prompts" / prompt_name
    if not prompt_path.exists():
        # 这里给出一个硬核的报错，提醒开发者必须创建文件
        raise FileNotFoundError(f"【架构禁忌】: 严禁在代码中硬编码 Prompt！请创建文件: {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def analyze_text(content: str, api_key: str, endpoint_id: str):
    """
    调用火山引擎 Ark Runtime (Doubao) 分析文本。
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("analyze_sales")

    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=0.3, 
        )
        
        raw_content = completion.choices[0].message.content
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
             raw_content = raw_content.split("```")[1].split("```")[0].strip()
             
        return json.loads(raw_content)
    except Exception as e:
        print(f"[bold red]LLM 分析失败：{e}[/bold red]")
        return None

def refine_sales_data(original_data: dict, user_supplements: dict, api_key: str, endpoint_id: str):
    """
    使用 LLM 校验并合并用户补录的信息。
    """
    if not user_supplements:
        return original_data

    client = Ark(api_key=api_key)
    system_prompt = load_prompt("refine_sales")

    payload = {
        "original_json": original_data,
        "user_supplements": user_supplements
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

def classify_intent(text: str, api_key: str, endpoint_id: str) -> str:
    """
    判断用户的意图：ANALYZE, QUERY, 或 OTHER。
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
        content = completion.choices[0].message.content.strip().upper()
        if "ANALYZE" in content: return "ANALYZE"
        if "QUERY" in content: return "QUERY"
        return "OTHER"
    except:
        return "ANALYZE" # 默认走分析逻辑

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

def is_sales_content(text: str, api_key: str, endpoint_id: str) -> bool:
    """
    判断输入内容是否为销售对话或业务相关记录。
    """
    client = Ark(api_key=api_key)
    system_prompt = load_prompt("classify_content")
    
    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.1, 
        )
        content = completion.choices[0].message.content.strip().upper()
        return "TRUE" in content
    except:
        return True
