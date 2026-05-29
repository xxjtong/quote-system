"""SseAdapter — 将 Agent 输出转为 AiChat.vue 兼容的 SSE 事件流"""
import json
import time


class SseAdapter:
    @staticmethod
    def connect(t0):
        elapsed = time.time() - t0
        return [f'data: {json.dumps({"type": "connect", "elapsed": f"{elapsed:.1f}s"})}\n\n']

    @staticmethod
    def first_token(t0):
        elapsed = time.time() - t0
        return [f'data: {json.dumps({"type": "first_token", "ttft": f"{elapsed:.1f}s"})}\n\n']

    @staticmethod
    def text(delta):
        if delta:
            return [f'data: {json.dumps({"type": "text", "text": delta}, ensure_ascii=False)}\n\n']
        return []

    @staticmethod
    def tool():
        return [f'data: {json.dumps({"type": "tool"})}\n\n']

    @staticmethod
    def done(parsed, t0):
        elapsed = time.time() - t0
        return [f'data: {json.dumps({"type": "done", "parsed": parsed, "elapsed": f"{elapsed:.1f}s"}, ensure_ascii=False)}\n\n']

    @staticmethod
    def quick_replies(items):
        if items:
            return [f'data: {json.dumps({"type": "quick_replies", "items": items}, ensure_ascii=False)}\n\n']
        return []

    @staticmethod
    def error(message):
        return [f'data: {json.dumps({"type": "error", "error": message}, ensure_ascii=False)}\n\n']

    @staticmethod
    def done_marker():
        return ['data: [DONE]\n\n']
