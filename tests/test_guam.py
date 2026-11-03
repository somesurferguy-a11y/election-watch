import copy,hashlib,io,json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from territories import reviewed_payload,guam_feed
from store import Engine,chamber_summary
BASE=json.loads((Path(__file__).resolve().parents[1]/'data'/'guam_reviewed.json').read_text(encoding='utf-8'))
class GuamTests(unittest.TestCase):
 def test_saved_primary_report_fingerprint(self):
  raw=(Path(__file__).resolve().parents[1]/'data'/'evidence'/'guam-gec-unofficial-2026-11-04-0130.pdf').read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),BASE['verification_sha256'])
 def test_report_totals_and_no_winner_calls(self):
  data=reviewed_payload(copy.deepcopy(BASE));self.assertEqual([r['report_total'] for r in data['races']],[30994,30677,30254]);self.assertTrue(all(r['status']=='unofficial' and not r.get('winner_id') for r in data['races']))
  self.assertEqual(data['races'][0]['candidates'][0]['votes'],15945);self.assertEqual(data['races'][1]['candidates'][0]['votes'],15645)
 def test_delegate_cannot_change_congress_power(self):
  summary=chamber_summary(reviewed_payload(copy.deepcopy(BASE))['races']);self.assertTrue(all(sum(c['seats'].values())==0 for c in summary))
  data=copy.deepcopy(BASE);data['races'][1]['chamber']='house'
  with self.assertRaises(ValueError):reviewed_payload(data)
 def test_mismatch_or_certification_is_rejected(self):
  for field,value in [('report_total',1),('status','certified')]:
   data=copy.deepcopy(BASE);data['races'][0][field]=value
   with self.assertRaises(ValueError):reviewed_payload(data)
 def test_matching_report_and_changed_report_guard(self):
  raw=b'reviewed report';data=copy.deepcopy(BASE);data['verification_sha256']=hashlib.sha256(raw).hexdigest()
  with patch('territories.json.loads',return_value=data),patch('territories.urllib.request.urlopen',return_value=io.BytesIO(raw)):
   self.assertEqual(len(guam_feed()['races']),3)
  with patch('territories.json.loads',return_value=data),patch('territories.urllib.request.urlopen',return_value=io.BytesIO(b'changed')):
   with self.assertRaisesRegex(ValueError,'changed'):guam_feed()
 def test_state_keeps_guam_separate_from_chamber_totals(self):
  with tempfile.TemporaryDirectory() as d:
   engine=Engine(d)
   try:
    engine.accept('guam',reviewed_payload(copy.deepcopy(BASE)));state=engine.state();rows=[r for r in state['races'] if r['id'].startswith('guam:')];self.assertEqual(len(rows),3);self.assertTrue(all(r['has_results'] for r in rows));self.assertTrue(all(sum(c['seats'].values())==0 for c in state['chambers']))
   finally:engine.close();engine.db.conn.close()
