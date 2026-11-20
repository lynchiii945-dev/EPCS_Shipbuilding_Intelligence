# -*- coding: utf-8 -*-
"""规则建议。只根据正文给出待审核结构，不调用外部模型，也不看文件名。"""
import re

_CLASSES = (
    ("合同", "合同", 0.8),
    ("周报", "周报", 0.8),
    ("图纸", "图纸", 0.8),
    ("会议", "会议", 0.75),
    ("纪要", "会议", 0.75),
    ("邮件", "邮件", 0.7),
    ("规格", "规格书", 0.7),
)
_CODE = re.compile(r"项目编号\s*[:：]\s*([A-Za-z][A-Za-z0-9-]{2,})")
_NAME = re.compile(r"项目名称\s*[:：]\s*(.+)")
_MATTER = re.compile(r"^(问题|风险|待办|决定|行动项)\s*[:：]\s*(.+)$")


def propose(text, *, readable):
    """返回待审核建议。无法阅读时只有一条未解析记录。"""
    if not readable:
        return [{
            "candidate_type": "PENDING_PARSE",
            "info_nature": "AI_INFERENCE",
            "confidence": 0.0,
            "raw_text": None,
            "payload": {
                "understood": False,
                "reason": "格式未解析，没有分类、知识或事项",
            },
        }]
    suggestions = [_classification(text)]
    if text.strip():
        suggestions.append({
            "candidate_type": "NORMALIZED_TEXT",
            "info_nature": "PROPOSAL",
            "confidence": 1.0,
            "raw_text": text,
            "payload": {
                "locator": "full",
                "note": "仅规范化换行和行尾空白，不是模型改写",
            },
        })
    project = _project_fact(text)
    if project:
        suggestions.append(project)
    suggestions.extend(_knowledge(text))
    suggestions.extend(_matters(text))
    return suggestions


def _classification(text):
    label, confidence = "未分类", 0.4
    for keyword, name, score in _CLASSES:
        if keyword in text:
            label, confidence = name, score
            break
    if "个人" in text:
        zone, zone_confidence = "personal", 0.7
    else:
        zone, zone_confidence = "company", 0.45
    return {
        "candidate_type": "CLASSIFICATION",
        "info_nature": "PROPOSAL",
        "confidence": confidence,
        "raw_text": None,
        "payload": {
            "label": label,
            "zone": zone,
            "zone_confidence": zone_confidence,
            "locator": "full",
        },
    }


def _project_fact(text):
    code = None
    name = None
    code_line = None
    name_line = None
    raw_lines = []
    for number, line in enumerate(text.split("\n"), 1):
        code_match = _CODE.search(line)
        if code_match and code is None:
            code = code_match.group(1)
            code_line = number
            raw_lines.append(line.strip())
        name_match = _NAME.search(line)
        if name_match and name is None:
            name = name_match.group(1).strip()
            name_line = number
            raw_lines.append(line.strip())
    if code is None and name is None:
        return None
    if code and name:
        confidence = 0.9
    elif code:
        confidence = 0.85
    else:
        confidence = 0.8
    return {
        "candidate_type": "PROJECT_FACT",
        "info_nature": "PROPOSAL",
        "confidence": confidence,
        "raw_text": "\n".join(raw_lines),
        "payload": {
            "project_code": code,
            "name": name,
            "locator": "line:%d" % (code_line or name_line),
            "eligible": bool(code and name),
        },
    }


def _knowledge(text):
    lines = text.split("\n")
    found = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("#"):
            index += 1
            continue
        title = line.lstrip("#").strip()
        body = []
        nxt = index + 1
        while nxt < len(lines) and not lines[nxt].startswith("#"):
            body.append(lines[nxt])
            nxt += 1
        summary = "\n".join(body).strip()
        if title:
            found.append({
                "candidate_type": "KNOWLEDGE",
                "info_nature": "PROPOSAL",
                "confidence": 0.6,
                "raw_text": (line + "\n" + summary).strip(),
                "payload": {
                    "title": title,
                    "summary": summary[:240],
                    "locator": "line:%d" % (index + 1),
                },
            })
        index = nxt
    return found


def _matters(text):
    found = []
    for number, line in enumerate(text.split("\n"), 1):
        match = _MATTER.match(line.strip())
        if not match:
            continue
        found.append({
            "candidate_type": "BUSINESS_MATTER",
            "info_nature": "PROPOSAL",
            "confidence": 0.7,
            "raw_text": line.strip(),
            "payload": {
                "kind": match.group(1),
                "text": match.group(2).strip(),
                "locator": "line:%d" % number,
                "note": "只保留为待审核建议，不写入 issue/risk/task",
            },
        })
    return found
