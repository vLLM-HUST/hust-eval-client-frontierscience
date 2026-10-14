import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from hust_eval_frontierscience import pipeline as p, seal

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.bodies=[]; bodies=self.bodies
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length']))); bodies.append(body)
                grade=body['messages'][0]['content'].startswith('You are grading')
                content='Rubric satisfied.\nVERDICT: 7' if grade and 'The rubric:' in body['messages'][0]['content'] else 'Equivalent.\nVERDICT: CORRECT' if grade else 'FINAL ANSWER: test'
                result={'choices':[{'message':{'content':content},'finish_reason':'stop'}],'usage':{'completion_tokens':10}}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(result).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.assets=self.root/'assets'; hashes={}
        for track,count in p.COUNTS.items():
            file=self.assets/track/'test.jsonl'; file.parent.mkdir(parents=True)
            rows=[{'problem':f'Question {i}','answer':'SECRET RUBRIC','subject':'physics','task_group_id':'duplicate-group'} for i in range(count)]
            file.write_text(''.join(json.dumps(row)+'\n' for row in rows)); hashes[track]=p.sha256_file(file)
        cfg={'base_url':f'http://127.0.0.1:{self.server.server_port}','model':'qwen3.5-35b','concurrency':4,'request':{'max_tokens':128,'temperature':0}}
        p.dump(self.root/'config.json',cfg); self.plan=self.root/'plan'
        with patch.dict(p.DATA_HASHES,hashes):
            p.prepare(argparse.Namespace(assets=str(self.assets),output=str(self.plan),solver_config=str(self.root/'config.json'),judge_config=str(self.root/'config.json')))
    def stage(self,stage,limit=None,resume=False):
        args=argparse.Namespace(plan=str(self.plan),output=str(self.root/stage),responses=str(self.root/'solver'),limit=limit,resume=resume)
        with contextlib.redirect_stdout(io.StringIO()): return p.execute(args,stage)
    def report(self):
        return p.summary(argparse.Namespace(plan=str(self.plan),responses=str(self.root/'solver'),grades=str(self.root/'judge'),output=str(self.root/'report')))
    def test_full_http_flow_resume_summary_seal(self):
        self.stage('solver'); self.assertEqual(len(self.bodies),160)
        self.assertTrue(all('SECRET RUBRIC' not in json.dumps(b) for b in self.bodies))
        self.stage('judge'); self.assertEqual(len(self.bodies),320)
        self.stage('solver',resume=True); self.stage('judge',resume=True); self.assertEqual(len(self.bodies),320)
        report=self.report(); self.assertEqual(report['scope'],'full_gold'); self.assertEqual(report['tracks']['research']['successes'],60)
        seal.seal_evidence(self.root); (self.root/'results').mkdir()
        table=self.root/'results/table.csv'; table.write_text('track,success\nresearch,1\n')
        seal.seal_final(self.root,table); self.assertTrue(seal.seal_check(self.root,table)['ok'])
        (self.plan/'tasks.json').write_text('[]'); self.assertFalse(seal.seal_check(self.root,table)['ok'])
    def test_changed_record_rejected(self):
        self.stage('solver',limit=1); file=self.root/'solver/requests/olympiad-0000.json'
        record=p.read(file); record['content']='tampered';p.dump(file,record)
        with self.assertRaises(ValueError):self.stage('solver',limit=1,resume=True)
    def test_changed_plan_rejected(self):
        (self.plan/'tasks.json').write_text('[]')
        with self.assertRaises(ValueError):p.load_plan(self.plan)
    def test_group_ids_do_not_deduplicate(self):
        _,tasks=p.load_plan(self.plan);self.assertEqual(len({t['case_id'] for t in tasks}),160)
        self.stage('solver',limit=2); self.stage('judge');report=self.report()
        self.assertEqual(report['scope'],'subset_smoke');self.assertIsNone(report['tracks']['research']['success_rate'])
    def test_failed_judge_is_unresolved(self):
        self.stage('solver',limit=1)
        with patch.object(p,'call',return_value={'status':'ok','content':'not json','finish_reason':'stop'}):self.stage('judge')
        report=self.report()['tracks']['olympiad'];self.assertIsNone(report['success_rate']);self.assertEqual(report['judge_unresolved'],1)
    def test_solver_failure_stays_in_denominator(self):
        with patch.object(p,'call',return_value={'status':'transport_error','error':'timeout'}):self.stage('solver',limit=1)
        self.stage('judge');self.assertEqual(len(self.bodies),0)
        report=self.report()['tracks']['olympiad'];self.assertEqual(report['solver_failures'],1);self.assertEqual(report['success_rate'],0)
    def test_materialize_contains_no_answers(self):
        out=self.root/'bench.jsonl';p.materialize(argparse.Namespace(plan=str(self.plan),output=str(out),sample=20))
        self.assertEqual(len(out.read_text().splitlines()),20);self.assertNotIn('SECRET',out.read_text())
    def test_active_lock_blocks_seal(self):
        (self.root/'.active.lock').touch()
        with self.assertRaises(seal.SealError):seal.seal_evidence(self.root)
    def test_wrong_dataset_hash_rejected(self):
        with self.assertRaises(ValueError):p.prepare(argparse.Namespace(assets=str(self.assets),output=str(self.root/'bad'),solver_config=str(self.root/'config.json'),judge_config=str(self.root/'config.json')))

class JudgeTests(unittest.TestCase):
    def test_threshold(self):
        for n,want in [(6.9,False),(7,True),(10,True),(0,False)]:
            self.assertEqual(p.parse_grade('research',f'Reason\nVERDICT: {n}','stop')['correct'],want)
    def test_invalid_outputs(self):
        for track,text,finish in [('research','VERDICT: NaN','stop'),('research','VERDICT: 11','stop'),('research','VERDICT: -1','stop'),('research','VERDICT: 8/10','stop'),('olympiad','VERDICT: true','stop'),('olympiad','VERDICT: CORRECT','length'),('research','VERDICT: 8\nextra text','stop'),('research','{"score":8,"reason":"x"}','stop')]:
            with self.subTest(text=text),self.assertRaises(ValueError):p.parse_grade(track,text,finish)
    def test_last_line_only(self):
        self.assertFalse(p.parse_grade('olympiad','Earlier VERDICT: CORRECT\nVERDICT: INCORRECT','stop')['correct'])
    def test_audit_does_not_change_verdict(self):
        g=p.parse_grade('research','Total score: 2.0\nVERDICT: 3.5','stop')
        self.assertEqual(g['score'],3.5);self.assertEqual(len(g['audit_flags']),1)
        g=p.parse_grade('research','1 + 0.5 + 0.5 = 3.5\nVERDICT: 3.5','stop')
        self.assertEqual(g['score'],3.5);self.assertEqual(len(g['audit_flags']),1)
    def test_templates_keep_injected_braces(self):
        template=p.JUDGE_PROMPTS['research']
        result=template.format_map({'problem':'x={x}', 'rubric':'{secret}', 'answer':'{rubric}'})
        self.assertIn('The attempted answer: {rubric}',result)
        self.assertIn('The rubric: {secret}',result)


class MmluPolicyTests(unittest.TestCase):
    def test_recover_first_verdict_from_truncation(self):
        g=p.parse_grade('research','Reason\nVERDICT: 7.5\nMore reasoning\nVERDICT: 4', 'length','mmlu_extract_first')
        self.assertEqual(g['score'],7.5)
        self.assertEqual(g['verdict_count'],1)
        self.assertTrue(g['correct'])
        self.assertIn('truncated_judge_verdict_recovered',[x['kind'] for x in g['audit_flags']])
    def test_no_guess_from_numbers_or_partial_eof(self):
        for text in ['Total score: 8.0\nstill thinking','VERDICT: 8','VERDICT: 8.','VERDICT: 11\nVERDICT: 8\n']:
            with self.subTest(text=text),self.assertRaises(ValueError):
                p.parse_grade('research',text,'length','mmlu_extract_first')
    def test_multiple_verdicts_first_and_flag(self):
        g=p.parse_grade('research','VERDICT: 3.5\nVERDICT: 8\n','stop','mmlu_extract_first')
        self.assertEqual(g['score'],3.5)
        self.assertIn('multiple_different_verdicts',[x['kind'] for x in g['audit_flags']])
    def test_olympiad_truncation(self):
        g=p.parse_grade('olympiad','VERDICT: CORRECT\nmore text','length','mmlu_extract_first')
        self.assertTrue(g['correct'])

class MmluDenominatorTests(unittest.TestCase):
    setUp=PipelineTests.setUp
    stage=PipelineTests.stage
    report=PipelineTests.report
    def test_invalid_and_valid_truncated_in_all_case_denominator(self):
        contract=p.read(self.plan/'contract.json')
        contract['scoring_policy']='mmlu_extract_first'
        p.dump(self.plan/'contract.json',contract)
        self.stage('solver',limit=2)
        replies=[{'status':'ok','content':'VERDICT: CORRECT\nmore','finish_reason':'length'},
                 {'status':'ok','content':'no verdict','finish_reason':'length'}]
        with patch.object(p,'call',side_effect=replies):self.stage('judge')
        stats=self.report()['tracks']['olympiad']
        self.assertEqual(stats['successes'],1)
        self.assertEqual(stats['success_rate'],0.5)
        self.assertEqual(stats['judge_invalid'],1)
        self.assertEqual(stats['judge_truncated'],2)
        self.assertEqual(stats['judge_truncated_with_grade'],1)
