# -*- coding: utf-8 -*-
"""阅读器。文本和 Markdown 直接读。PDF 只抽取能解码的文本流。

抽不出文本或其他格式时返回未解析，不编造摘要。
"""
import re
import zlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadResult:
    kind: str
    text: str
    note: str


def normalize_text(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip("\n")


def read_bytes(data, suffix):
    suffix = suffix.lower()
    if suffix in (".md", ".markdown", ".txt"):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return ReadResult("UNPARSED", "", "待解析：文本不是 UTF-8")
        kind = "MARKDOWN" if suffix in (".md", ".markdown") else "TEXT"
        return ReadResult(kind, normalize_text(text), "")
    if suffix == ".pdf":
        extracted = extract_pdf_text(data)
        if extracted.strip():
            return ReadResult("PDF", normalize_text(extracted), "")
        return ReadResult("UNPARSED", "", "待解析：PDF 中没有抽出文本")
    return ReadResult("UNPARSED", "", "待解析：该格式本切片不阅读")


def extract_pdf_text(data):
    """从 PDF 内容流抽出字面字符串。支持未压缩流和 FlateDecode。"""
    if b"%PDF" not in data[:1024]:
        return ""
    pieces = []
    for match in re.finditer(br"stream\r?\n(.*)\r?\nendstream", data, re.S):
        raw = match.group(1)
        header = data[max(0, match.start() - 400):match.start()]
        chunk = raw
        if b"FlateDecode" in header:
            try:
                chunk = zlib.decompress(raw)
            except zlib.error:
                continue
        pieces.extend(_pdf_literals(chunk))
    return "\n".join(piece for piece in pieces if piece.strip())


def _pdf_literals(chunk):
    text = chunk.decode("latin1")
    found = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "(":
            index += 1
            buf = []
            depth = 1
            while index < length and depth:
                current = text[index]
                if current == "\\":
                    index += 1
                    if index < length:
                        buf.append(_pdf_escape(text[index]))
                    index += 1
                    continue
                if current == "(":
                    depth += 1
                    buf.append(current)
                elif current == ")":
                    depth -= 1
                    if depth:
                        buf.append(current)
                else:
                    buf.append(current)
                index += 1
            found.append("".join(buf))
            continue
        if char == "<" and index + 1 < length and text[index + 1] != "<":
            end = text.find(">", index + 1)
            if end < 0:
                break
            found.append(_pdf_hex(text[index + 1:end]))
            index = end + 1
            continue
        index += 1
    return found


def _pdf_escape(char):
    return {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "b": "\b",
        "f": "\f",
        "(": "(",
        ")": ")",
        "\\": "\\",
    }.get(char, char)


def _pdf_hex(raw):
    compact = re.sub(r"\s+", "", raw)
    if len(compact) % 2:
        compact += "0"
    try:
        blob = bytes.fromhex(compact)
    except ValueError:
        return ""
    if len(blob) >= 2 and blob[0] == 0xFE and blob[1] == 0xFF:
        return blob[2:].decode("utf-16-be", errors="replace")
    if blob and blob[0] > 127:
        try:
            return blob.decode("utf-16-be")
        except UnicodeDecodeError:
            return blob.decode("latin1", errors="replace")
    return blob.decode("latin1", errors="replace")
