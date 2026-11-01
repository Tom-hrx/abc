"""成本换算。只用字符数做量级估算，不做分词（分词交给模型）。"""
from __future__ import annotations

import math


def estimate_cost_usd(input_tokens: int, output_tokens: int, config) -> float:
    return (
        input_tokens / 1_000_000 * config.LLM_PRICE_IN_PER_1M
        + output_tokens / 1_000_000 * config.LLM_PRICE_OUT_PER_1M
    )


def to_cny(usd: float, config) -> float:
    return usd * config.USD_TO_CNY


def estimate_document(char_count: int, config) -> dict:
    """给出"开始分析前"的量级预估。

    经验系数（英文）：1 token ≈ 4 字符；句子数 ≈ 字符数 / 90。
    分段阶段输出约等于输入（照抄），结构阶段约 800 token，
    逐句阶段输出约为输入的 0.9 倍。
    """
    tokens_in = max(1, math.ceil(char_count / 4))
    sentences = max(1, math.ceil(char_count / 90))
    batches = math.ceil(sentences / config.SENTENCE_BATCH_SIZE)

    total_in = tokens_in * 3 + batches * 400
    total_out = tokens_in + 800 + int(tokens_in * 0.9)
    usd = estimate_cost_usd(total_in, total_out, config)

    seconds = 25 + 15 + batches * 7
    return {
        "char_count": char_count,
        "estimated_sentences": sentences,
        "estimated_batches": batches,
        "estimated_tokens_in": total_in,
        "estimated_tokens_out": total_out,
        "estimated_cost_cny": round(to_cny(usd, config), 3),
        "estimated_seconds": seconds,
    }
