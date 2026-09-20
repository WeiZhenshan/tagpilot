"""LLM 富化：只生成别名/定义/易混淆/正反例，禁止写事实字段。"""

from __future__ import annotations

import json
from typing import Any, Callable

FORBIDDEN_KEYS = {
    "rank_no",
    "lower_bound",
    "upper_bound",
    "unit",
    "unit_scale",
    "parent_code",
    "parent_tag_id",
    "statistic",
    "semantic_type",
}

SCHEMA_KEYS = {"aliases", "definition_long", "confusable", "positive_examples", "negative_examples"}


def validate_enrichment(payload: dict[str, Any]) -> dict[str, Any]:
    extra = set(payload) - SCHEMA_KEYS
    if extra:
        raise ValueError(f"LLM 输出含未允许字段: {sorted(extra)}")
    for key in FORBIDDEN_KEYS:
        dumped = json.dumps(payload, ensure_ascii=False)
        if f'"{key}"' in dumped:
            raise ValueError(f"禁止 LLM 生成事实字段 {key}")
    aliases = payload.get("aliases") or []
    if not isinstance(aliases, list):
        raise ValueError("aliases 必须是数组")
    return {
        "aliases": aliases,
        "definition_long": payload.get("definition_long") or "",
        "confusable": payload.get("confusable") or [],
        "positive_examples": payload.get("positive_examples") or [],
        "negative_examples": payload.get("negative_examples") or [],
        "source": "LLM",
        "review_status": "DRAFT",
    }


def enrich_concept(concept: dict[str, Any], generate: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    prompt = (
        "根据已审核概念生成检索别名和正反例 JSON。"
        "禁止编造金额区间、单位、机构树或统计口径。"
        f"概念:{concept.get('concept_code')} {concept.get('concept_name')} {concept.get('definition')}"
    )
    raw = generate(prompt)
    return validate_enrichment(raw)


def stub_generate(prompt: str) -> dict[str, Any]:
    if "AUM" in prompt:
        return {
            "aliases": ["管资规模", "资产规模"],
            "definition_long": "客户资产管理规模",
            "confusable": [],
            "positive_examples": ["当前AUM超过50万的客户"],
            "negative_examples": ["近12个月最高AUM"],
        }
    return {
        "aliases": [],
        "definition_long": "",
        "confusable": [],
        "positive_examples": [],
        "negative_examples": [],
    }


class OllamaGenerator:
    """默认在本机推理；调用方仅传入已确认概念元数据，无客户数据/测试题。"""
    def __init__(self, model: str, base_url='http://127.0.0.1:11434', client=None):
        from urllib.parse import urlparse
        import httpx
        if urlparse(base_url).hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('远程模型需先完成数据边界评审，本适配器仅允许本机服务')
        if not model:
            raise ValueError('模型名称不能为空')
        self.model, self.base_url = model, base_url.rstrip('/')
        self.client = client or httpx.Client(timeout=120, follow_redirects=False)
        self.usage = {'input_tokens': 0, 'output_tokens': 0, 'duration_ns': 0, 'requests': 0}

    def __call__(self, prompt):
        response = self.client.post(self.base_url + '/api/generate', json={
            'model': self.model, 'prompt': prompt, 'stream': False, 'format': 'json',
            'options': {'temperature': 0, 'num_predict': 1200}})
        response.raise_for_status()
        body = response.json()
        if not body.get('done'):
            raise ValueError('模型生成未完成')
        self.usage['input_tokens'] += body.get('prompt_eval_count', 0)
        self.usage['output_tokens'] += body.get('eval_count', 0)
        self.usage['duration_ns'] += body.get('total_duration', 0)
        self.usage['requests'] += 1
        return json.loads(body['response'])


def enrich_reviewed_batch(concepts, generator, max_batch=10):
    if len(concepts) > max_batch:
        raise ValueError('先完成小批质量确认，再调整批次上限')
    outputs = []
    for concept in concepts:
        if concept.get('review_status') != 'REVIEWED' or concept.get('sealed') or concept.get('dataset_type') in {'GOLD', 'SEALED'}:
            raise ValueError('仅已复核概念元数据可用于富化，禁止封存题')
        metadata = {k: concept.get(k) for k in ('concept_code', 'concept_name', 'definition')}
        outputs.append({'concept_code': metadata['concept_code'], **enrich_concept(metadata, generator)})
    return outputs
