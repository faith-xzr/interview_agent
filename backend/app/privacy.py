import re
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class MaskedText:
    text: str
    replacements: Dict[str, str]


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
WECHAT_RE = re.compile(r"((?:微信|wechat|WeChat|WX|wx)[:：\s]*)([A-Za-z][A-Za-z0-9_-]{5,})")


def mask_pii(text: str, candidate_name: str = None) -> MaskedText:
    replacements: Dict[str, str] = {}
    masked = text

    if candidate_name and candidate_name.strip() and candidate_name != "未知候选人":
        placeholder = "候选人A"
        masked = masked.replace(candidate_name, placeholder)
        replacements[placeholder] = candidate_name

    masked = _replace_full_match(masked, EMAIL_RE, "EMAIL", replacements)
    masked = _replace_full_match(masked, PHONE_RE, "PHONE", replacements)
    masked = _replace_wechat(masked, replacements)
    return MaskedText(text=masked, replacements=replacements)


def restore_pii(text: str, replacements: Dict[str, str]) -> str:
    restored = text
    for placeholder, original in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        restored = restored.replace(f"[{placeholder}]", original)
        restored = restored.replace(placeholder, original)
    return restored


def restore_pii_in_data(value: Any, replacements: Dict[str, str]) -> Any:
    if isinstance(value, str):
        return restore_pii(value, replacements)
    if isinstance(value, list):
        return [restore_pii_in_data(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: restore_pii_in_data(item, replacements) for key, item in value.items()}
    return value


def _replace_full_match(text: str, pattern: re.Pattern, label: str, replacements: Dict[str, str]) -> str:
    counter = 0

    def repl(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        placeholder = f"{label}_{counter}"
        replacements[placeholder] = match.group(0)
        return f"[{placeholder}]"

    return pattern.sub(repl, text)


def _replace_wechat(text: str, replacements: Dict[str, str]) -> str:
    counter = 0

    def repl(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        placeholder = f"WECHAT_{counter}"
        replacements[placeholder] = match.group(2)
        return f"{match.group(1)}[{placeholder}]"

    return WECHAT_RE.sub(repl, text)

