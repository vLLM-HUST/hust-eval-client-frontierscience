import tempfile
import unittest
from pathlib import Path
from hust_eval_frontierscience.bench import bench

class BenchTests(unittest.TestCase):
    def test_dry_run_freezes_inputs_and_command(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); data=root/'data.jsonl';data.write_text('{"prompt":"one"}\n{"prompt":"two"}\n')
            result=bench(root/'run','fs',str(data),'http://localhost:18180','qwen3.5-35b','/models/test',2,256,'vllm',True)
            self.assertEqual(result['command'][:3],['vllm','bench','serve'])
            self.assertEqual(result['dataset_rows'],2)
            self.assertEqual((root/'run/inputs/fs.materialized.jsonl').read_bytes(),data.read_bytes())
            self.assertFalse((root/'run/outputs/fs.json').exists())
    def test_refuse_implicit_repeated_cases(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=root/'data.jsonl';data.write_text('{"prompt":"one"}\n')
            with self.assertRaises(ValueError):bench(root/'run','fs',str(data),'http://localhost','model','tok',2,256,'vllm',True)
