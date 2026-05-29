"""AI Engine 配置 — 模型/供应商映射、常量"""
import os

PROVIDERS = {
    'deepseek': {
        'base_url': 'https://api.deepseek.com/v1',
        'api_key': os.environ.get('DEEPSEEK_API_KEY', ''),
        'api_mode': 'openai',
    },
    'openai': {
        'base_url': 'https://api.openai.com/v1',
        'api_key': os.environ.get('OPENAI_API_KEY', ''),
        'api_mode': 'openai',
    },
}

MODEL_MAP = {
    'deepseek-v4-flash': {'provider': 'deepseek', 'model': 'deepseek-chat'},
    'deepseek-v4-pro':   {'provider': 'deepseek', 'model': 'deepseek-reasoner'},
}

DEFAULT_MODEL = 'deepseek-v4-flash'
MAX_AGENT_TURNS = 5
MAX_CONTEXT_MESSAGES = 30

AVAILABLE_MODELS = [
    {'id': 'deepseek-v4-flash', 'name': 'DeepSeek V4 Flash (快速)', 'provider': 'deepseek'},
    {'id': 'deepseek-v4-pro',   'name': 'DeepSeek V4 Pro (深度推理)', 'provider': 'deepseek'},
]
