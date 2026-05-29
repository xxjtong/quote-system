"""ToolRegistry — 工具注册与安全执行"""
import json
import sqlite3
from pathlib import Path


class ToolRegistry:
    def __init__(self, user_context=None):
        self.user_context = user_context or {}
        self._registry = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register('query_database', self._exec_query_database)
        self.register('call_api', self._exec_call_api)

    def register(self, name, executor):
        self._registry[name] = executor

    def execute(self, name, args):
        executor = self._registry.get(name)
        if not executor:
            return {'error': f'未知工具: {name}'}
        try:
            return executor(args)
        except Exception as e:
            return {'error': f'工具执行失败: {str(e)}'}

    def _exec_query_database(self, args):
        sql = (args.get('query') or args.get('sql') or '').strip()
        upper = sql.upper()
        if not upper.startswith('SELECT'):
            return {'error': '只允许 SELECT 查询'}
        for kw in ['PRAGMA', 'ATTACH', 'DETACH', 'VACUUM', 'REINDEX',
                    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']:
            if kw in upper:
                return {'error': f'不允许使用 {kw}'}

        db_path = self.user_context.get('db_path', str(Path(__file__).parent.parent / 'quote.db'))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            rows = [dict(row) for row in cursor.fetchmany(50)]
            return {'rows': rows, 'count': len(rows)}
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()

    def _exec_call_api(self, args):
        import requests as http_requests
        method = args.get('method', 'GET').upper()
        path = args.get('path', '')
        body = args.get('body')
        token = self.user_context.get('auth_token', '')
        base_url = self.user_context.get('base_url', 'http://127.0.0.1:5001')
        if not path.startswith('/'):
            path = '/' + path
        url = f'{base_url}{path}'
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        try:
            if method == 'GET':
                resp = http_requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                resp = http_requests.post(url, json=body or {}, headers=headers, timeout=15)
            else:
                return {'error': f'不支持的方法: {method}'}
            return resp.json() if resp.text else {'status': resp.status_code}
        except Exception as e:
            return {'error': f'API 调用失败: {str(e)}'}
