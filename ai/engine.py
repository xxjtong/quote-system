"""LlmEngine — OpenAI 兼容 HTTP 客户端（流式 + 非流式）"""
import json
import requests
from ai.config import MODEL_MAP, PROVIDERS


class LlmEngine:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})

    def _resolve(self, model_id):
        mapping = MODEL_MAP.get(model_id)
        if not mapping:
            raise ValueError(f'Unknown model: {model_id}')
        provider = PROVIDERS.get(mapping['provider'])
        if not provider or not provider['api_key']:
            raise ValueError(f'Provider {mapping["provider"]} not configured (missing API key)')
        return {
            'url': f'{provider["base_url"]}/chat/completions',
            'api_key': provider['api_key'],
            'model': mapping['model'],
        }

    def chat(self, model_id, messages, tools=None, **kwargs):
        """非流式调用。返回完整响应 dict（OpenAI 格式）。"""
        cfg = self._resolve(model_id)
        body = {
            'model': cfg['model'],
            'messages': messages,
            'temperature': kwargs.get('temperature', 0.3),
            'max_tokens': kwargs.get('max_tokens', 2000),
        }
        if tools:
            body['tools'] = tools
        resp = self._session.post(
            cfg['url'],
            json=body,
            headers={'Authorization': f'Bearer {cfg["api_key"]}'},
            timeout=kwargs.get('timeout', 60),
        )
        resp.raise_for_status()
        return resp.json()

    def chat_stream(self, model_id, messages, tools=None, **kwargs):
        """流式生成器。yield OpenAI SSE chunks (dict)。"""
        cfg = self._resolve(model_id)
        body = {
            'model': cfg['model'],
            'messages': messages,
            'temperature': kwargs.get('temperature', 0.3),
            'max_tokens': kwargs.get('max_tokens', 2000),
            'stream': True,
        }
        if tools:
            body['tools'] = tools
        resp = self._session.post(
            cfg['url'],
            json=body,
            headers={'Authorization': f'Bearer {cfg["api_key"]}'},
            stream=True,
            timeout=kwargs.get('timeout', 120),
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode('utf-8', errors='replace')
            if not line.startswith('data: '):
                continue
            payload = line[6:]
            if payload == '[DONE]':
                break
            try:
                yield json.loads(payload)
            except json.JSONDecodeError:
                continue
