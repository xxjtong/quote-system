"""AI Engine 配置 — 模型/供应商映射、常量"""
import os

PROVIDERS = {
    'deepseek': {
        'base_url': 'https://api.deepseek.com/v1',
        'api_key': os.environ.get('DEEPSEEK_API_KEY', ''),
        'api_mode': 'openai',
    },
    'xiaomi': {
        'base_url': os.environ.get('XIAOMI_API_BASE', 'https://api.xiaomimimo.com/v1'),
        'api_key': os.environ.get('XIAOMI_API_KEY', ''),
        'api_mode': 'openai',
    },
}

# 主对话模型
MODEL_MAP = {
    'deepseek-v4-flash': {'provider': 'deepseek', 'model': 'deepseek-chat'},
    'deepseek-v4-pro':   {'provider': 'deepseek', 'model': 'deepseek-reasoner'},
    'mimo-v2.5-pro':     {'provider': 'xiaomi',  'model': 'mimo-v2.5-pro'},
    'mimo-v2.5':         {'provider': 'xiaomi',  'model': 'mimo-v2.5'},
    'mimo-v2-omni':      {'provider': 'xiaomi',  'model': 'mimo-v2-omni'},
}

# 辅助模型: OCR / 视觉识别 / Quick Reply / 降级备用
AUX_MODEL = 'mimo-v2.5-pro'
VISION_MODEL = 'mimo-v2-omni'

DEFAULT_MODEL = 'deepseek-v4-flash'
MAX_AGENT_TURNS = 5
MAX_CONTEXT_MESSAGES = 30

# 自动降级链: 主模型不可用时依次尝试
FALLBACK_CHAIN = ['deepseek', 'xiaomi']

AVAILABLE_MODELS = [
    {'id': 'deepseek-v4-flash', 'name': 'DeepSeek V4 Flash (快速)', 'provider': 'deepseek'},
    {'id': 'deepseek-v4-pro',   'name': 'DeepSeek V4 Pro (深度推理)', 'provider': 'deepseek'},
    {'id': 'mimo-v2.5-pro',     'name': '小米 MiMo V2.5 Pro', 'provider': 'xiaomi'},
]
