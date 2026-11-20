# -*- coding: utf-8 -*-
"""入口边界与归档复制。复制后立刻核对 SHA-256，失败则删掉半成品。"""
import hashlib
import os
import shutil
from pathlib import Path


class HashMismatch(Exception):
    def __init__(self, expected, actual):
        super().__init__("归档副本 SHA-256 不一致: %s != %s" % (expected, actual))
        self.expected = expected
        self.actual = actual


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def is_inside(path, root):
    """解析符号链接后，判断路径是否仍在 root 之内。"""
    resolved = Path(path).resolve()
    base = Path(root).resolve()
    if resolved == base:
        return True
    return base in resolved.parents


def safe_filename(name):
    cleaned = Path(name).name
    if cleaned in ("", ".", ".."):
        return "unnamed"
    return cleaned


def copy_and_verify(src, dest, expected_sha):
    """复制到临时文件，校验通过后才换到正式归档名。不改来源文件。"""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    try:
        shutil.copy2(src, partial)
        actual = sha256_file(partial)
        if actual != expected_sha:
            raise HashMismatch(expected_sha, actual)
        os.replace(partial, dest)
        if sha256_file(dest) != expected_sha:
            raise HashMismatch(expected_sha, sha256_file(dest))
        if sha256_file(src) != expected_sha:
            raise HashMismatch(expected_sha, sha256_file(src))
        return dest
    except Exception:
        if partial.exists():
            partial.unlink()
        if dest.exists() and sha256_file(dest) != expected_sha:
            dest.unlink()
        raise
