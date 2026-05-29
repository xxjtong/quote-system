"""LlmEngine — OpenAI 兼容 HTTP 客户端（流式 + 非流式，含自动重试 + 降级 + 辅助模型）"""
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ai.config import MODEL_MAP, PROVIDERS, AUX_MODEL, VISION_MODEL, FALLBACK_CHAIN


class LlmEngine:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})
        # 502/503/504 自动重试 3 次，间隔 1s/2s/4s
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
            allowed_methods=['POST'],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount('https://', adapter)

    def _resolve(self, model_id):
        mapping = MODEL_MAP.get(model_id)
        if not mapping:
            raise ValueError(f'Unknown model: {model_id}')
        return self._cfg_for(mapping['provider'], mapping['model'])

    def _cfg_for(self, provider_name, model_name):
        provider = PROVIDERS.get(provider_name)
        if not provider or not provider['api_key']:
            raise ValueError(f'Provider {provider_name} not configured (missing API key)')
        return {
            'url': f'{provider["base_url"]}/chat/completions',
            'api_key': provider['api_key'],
            'model': model_name,
        }

    def _try_fallback(self, model_id, messages, tools, kwargs, stream=False):
        """按 FALLBACK_CHAIN 依次尝试，全部失败才抛异常"""
        mapping = MODEL_MAP.get(model_id)
        providers_to_try = [mapping['provider']] if mapping else []
        providers_to_try += [p for p in FALLBACK_CHAIN if p not in providers_to_try]

        # 每个 provider 的默认模型（降级时用）
        _PROVIDER_DEFAULT_MODEL = {
            'deepseek': 'deepseek-chat',
            'xiaomi': 'mimo-v2.5-pro',
        }

        last_err = None
        for p in providers_to_try:
            try:
                # 同 provider 用原模型名，切 provider 用新 provider 的默认模型
                model = mapping['model'] if mapping and p == mapping['provider'] else _PROVIDER_DEFAULT_MODEL.get(p, model_id)
                cfg = self._cfg_for(p, model)
                if stream:
                    return self._do_stream(cfg, messages, tools, kwargs)
                else:
                    return self._do_chat(cfg, messages, tools, kwargs)
            except Exception as e:
                last_err = e
                continue
        raise last_err or Exception('All providers failed')

    def _do_chat(self, cfg, messages, tools, kwargs):
        body = {
            'model': cfg['model'],
            'messages': messages,
            'temperature': kwargs.get('temperature', 0.3),
            'max_tokens': kwargs.get('max_tokens', 2000),
        }
        if tools:
            body['tools'] = tools
        resp = self._session.post(
            cfg['url'], json=body,
            headers={'Authorization': f'Bearer {cfg["api_key"]}'},
            timeout=kwargs.get('timeout', 60),
        )
        if not resp.ok:
            detail = resp.text[:500] if resp.text else 'No body'
            raise Exception(f'{resp.status_code} {resp.reason}: {detail}')
        return resp.json()

    def _do_stream(self, cfg, messages, tools, kwargs):
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
            cfg['url'], json=body,
            headers={'Authorization': f'Bearer {cfg["api_key"]}'},
            stream=True, timeout=kwargs.get('timeout', 120),
        )
        if not resp.ok:
            detail = resp.text[:500] if resp.text else 'No body'
            raise Exception(f'{resp.status_code} {resp.reason}: {detail}')
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

    def chat(self, model_id, messages, tools=None, **kwargs):
        """非流式调用（含自动降级）。返回完整响应 dict。"""
        return self._try_fallback(model_id, messages, tools, kwargs, stream=False)

    def chat_stream(self, model_id, messages, tools=None, **kwargs):
        """流式生成器（含自动降级）。yield OpenAI SSE chunks。"""
        yield from self._try_fallback(model_id, messages, tools, kwargs, stream=True)

    # ─── 辅助模型方法 ───

    def chat_aux(self, messages, **kwargs):
        """辅助 LLM 调用（Quick Reply / 轻量分类等），使用 AUX_MODEL。"""
        return self.chat(AUX_MODEL, messages, max_tokens=kwargs.get('max_tokens', 200),
                         temperature=kwargs.get('temperature', 0.3))

    def chat_vision(self, image_base64, prompt, **kwargs):
        """视觉识别（OCR / 图片理解），使用 VISION_MODEL (mimo-v2-omni)。"""
        messages = [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_base64}'}},
            ]
        }]
        return self.chat(VISION_MODEL, messages, max_tokens=kwargs.get('max_tokens', 2000),
                         temperature=kwargs.get('temperature', 0.1))
