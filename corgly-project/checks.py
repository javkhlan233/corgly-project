"""Functional checks using an isolated database and mocked Slack transport."""
import json
import os
import tempfile
from unittest.mock import patch
import server

results = []
def check(name, condition):
    assert condition, name
    results.append({'check': name, 'result': 'PASS'})

def error(name, status, method, path, data):
    try:
        server.dispatch(method, path, data)
    except server.ApiError as e:
        check(name, e.status == status)
    else:
        raise AssertionError(name)

class SlackResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return b'ok'

with tempfile.TemporaryDirectory() as d:
    server.DB = d + '/test.sqlite3'
    server.initialize()
    check('Empty list returns 200', server.dispatch('GET', '/api/polls', {}) == (200, []))
    error('Empty question returns 400', 400, 'POST', '/api/polls', {'question':'', 'options':['A','B']})
    error('One option returns 400', 400, 'POST', '/api/polls', {'question':'Q', 'options':['A']})
    error('Duplicate options return 400', 400, 'POST', '/api/polls', {'question':'Q', 'options':['A','a']})
    error('Question above limit returns 400', 400, 'POST', '/api/polls', {'question':'Q'*201, 'options':['A','B']})
    error('Seven options return 400', 400, 'POST', '/api/polls', {'question':'Q', 'options':list('ABCDEFG')})
    status, poll = server.dispatch('POST', '/api/polls', {'question':' Test question ', 'options':['Yes','No']})
    check('Create returns 201 and trims whitespace', status == 201 and poll['question'] == 'Test question')
    pid, oid = poll['id'], poll['options'][0]['id']
    check('Get returns full poll', server.dispatch('GET', f'/api/polls/{pid}', {})[1] == poll)
    status, poll = server.dispatch('POST', f'/api/polls/{pid}/votes', {'option_id':oid})
    check('Vote increments option and total', status == 200 and poll['total_votes'] == 1 and poll['options'][0]['votes'] == 1)
    error('Invalid option returns 400', 400, 'POST', f'/api/polls/{pid}/votes', {'option_id':9999})
    error('Missing poll returns 404', 404, 'GET', '/api/polls/9999', {})
    with patch.dict(os.environ, {}, clear=True):
        error('Unconfigured Slack returns 503', 503, 'POST', f'/api/polls/{pid}/slack', {})
    with patch.dict(os.environ, {'SLACK_WEBHOOK_URL':'https://hooks.slack.com/services/test/test/test'}):
        with patch('urllib.request.urlopen', return_value=SlackResponse()) as mock:
            check('Mock Slack returns 200', server.dispatch('POST', f'/api/polls/{pid}/slack', {}) == (200, {'ok':True}))
            check('Slack payload contains question and count', 'Yes: 1' in json.loads(mock.call_args.args[0].data)['text'])
        with patch('urllib.request.urlopen', side_effect=TimeoutError()):
            error('Slack transport failure returns 502', 502, 'POST', f'/api/polls/{pid}/slack', {})
    server.initialize()
    check('Vote persists after reconnect', server.dispatch('GET', f'/api/polls/{pid}', {})[1]['total_votes'] == 1)
print(json.dumps({'passed':len(results),'checks':results,'slack_mode':'mock, no real Slack message sent'}, indent=2))
