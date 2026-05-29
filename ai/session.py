"""SessionManager — 服务端对话持久化，上下文窗口裁剪"""
import json
from datetime import datetime
from extensions import db
from models import AIConversation, AIMessage
from ai.config import MAX_CONTEXT_MESSAGES


class SessionManager:
    def __init__(self, user_id, session_id=''):
        self.user_id = user_id
        self.session_id = session_id or str(user_id)

    def get_or_create_conversation(self):
        conv = AIConversation.query.filter_by(
            user_id=self.user_id, session_id=self.session_id
        ).first()
        if not conv:
            conv = AIConversation(user_id=self.user_id, session_id=self.session_id)
            db.session.add(conv)
            db.session.commit()
        return conv

    def add_message(self, conversation_id, role, content, **kwargs):
        msg = AIMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=json.dumps(kwargs['tool_calls'], ensure_ascii=False) if kwargs.get('tool_calls') else None,
            tool_call_id=kwargs.get('tool_call_id'),
            name=kwargs.get('name'),
        )
        db.session.add(msg)
        conv = db.session.get(AIConversation, conversation_id)
        if conv:
            conv.message_count = AIMessage.query.filter_by(conversation_id=conversation_id).count()
            conv.updated_at = datetime.now()
        db.session.commit()
        return msg

    def get_messages(self, conversation_id, limit=None):
        if limit is None:
            limit = MAX_CONTEXT_MESSAGES
        # SQL LIMIT avoids loading full history into memory
        messages = AIMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(AIMessage.created_at.desc()).limit(limit * 2).all()
        messages.reverse()

        system_msgs = [m for m in messages if m.role == 'system']
        other_msgs = [m for m in messages if m.role != 'system']
        trimmed = other_msgs[-(limit - len(system_msgs)):] if len(system_msgs) < limit else other_msgs[-limit:]
        return [self._to_dict(m) for m in (system_msgs + trimmed)]

    def _to_dict(self, msg):
        d = {'role': msg.role}
        if msg.role == 'assistant' and msg.tool_calls:
            d['content'] = msg.content or ''
            d['tool_calls'] = json.loads(msg.tool_calls)
        elif msg.role == 'tool':
            d['content'] = msg.content or ''
            d['tool_call_id'] = msg.tool_call_id
        else:
            d['content'] = msg.content or ''
        return d

    def clear_conversation(self, conversation_id):
        AIMessage.query.filter_by(conversation_id=conversation_id).delete()
        conv = db.session.get(AIConversation, conversation_id)
        if conv:
            conv.message_count = 0
        db.session.commit()
