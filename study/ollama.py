import json
from urllib.request import Request, urlopen


def choose_evidence(model, question, lines):
    request = Request("http://127.0.0.1:11434/api/chat", data=json.dumps({
        "model": model, "stream": False, "think": False,
        "format": {"type": "object", "properties": {"lines": {
            "type": "array", "items": {"type": "integer", "minimum": 1, "maximum": len(lines)},
            "minItems": 1, "maxItems": 4,
        }}, "required": ["lines"]},
        "options": {"temperature": 0, "num_predict": 96},
        "messages": [
            {"role": "system", "content": '从计算依据中选择最相关的行编号，返回 {"lines":[编号]}。'},
            {"role": "user", "content": question + "\n" + "\n".join(
                f"{index}. {line}" for index, line in enumerate(lines, 1)
            )},
        ],
    }).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=45) as response:
        raw = json.load(response)["message"]["content"]
    chosen = json.loads(raw)["lines"]
    if not isinstance(chosen, list) or not 1 <= len(chosen) <= 4 or any(
        type(index) is not int or not 1 <= index <= len(lines) for index in chosen
    ):
        raise ValueError("Invalid evidence selection")
    return "\n".join(lines[index - 1] for index in sorted({1, *chosen}))


def generate_answer(model, question, evidence, base_url="http://127.0.0.1:11434"):
    request = Request(base_url.rstrip("/") + "/api/chat", data=json.dumps({
        "model": model,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.15, "num_predict": 700},
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是山城地研的 GIS 研究助手。只能依据用户提供的研究证据回答。"
                    "不得编造年份、数值、来源或数据质量；证据不足时明确说明。"
                    "区分实测统计、模型计算和模拟结果；相关性不得表述为因果关系。"
                    "用简洁中文回答，并在关键数字后标明单位。"
                ),
            },
            {"role": "user", "content": f"研究问题：{question}\n\n可用证据：\n{evidence}"},
        ],
    }).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    answer = payload.get("message", {}).get("content", "").strip()
    if not answer:
        raise ValueError("Ollama returned an empty answer.")
    return answer
