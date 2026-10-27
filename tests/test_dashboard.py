import copy
import json
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import config
from feeds import parse_florida,parse_irc,parse_poly,parse_kalshi,market_record,parse_openamerica
from store import Engine,chamber_summary,fingerprint
from server import DashboardServer
from validation import validate_results,validate_polls

NOW=datetime(2026,11,4,12,tzinfo=timezone.utc)
TEST_TMP=Path(__file__).resolve().parent/'runtime'
TEST_TMP.mkdir(exist_ok=True)

def payload(votes=(110,90)):
    return {'election_date':'2026-11-03','demo':False,'source_updated_at':'2026-11-04T10:00:00Z','races':[
      {'id':'us:test','seat_id':'US-TEST','name':'Test U.S. House district','jurisdiction':'Test state','scope':'national','chamber':'house','status':'unofficial',
       'source_name':'Test official source','source_url':'https://example.org/results','source_updated_at':'2026-11-04T10:00:00Z',
       'candidates':[{'id':'a','name':'Candidate A','party':'DEM','votes':votes[0]},{'id':'b','name':'Candidate B','party':'REP','votes':votes[1]}]}]}

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.patcher=patch('validation.datetime',wraps=datetime);self.dt=self.patcher.start();self.dt.now.return_value=NOW
    def tearDown(self):self.patcher.stop()
    def test_shares_derived(self):self.assertEqual(validate_results(payload())['races'][0]['candidates'][0]['percentage'],55)
    def test_primary_rejected(self):
        p=payload();p['election_date']='2026-08-18'
        with self.assertRaises(ValueError):validate_results(p)
    def test_demo_import_rejected(self):
        p=payload();p['demo']=True
        with self.assertRaises(ValueError):validate_results(p)
    def test_pre_election_counts_rejected(self):
        self.dt.now.return_value=datetime(2026,10,26,tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError,'pre-election'):validate_results(payload())
    def test_winner_needs_attribution(self):
        p=payload();p['races'][0]['status']='projected'
        with self.assertRaises(ValueError):validate_results(p)
    def test_negative_nan_and_fraction_votes(self):
        for value in [-1,float('nan'),1.5,True]:
            with self.subTest(value=value),self.assertRaises(ValueError):validate_results(payload((value,1)))
    def test_duplicate_candidate_rejected(self):
        p=payload();p['races'][0]['candidates'][1]['id']='a'
        with self.assertRaises(ValueError):validate_results(p)
    def test_naive_timestamp_rejected(self):
        p=payload();p['source_updated_at']='2026-11-04T10:00:00'
        with self.assertRaises(ValueError):validate_results(p)
    def test_javascript_link_rejected(self):
        p=payload();p['races'][0]['source_url']='javascript:alert(1)'
        with self.assertRaises(ValueError):validate_results(p)
    def test_duplicate_race_rejected(self):
        p=payload();p['races'].append(copy.deepcopy(p['races'][0]))
        with self.assertRaises(ValueError):validate_results(p)
    def test_poll_missing_method_rejected(self):
        with self.assertRaises(ValueError):validate_polls({'election_date':config.ELECTION_DATE,'demo':False,'polls':[{'id':'one'}]})

class ParserTests(unittest.TestCase):
    def test_florida_official_fixture(self):
        text=(Path(__file__).parent/'fixtures'/'fl-general.tsv').read_text(encoding='utf-8')
        p=parse_florida(text,'2026-10-19T16:17:13Z')
        self.assertTrue(p['races']);self.assertTrue(all(r['status']=='awaiting' for r in p['races']))
        self.assertTrue(any(r['scope']=='indian_river' for r in p['races']))
        self.assertEqual(sum(c['votes'] for r in p['races'] for c in r['candidates']),0)
    def test_wrong_date_rejected(self):
        text=(Path(__file__).parent/'fixtures'/'fl-general.tsv').read_text().replace('11/03/2026','08/18/2026')
        with self.assertRaisesRegex(ValueError,'date mismatch'):parse_florida(text)
    def test_duplicate_rows_not_summed(self):
        text=(Path(__file__).parent/'fixtures'/'fl-general.tsv').read_text();lines=text.splitlines()
        duplicate=next(line for line in lines[1:] if line.strip())
        with self.assertRaises(ValueError):parse_florida(text+'\n'+duplicate)
    def test_bad_layout_rejected(self):
        with self.assertRaises(ValueError):parse_florida('<html>temporarily unavailable</html>')
    def test_enr_fixture_schema(self):
        text=(Path(__file__).parent/'fixtures'/'enr-general.html').read_text(encoding='utf-8')
        p=parse_irc(text,'https://example.org/results')
        self.assertEqual(len(p['races']),1);self.assertGreater(len(p['races'][0]['candidates']),1)
        self.assertEqual(p['races'][0]['name'],'United States Senator')
    def test_test_results_rejected(self):
        with self.assertRaisesRegex(ValueError,'testing data'):parse_irc('<h1>Test Results Only</h1>','https://example.org/')
    def test_primary_enr_rejected(self):
        with self.assertRaises(ValueError):parse_irc('<h1>Official Primary Election</h1><h2>Election Date: 8/18/2026</h2>','https://example.org/')
    def test_poly_string_encoded_arrays(self):
        markets=[{'id':'123','question':'Will the Democratic Party control the House after the 2026 Midterm elections?','outcomes':'["Yes","No"]','outcomePrices':'["0.61","0.39"]','bestBid':.6,'bestAsk':.62,'slug':'test'}]
        p=parse_poly(markets,'control-house')[0];self.assertEqual(p['probability'],61);self.assertIn('Democratic',p['outcome']);self.assertIsNone(p['quote_updated_at'])
    def test_wrong_market_year_rejected(self):
        with self.assertRaises(ValueError):parse_kalshi({'ticker':'CONTROLS-2028-D'})
    def test_kalshi_dollar_fields(self):
        p=parse_kalshi({'ticker':'CONTROLS-2026-D','title':'Will Democrats win the U.S. Senate in 2026?','yes_bid_dollars':'0.64','yes_ask_dollars':'0.65','status':'active'})
        self.assertEqual(p['probability'],64.5);self.assertEqual(p['spread_pp'],1)
    def test_zero_bid_is_not_missing(self):
        p=market_record('Test','1','q','yes',0,.02,.01,None,0,None,'','', 'open','g');self.assertEqual(p['spread_pp'],2)
    def test_national_before_election_empty_is_valid(self):
        p=parse_openamerica({'api':1,'year':2026,'office':'Senate','as_of':None,'races':{}},'Senate')
        self.assertEqual(p['races'],[])
    def test_national_replay_cannot_enter_live(self):
        with self.assertRaisesRegex(ValueError,'replay'):parse_openamerica({'api':1,'year':2024,'office':'Senate','races':{}},'Senate')
    def test_national_never_duplicates_florida(self):
        p=parse_openamerica({'api':1,'year':2026,'office':'Senate','races':{'FL':{}}},'Senate')
        self.assertEqual(p['races'],[])
    def test_national_totals_must_agree(self):
        with self.assertRaises(ValueError):parse_openamerica({'api':1,'year':2026,'office':'House','races':{'AZ-01':{'total':10,'cands':[{'n':'A','p':'D','v':9}]}}},'House')

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=TEST_TMP);self.engine=Engine(self.temp.name)
        self.patcher=patch('validation.datetime',wraps=datetime);self.dt=self.patcher.start();self.dt.now.return_value=NOW
    def tearDown(self):self.patcher.stop();self.engine.close();self.engine.db.conn.close();self.temp.cleanup()
    def test_unchanged_data_does_not_change_publication_time(self):
        self.engine.accept('national',validate_results(payload()));before=self.engine.sources['national'].copy()
        self.engine.accept('national',validate_results(payload()));after=self.engine.sources['national']
        self.assertEqual(before['source_updated_at'],after['source_updated_at']);self.assertEqual(before['last_observed_change'],after['last_observed_change'])
    def test_error_preserves_last_good_data(self):
        self.engine.accept('national',validate_results(payload()));before=self.engine.sources['national']['last_success']
        with patch.dict('store.ADAPTERS',{'national':lambda:(_ for _ in ()).throw(ValueError('bad feed'))}):self.engine.refresh_one('national')
        s=self.engine.sources['national'];self.assertEqual(s['last_success'],before);self.assertEqual(s['status'],'error');self.assertTrue(s['payload']['races'])
    def test_lead_change_event_not_winner(self):
        self.engine.accept('national',validate_results(payload()));self.engine.accept('national',validate_results(payload((90,110))))
        self.assertIn('takes the lead',self.engine.events[-1]['text']);self.assertNotIn('projected',self.engine.events[-1]['text'])
    def test_correction_event(self):
        self.engine.accept('national',validate_results(payload()));self.engine.accept('national',validate_results(payload((90,80))))
        self.assertIn('corrected',self.engine.events[-1]['text'])
    def test_chambers_never_count_leaders(self):
        p=validate_results(payload());self.assertEqual(chamber_summary(p['races'])[0]['seats']['DEM'],0)
    def test_attributed_call_counted(self):
        p=payload();p['races'][0].update(status='projected',winner_id='a',call_source='Test desk',call_at='2026-11-04T10:00:00Z');p=validate_results(p)
        self.assertEqual(chamber_summary(p['races'])[0]['seats']['DEM'],1)
    def test_settings_persist_and_validate(self):
        self.engine.update_settings({'pins':['test'],'rotation_seconds':20});self.assertEqual(self.engine.db.get('settings')['pins'],['test'])
        with self.assertRaises(ValueError):self.engine.update_settings({'rotation_seconds':0})
    def test_pins_do_not_reset_display_revision(self):
        revision=self.engine.settings_revision;self.engine.update_settings({'pins':['abc']});self.assertEqual(self.engine.settings_revision,revision)
    def test_demo_always_explicit(self):
        self.engine.update_settings({'mode':'demo'});s=self.engine.state();self.assertTrue(s['demo']);self.assertTrue(all(e['demo'] for e in s['ticker_events']))
    def test_manual_snapshots_not_labeled_connected(self):
        self.engine.accept('national',validate_results(payload()),imported=True);self.engine.refresh_one('national')
        self.assertEqual(self.engine.sources['national']['status'],'imported')
    def test_fingerprint_ignores_retrieval_metadata(self):
        self.assertEqual(fingerprint({'x':1,'retrieved_at':'a'}),fingerprint({'x':1,'retrieved_at':'b'}))

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=TEST_TMP);self.engine=Engine(self.temp.name);self.server=DashboardServer(('127.0.0.1',0),self.engine)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.engine.close();self.engine.db.conn.close();self.temp.cleanup()
    def request(self,path,body=None,headers=None):
        return urllib.request.urlopen(urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers or {}))
    def test_routes_and_static_assets(self):
        for path in ['/','/host','/static/css/tv.css','/static/js/app.js','/api/v1/state','/health']:
            with self.subTest(path=path),self.request(path) as r:self.assertEqual(r.status,200)
    def test_csrf_required(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/v1/settings',{'mode':'demo'},{'Content-Type':'application/json'})
        self.assertEqual(cm.exception.code,403)
    def test_cross_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/v1/settings',{'mode':'demo'},{'Content-Type':'application/json','X-CSRF-Token':self.server.csrf,'Origin':'https://evil.example'})
        self.assertEqual(cm.exception.code,403)
    def test_settings_round_trip(self):
        with self.request('/api/v1/settings',{'mode':'demo'},{'Content-Type':'application/json','X-CSRF-Token':self.server.csrf}) as r:self.assertEqual(r.status,200)
        with self.request('/api/v1/state') as r:self.assertTrue(json.load(r)['demo'])
    def test_path_traversal_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/static/../config.py')
        self.assertEqual(cm.exception.code,403)
    def test_unknown_host_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/v1/admin',headers={'Host':'evil.example'})
        self.assertEqual(cm.exception.code,403)
    def test_import_sample_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/v1/import',{'source':'national','data':{'demo':True}},{'Content-Type':'application/json','X-CSRF-Token':self.server.csrf})
        self.assertEqual(cm.exception.code,400)

if __name__=='__main__':unittest.main()
