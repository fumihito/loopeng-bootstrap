import http.server
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
HOOK=ROOT/'.agent-loop/hooks/loop_hook.py'

class Receiver(http.server.BaseHTTPRequestHandler):
    payloads=[]
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        self.__class__.payloads.append(self.rfile.read(length))
        self.send_response(200); self.end_headers()
    def log_message(self,*args): pass

class TelemetryTests(unittest.TestCase):
    def test_command_names_do_not_include_arguments(self):
        ns={}
        exec(HOOK.read_text(),ns)
        names=ns['command_names']('TOKEN=supersecret git status --porcelain && python3 /tmp/private.py --password hunter2 | tee /tmp/out')
        self.assertEqual(names,['git','python3','tee'])
        rendered=json.dumps(names)
        for secret in ['supersecret','hunter2','private.py','/tmp/out','status','porcelain']:
            self.assertNotIn(secret,rendered)

    def test_brief_requested_telemetry_is_content_free(self):
        ns = {}
        exec(HOOK.read_text(), ns)
        event = {'hook_event_name': 'UserPromptSubmit', 'session_id': 's', 'turn_id': 't', 'cwd': str(ROOT), 'prompt': 'brief: private prompt'}
        attrs = ns['telemetry_attributes'](event, 'claude', {'routing.mode': 'LOOP', 'entry.role': 'loop-brief-assistant'})
        self.assertEqual(attrs['routing.mode'], 'LOOP')
        self.assertEqual(attrs['entry.role'], 'loop-brief-assistant')
        self.assertNotIn('prompt', attrs)
        self.assertNotIn('content', attrs)
        self.assertNotIn('body', attrs)
        self.assertNotIn('text', attrs)

    def test_otlp_payload_is_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)
            (repo/'.agent-loop').mkdir(parents=True)
            (repo/'.agent-loop/otel.json').write_text((ROOT/'.agent-loop/otel.json').read_text(), encoding='utf-8')
            (repo/'.agent-loop/hooks').mkdir(exist_ok=True)
            (repo/'.agent-loop/hooks/loop_hook.py').write_bytes(HOOK.read_bytes())
            ns={}
            exec(HOOK.read_text(),ns)
            captured={}

            class Response:
                status=200
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc, tb):
                    return False

            def fake_urlopen(request, timeout=0.5):
                captured['request']=request
                return Response()

            event={'hook_event_name':'PreToolUse','session_id':'s','turn_id':'t','cwd':str(repo),'tool_name':'Bash','tool_input':{'command':'API_KEY=secret git status --token credential'}}
            attrs=ns['telemetry_attributes'](event,'claude',{'tool_input_redacted':True})
            with mock.patch.object(ns['urllib'].request, 'urlopen', side_effect=fake_urlopen):
                ns['send_otel'](repo,'agent.loop.telemetry.self_test',attrs)
            body=captured['request'].data.decode()
            self.assertIn('git',body); self.assertIn('tool_input_redacted',body)
            for secret in ['API_KEY','secret','status','token','credential','tool_input.command']:
                self.assertNotIn(secret,body)

if __name__=='__main__': unittest.main()

class SkillAndJournalTests(unittest.TestCase):
    def test_skill_names_are_allowlisted(self):
        ns={}
        exec(HOOK.read_text(),ns)
        self.assertEqual(ns['skill_name']({'hook_event_name':'UserPromptExpansion','command_name':'gatekeeper'}),'gatekeeper')
        self.assertEqual(ns['skill_name']({'hook_event_name':'UserPromptExpansion','command_name':'sensemaker'}),'sensemaker')
        self.assertEqual(ns['skill_name']({'hook_event_name':'PreToolUse','tool_name':'Skill','tool_input':{'skill':'meta-evaluator','args':'secret'}}),'meta-evaluator')
        self.assertEqual(ns['skill_name']({'hook_event_name':'SubagentStart','agent_type':'state-steward'}),'state-steward')
        self.assertIsNone(ns['skill_name']({'hook_event_name':'UserPromptExpansion','command_name':'../../secret'}))

    def test_runtime_journal_excludes_tool_input(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td)
            for rel in ['.agent-loop/hooks/loop_hook.py','.agent-loop/policy.json','.agent-loop/otel.json','.agent-loop/lib/loop_gate.py']:
                src=ROOT/rel; dst=repo/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(src.read_bytes())
            env=os.environ.copy(); env['AGENT_LOOP_OTEL_EXPORTER']='none'
            start={'hook_event_name':'UserPromptSubmit','session_id':'s1','turn_id':'t1','cwd':str(repo),'prompt':'private prompt'}
            subprocess.run([sys.executable,str(repo/'.agent-loop/hooks/loop_hook.py'),'--platform','claude'],input=json.dumps(start),text=True,env=env,check=True,capture_output=True)
            post={'hook_event_name':'PostToolUse','session_id':'s1','turn_id':'t1','cwd':str(repo),'tool_name':'Bash','tool_input':{'command':'TOKEN=verysecret git status --password hidden'},'tool_response':'private output'}
            subprocess.run([sys.executable,str(repo/'.agent-loop/hooks/loop_hook.py'),'--platform','claude'],input=json.dumps(post),text=True,env=env,check=True,capture_output=True)
            body=(repo/'.agent-loop/runtime/turns/t1/journal.jsonl').read_text()
            self.assertIn('git',body)
            for secret in ['verysecret','hidden','private output','password','status','TOKEN=']:
                self.assertNotIn(secret,body)
