"""Agent — tool calling 循环编排 + SSE 流式输出"""
import json
import time
import threading
from ai.config import DEFAULT_MODEL, MAX_AGENT_TURNS
from ai.sse import SseAdapter
from ai.reply_parser import parse_reply_actions, generate_quick_replies


class Agent:
    def __init__(self, llm_engine, tool_registry):
        self.llm = llm_engine
        self.tools = tool_registry

    def run(self, messages, tool_defs, conv_id=None, session_mgr=None, stream=True, quick_reply_llm=None):
        """主入口。stream=True 返回 SSE 事件生成器，否则返回 {'reply': ...}"""
        if stream:
            return list(self._run_stream(messages, tool_defs, conv_id, session_mgr, quick_reply_llm))
        return self._run_sync(messages, tool_defs, conv_id, session_mgr, quick_reply_llm)

    def _run_sync(self, messages, tool_defs, conv_id, session_mgr, quick_reply_llm):
        """非流式：工具循环 + 返回完整回复"""
        t0 = time.time()
        turn = 0
        tool_called = False

        while turn < MAX_AGENT_TURNS:
            try:
                response = self.llm.chat(DEFAULT_MODEL, messages, tools=tool_defs, max_tokens=2000)
            except Exception as e:
                return {'reply': '', 'error': str(e)}

            choice = response['choices'][0]
            msg = choice['message']

            if conv_id and session_mgr:
                session_mgr.add_message(conv_id, 'assistant', msg.get('content', ''),
                                        tool_calls=msg.get('tool_calls'))

            if not msg.get('tool_calls'):
                reply = msg.get('content', '')
                parsed = parse_reply_actions(reply)
                return {
                    'reply': reply,
                    'parsed': parsed,
                    'elapsed': time.time() - t0,
                    'tool_called': tool_called,
                }

            tool_called = True
            for tc in msg['tool_calls']:
                fn = tc['function']
                try:
                    args = json.loads(fn['arguments'])
                except json.JSONDecodeError:
                    args = {}
                result = self.tools.execute(fn['name'], args)
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc.get('id', ''),
                    'name': fn['name'],
                    'content': json.dumps(result, ensure_ascii=False),
                })
                if conv_id and session_mgr:
                    session_mgr.add_message(conv_id, 'tool', json.dumps(result, ensure_ascii=False),
                                            tool_call_id=tc.get('id', ''), name=fn['name'])

            turn += 1

        return {'reply': '', 'error': '处理超时，请重试'}

    def _run_stream(self, messages, tool_defs, conv_id, session_mgr, quick_reply_llm):
        """流式：工具循环（非流式）+ 最终回复（流式）"""
        t0 = time.time()
        events = []
        turn = 0
        tool_called = False

        # Emit connect immediately so frontend knows we're alive
        events.extend(SseAdapter.connect(t0))

        # Phase 1: Tool rounds (non-streaming)
        while turn < MAX_AGENT_TURNS:
            try:
                response = self.llm.chat(DEFAULT_MODEL, messages, tools=tool_defs, max_tokens=2000)
            except Exception as e:
                events.extend(SseAdapter.error(f'AI 服务异常: {str(e)}'))
                events.extend(SseAdapter.done_marker())
                return events

            choice = response['choices'][0]
            msg = choice['message']

            if conv_id and session_mgr:
                session_mgr.add_message(conv_id, 'assistant', msg.get('content', ''),
                                        tool_calls=msg.get('tool_calls'))

            if not msg.get('tool_calls'):
                # No more tool calls — stream the final text response
                final_text = msg.get('content', '') or ''
                if not final_text and tool_called:
                    final_text = '抱歉，查询过程中遇到问题，请尝试换个方式提问。'
                if tool_called:
                    events.extend(SseAdapter.tool())

                if final_text:
                    events.extend(SseAdapter.first_token(t0))
                    # Stream text in chunks for visual effect
                    chunk_size = 3
                    for i in range(0, len(final_text), chunk_size):
                        events.extend(SseAdapter.text(final_text[i:i+chunk_size]))

                parsed = parse_reply_actions(final_text)
                events.extend(SseAdapter.done(parsed, t0))

                # Quick replies (fire-and-forget if quick_reply_llm available)
                if quick_reply_llm:
                    try:
                        replies = generate_quick_replies(
                            final_text,
                            lambda sys, usr, mt: quick_reply_llm(DEFAULT_MODEL, sys, usr, mt)
                        )
                        events.extend(SseAdapter.quick_replies(replies))
                    except Exception:
                        pass

                events.extend(SseAdapter.done_marker())
                return events

            # Tool calls present
            tool_called = True
            for tc in msg['tool_calls']:
                fn = tc['function']
                try:
                    args = json.loads(fn['arguments'])
                except json.JSONDecodeError:
                    args = {}
                result = self.tools.execute(fn['name'], args)
                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc.get('id', ''),
                    'name': fn['name'],
                    'content': json.dumps(result, ensure_ascii=False),
                })
                if conv_id and session_mgr:
                    session_mgr.add_message(conv_id, 'tool', json.dumps(result, ensure_ascii=False),
                                            tool_call_id=tc.get('id', ''), name=fn['name'])

            turn += 1

        events.extend(SseAdapter.error('处理超时，请重试'))
        events.extend(SseAdapter.done_marker())
        return events
