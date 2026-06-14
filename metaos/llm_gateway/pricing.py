"""DeepSeek token pricing and balance estimates."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class ModelPrice:
    model: str
    input_cache_hit_per_1m: float
    input_cache_miss_per_1m: float
    output_per_1m: float


DEFAULT_PRICES: dict[str, ModelPrice] = {
    "deepseek-v4-flash": ModelPrice(
        model="deepseek-v4-flash",
        input_cache_hit_per_1m=0.0028,
        input_cache_miss_per_1m=0.14,
        output_per_1m=0.28,
    ),
    "deepseek-v4-pro": ModelPrice(
        model="deepseek-v4-pro",
        input_cache_hit_per_1m=0.003625,
        input_cache_miss_per_1m=0.435,
        output_per_1m=0.87,
    ),
}

MODEL_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-flash",
}


def price_for_model(model: str) -> ModelPrice:
    normalized = MODEL_ALIASES.get(model.strip().lower(), model.strip().lower())
    if normalized not in DEFAULT_PRICES:
        normalized = "deepseek-v4-pro" if "pro" in normalized else "deepseek-v4-flash"
    default = DEFAULT_PRICES[normalized]
    prefix = f"DEEPSEEK_PRICE_{default.model.upper().replace('-', '_')}"
    return ModelPrice(
        model=default.model,
        input_cache_hit_per_1m=float(
            os.getenv(f"{prefix}_INPUT_CACHE_HIT_PER_1M", default.input_cache_hit_per_1m)
        ),
        input_cache_miss_per_1m=float(
            os.getenv(f"{prefix}_INPUT_CACHE_MISS_PER_1M", default.input_cache_miss_per_1m)
        ),
        output_per_1m=float(os.getenv(f"{prefix}_OUTPUT_PER_1M", default.output_per_1m)),
    )


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int]:
    usage = usage or {}
    completion_details = usage.get("completion_tokens_details") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
    cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
    if cache_hit_tokens <= 0 and cache_miss_tokens <= 0:
        cache_miss_tokens = prompt_tokens
    completion_tokens = int(usage.get("completion_tokens") or 0)
    reasoning_tokens = int(
        usage.get("reasoning_tokens")
        or completion_details.get("reasoning_tokens")
        or 0
    )
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_cache_hit_tokens": cache_hit_tokens,
        "prompt_cache_miss_tokens": cache_miss_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def estimate_usage_cost(model: str, usage: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_usage(usage)
    price = price_for_model(model)
    input_cache_hit_cost = (
        normalized["prompt_cache_hit_tokens"]
        / TOKENS_PER_MILLION
        * price.input_cache_hit_per_1m
    )
    input_cache_miss_cost = (
        normalized["prompt_cache_miss_tokens"]
        / TOKENS_PER_MILLION
        * price.input_cache_miss_per_1m
    )
    output_cost = (
        normalized["completion_tokens"]
        / TOKENS_PER_MILLION
        * price.output_per_1m
    )
    total_cost = input_cache_hit_cost + input_cache_miss_cost + output_cost
    return {
        "currency": "USD",
        "model": price.model,
        "input_cache_hit_cost": round(input_cache_hit_cost, 8),
        "input_cache_miss_cost": round(input_cache_miss_cost, 8),
        "output_cost": round(output_cost, 8),
        "total_cost": round(total_cost, 8),
        "price_per_1m": {
            "input_cache_hit": price.input_cache_hit_per_1m,
            "input_cache_miss": price.input_cache_miss_per_1m,
            "output": price.output_per_1m,
        },
        "usage": normalized,
    }


def parse_balance_infos(balance_response: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not balance_response:
        return []
    infos = balance_response.get("balance_infos")
    if isinstance(infos, list):
        return [info for info in infos if isinstance(info, dict)]
    return []


def balance_usd_amount(info: dict[str, Any], cny_per_usd: float | None = None) -> float | None:
    currency = str(info.get("currency") or "").upper()
    total_balance = float(info.get("total_balance") or 0)
    if currency == "USD":
        return total_balance
    if currency == "CNY" and cny_per_usd:
        return total_balance / cny_per_usd
    return None


def estimate_balance_tokens(
    balance_response: dict[str, Any] | None,
    model: str,
    *,
    cny_per_usd: float | None = None,
) -> list[dict[str, Any]]:
    price = price_for_model(model)
    estimates: list[dict[str, Any]] = []
    for info in parse_balance_infos(balance_response):
        usd_amount = balance_usd_amount(info, cny_per_usd)
        if usd_amount is None:
            estimates.append(
                {
                    "currency": info.get("currency"),
                    "total_balance": info.get("total_balance"),
                    "estimate_available": False,
                }
            )
            continue
        estimates.append(
            {
                "currency": info.get("currency"),
                "total_balance": info.get("total_balance"),
                "estimate_available": True,
                "model": price.model,
                "usd_amount": round(usd_amount, 6),
                "input_cache_miss_tokens": int(
                    usd_amount / price.input_cache_miss_per_1m * TOKENS_PER_MILLION
                ),
                "input_cache_hit_tokens": int(
                    usd_amount / price.input_cache_hit_per_1m * TOKENS_PER_MILLION
                ),
                "output_tokens": int(usd_amount / price.output_per_1m * TOKENS_PER_MILLION),
                "price_per_1m": {
                    "input_cache_hit": price.input_cache_hit_per_1m,
                    "input_cache_miss": price.input_cache_miss_per_1m,
                    "output": price.output_per_1m,
                },
            }
        )
    return estimates
