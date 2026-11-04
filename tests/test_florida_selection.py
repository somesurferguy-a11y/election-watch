import copy,tempfile,unittest
from unittest.mock import patch
from roster import load_roster
from store import Engine
from validation import validate_results
from feeds import florida_feed
class FloridaSourceSelectionTests(unittest.TestCase):
 def test_primary_request_bypasses_cached_base_url(self):
  with patch('feeds.fetch_url',return_value=('file','timestamp')) as fetch,patch('feeds.parse_florida',return_value={'ok':True}):
   self.assertEqual(florida_feed(),{'ok':True});self.assertIn('?_ew_check=',fetch.call_args.args[0])
 def test_partial_fallback_never_adds_to_primary_or_overrides_nonzero_primary(self):
  base=next(copy.deepcopy(r) for r in load_roster()['races'] if r['scope']=='florida' and r['office_code']=='GOV')
  def payload(votes,partial):
   r=copy.deepcopy(base);r.update(status='unofficial' if votes else 'awaiting',source_name='Official Florida county reports (partial)' if partial else 'Florida Division of Elections',source_url='https://floridaelectionwatch.gov/CountyReportingStatus',source_updated_at='2026-11-04T00:00:00Z')
   for i,c in enumerate(r['candidates']):c['votes']=votes if i==0 else 0
   if partial:r.update(partial_coverage=True,counties_included=[{'code':'IND'}],coverage_note='Partial official county totals')
   return validate_results({'election_date':'2026-11-03','demo':False,'source_updated_at':r['source_updated_at'],'races':[r]})
  with tempfile.TemporaryDirectory() as path:
   engine=Engine(path)
   try:
    engine.accept('florida',payload(0,False));engine.accept('florida_counties',payload(100,True))
    r=next(r for r in engine.state()['races'] if r['id']==base['id']);self.assertTrue(r['partial_coverage']);self.assertEqual(r['candidates'][0]['votes'],100);self.assertEqual(len(r['counties_included']),1)
    engine.accept('florida',payload(500,False));r=next(r for r in engine.state()['races'] if r['id']==base['id']);self.assertEqual(r['candidates'][0]['votes'],500);self.assertFalse(r.get('partial_coverage',False));self.assertEqual(r['source_name'],'Florida Division of Elections')
   finally:engine.close();engine.db.conn.close()

 def test_unknown_county_candidate_votes_stay_unavailable_after_roster_merge(self):
  from roster import merge_race
  base={'id':'r','name':'R','candidates':[{'id':'a','name':'A','votes':0},{'id':'b','name':'B','votes':0}]}
  result={'status':'unofficial','partial_coverage':True,'candidates':[{'id':'a','name':'A','votes':10,'votes_available':True},{'id':'b','name':'B','votes':0,'votes_available':False}]}
  r=merge_race(base,result);self.assertFalse(r['candidates'][1]['votes_available']);self.assertTrue(r['result_incomplete']);self.assertIsNone(r['candidates'][1]['percentage'])

 def test_unknown_aggregate_writein_stays_unavailable_as_extra(self):
  from roster import merge_race
  base={'id':'r','name':'R','candidates':[{'id':'a','name':'A','votes':0}]}
  result={'status':'unofficial','partial_coverage':True,'candidates':[{'id':'a','name':'A','votes':10,'votes_available':True},{'id':'write','name':'Write-in totals','votes':2,'votes_available':False}]}
  r=merge_race(base,result);self.assertFalse(r['candidates'][1]['votes_available']);self.assertTrue(r['result_incomplete']);self.assertIsNone(r['candidates'][0]['percentage'])

 def test_partial_source_retries_after_one_minute_and_preserves_last_payload(self):
  import time
  with tempfile.TemporaryDirectory() as path:
   engine=Engine(path)
   try:
    engine.sources['florida_counties'].update(failures=20,payload={'races':[],'marker':'retained'})
    with patch.dict('store.ADAPTERS',{'florida_counties':lambda previous=None:(_ for _ in ()).throw(ValueError('county coverage lost'))}):engine.refresh_one('florida_counties')
    source=engine.sources['florida_counties'];self.assertLessEqual(source['next_due']-time.time(),61);self.assertEqual(source['payload']['marker'],'retained')
   finally:engine.close();engine.db.conn.close()
