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
    调用豆包大模型，提炼销售内容
    """
    # 初始化客户端
    client = Ark(api_key=api_key)

    try:
        # 加载提示词：老大哥把Prompt分家了，方便以后调教
        system_prompt = load_prompt("analyze_sales")
    except Exception as e:
        print(f"[ERROR] 提示词加载失败: {e}")
        return None

    print("正在连接豆包大模型...")
    
    try:
        completion = client.chat.completions.create(
            model=endpoint_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            # 这里的参数可以微调，temperature 低一点让它更严谨
            temperature=0.1, 
        )
        
        # 获取返回内容
        response_content = completion.choices[0].message.content.strip()
        
        # 尝试清洗可能存在的 Markdown 标记 (老大哥的经验之谈：有时候模型不听话)
        if response_content.startswith("```json"):
            response_content = response_content[7:]
        if response_content.endswith("```"):
            response_content = response_content[:-3]
            
        return json.loads(response_content)

    except json.JSONDecodeError:
        print(f"解析失败，模型返回的不是标准 JSON: {response_content}")
        return None
    except Exception as e:
        print(f"调用豆包出错了: {e}")
        return None
