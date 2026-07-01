import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

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

    def test_otlp_payload_is_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            repo=Path(td); (repo/'.agent-loop/hooks').mkdir(parents=True)
            (repo/'.agent-loop').mkdir(exist_ok=True)
            shutil_files=[('.agent-loop/hooks/loop_hook.py',HOOK),('.agent-loop/policy.json',ROOT/'.agent-loop/policy.json'),('.agent-loop/otel.json',ROOT/'.agent-loop/otel.json')]
            for rel,src in shutil_files:
                dst=repo/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(src.read_bytes())
            with socketserver.TCPServer(('127.0.0.1',0),Receiver) as server:
                port=server.server_address[1]
                thread=threading.Thread(target=server.handle_request); thread.start()
                env=os.environ.copy(); env['AGENT_LOOP_OTEL_ENDPOINT']=f'http://127.0.0.1:{port}/v1/logs'
                event={'hook_event_name':'PreToolUse','session_id':'s','turn_id':'t','cwd':str(repo),'tool_name':'Bash','tool_input':{'command':'API_KEY=secret git status --token credential'}}
                subprocess.run([sys.executable,str(repo/'.agent-loop/hooks/loop_hook.py'),'--platform','claude'],input=json.dumps(event),text=True,env=env,check=True,capture_output=True)
                thread.join(3)
                body=Receiver.payloads[-1].decode()
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
            for rel in ['.agent-loop/hooks/loop_hook.py','.agent-loop/policy.json','.agent-loop/otel.json']:
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
