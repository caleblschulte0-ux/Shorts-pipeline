import json,tempfile,unittest
from pathlib import Path
from review_prototypes.advanced_capabilities import *
class Tests(unittest.TestCase):
 def test_catalog(self):self.assertEqual(validate_catalog(),());self.assertGreaterEqual(len(CAPABILITIES),38);self.assertEqual(required_secret_names(),())
 def test_light_fallback(self):self.assertEqual(Router().route(RouteRequest("x",Need.LOCAL_SCRIPT,allow_heavy=False)).capabilities,("deterministic-writer",))
 def test_data_route(self):self.assertIn("duckdb-analysis",Router().route(RouteRequest("x",Need.DATA_STORY)).capabilities)
 def test_gpu_route(self):self.assertIn("whisperx-alignment",Router().route(RouteRequest("x",Need.WORD_SYNC_CAPTIONS,allow_gpu=True)).capabilities)
 def test_ollama(self):self.assertEqual(Planner().ollama(LocalPrompt("json","ContentPlan")).secret_names,())
 def test_geocode(self):self.assertEqual(Planner().geocode("Sioux Falls","pipeline-test").provider,"nominatim")
 def test_data_gate(self):self.assertIn("unit_mismatch",DataGate().compare((Series("a","%","US","1","m"),Series("b","$","US","1","m"))))
 def test_karaoke(self):self.assertIn(r"{\k40}Hello",Karaoke().build((Word("Hello",0,.4),Word("world",.4,.9))))
 def test_sfx(self):self.assertEqual(Planner().procedural_sfx("x.wav").env_names,())
 def test_fts(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);s=p/"r.jsonl";s.write_text(json.dumps({"id":"1","text":"hello"})+"\n");o=p/"x.db";fts_index(s,o);self.assertTrue(o.exists())
 def test_csv(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/"x.csv";p.write_text("name,value\nA,1\n");self.assertTrue(validate_csv(p,("name","value"))["ok"])
if __name__=="__main__":unittest.main()
