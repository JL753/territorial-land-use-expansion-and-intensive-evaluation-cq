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
