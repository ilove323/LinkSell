import json
from pathlib import Path
from volcenginesdkarkruntime import Ark

def load_prompt(prompt_name: str) -> str:
    """
    从 config/prompts 目录加载提示词
    """
    prompt_path = Path(f"config/prompts/{prompt_name}.txt")
    if not prompt_path.exists():
        raise FileNotFoundError(f"提示词文件没找着啊：{prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def analyze_text(content: str, api_key: str, endpoint_id: str):
    """
    调用火山引擎 Ark Runtime (Doubao) 分析文本。
    """
    # (Existing code for analyze_text...)
    client = Ark(api_key=api_key)
    
    # 加载 Prompt
    try:
        with open("config/prompts/analyze_sales.txt", "r", encoding="utf-8") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        print("[bold red]错误：找不到 Prompt 文件 config/prompts/analyze_sales.txt[/bold red]")
        return None

    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=0.3, # 降低随机性，保证格式稳定
        )
        
        raw_content = completion.choices[0].message.content
        
        # 清洗 Markdown 标记
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
             raw_content = raw_content.split("```")[1].split("```")[0].strip()
             
        return json.loads(raw_content)

    except Exception as e:
        print(f"[bold red]LLM 调用失败：{e}[/bold red]")
        return None

def refine_sales_data(original_data: dict, user_supplements: dict, api_key: str, endpoint_id: str):
    """
    使用 LLM 校验并合并用户补录的信息。
    """
    if not user_supplements:
        return original_data

    client = Ark(api_key=api_key)
    
    try:
        with open("config/prompts/refine_sales.txt", "r", encoding="utf-8") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        print("[bold red]错误：找不到 Prompt 文件 config/prompts/refine_sales.txt[/bold red]")
        return original_data

    # 构造请求数据
    payload = {
        "original_json": original_data,
        "user_supplements": user_supplements
    }

    try:
        print("[dim]正在请求 AI 校验补录数据...[/dim]")
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.1, # 极低随机性，只做清洗
        )
        
        raw_content = completion.choices[0].message.content
        
        # 清洗 Markdown 标记
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
             raw_content = raw_content.split("```")[1].split("```")[0].strip()
             
        return json.loads(raw_content)

    except Exception as e:
        print(f"[bold red]校验服务调用失败，将保留原始输入：{e}[/bold red]")
        # Fallback: 直接合并，不做校验
        updated_data = original_data.copy()
        opp = updated_data.get("project_opportunity", {})
        for k, v in user_supplements.items():
            opp[k] = v
        updated_data["project_opportunity"] = opp
        return updated_data

