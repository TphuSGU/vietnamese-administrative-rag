"""Small-talk detection so greetings never retrieve legal chunks.

Without this guard, "xin chào" becomes a vector/BM25 query, returns arbitrary
legal/procedure chunks, and the LLM lists their document numbers in a greeting.
"""

from __future__ import annotations

import re
import unicodedata

WELCOME_ANSWER = (
    "Chào bạn! Tôi là trợ lý AI hỗ trợ tra cứu thông tin văn bản chính quyền "
    "địa phương và thủ tục hành chính. Bạn có thể hỏi tôi về:\n"
    "- Thông tin liên hệ, giờ làm việc, lịch làm việc của phường An Phú.\n"
    "- Thủ tục hành chính: hồ sơ, thời gian, lệ phí.\n"
    "- Nội dung các nghị quyết, quyết định, thông báo của phường.\n"
    "Bạn cần tra cứu nội dung nào?"
)

THANKS_ANSWER = "Không có gì. Nếu cần tra cứu thêm thủ tục hoặc văn bản, bạn cứ hỏi tôi."


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", text or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def social_answer(query: str) -> str:
    """Return a canned answer for greetings/thanks, or an empty string."""
    text = _normalize(query)
    if not text:
        return ""
    tokens = text.split()

    if text in {
        "xin chao", "chao", "chao ban", "hello", "hi", "hey",
        "ban la ai", "ban co the giup gi", "ban co the giup gi cho toi",
        "ban co the lam gi", "ban lam duoc gi", "giup gi",
    }:
        return WELCOME_ANSWER

    if "cam on" in text or text in {"thank you", "thanks", "thank"}:
        return THANKS_ANSWER

    # "chào bạn, bạn có thể giúp gì..." but not "chào bạn, thủ tục khai sinh..."
    if (
        len(tokens) <= 12
        and (text.startswith("chao ") or text.startswith("xin chao "))
        and any(term in text for term in ("giup gi", "lam gi", "la ai", "co the giup"))
    ):
        return WELCOME_ANSWER

    return ""
