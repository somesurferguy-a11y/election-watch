import gzip,json,threading,unittest,urllib.error
from datetime import datetime,timezone
from unittest.mock import patch
import live_collector as collector

class FakeEngine:
 instances=[]
 def __init__(self):
  self.started=False;self.closed=False;self.lock=threading.RLock();self.sources={'florida':{'status':'pending','busy':False,'next_due':0}};self.events=[]
  self.values={};self.db=self;self.instances.append(self)
 def put(self,key,value):self.values[key]=value
 def get(self,key,default=None):return self.values.get(key,default)
 def start(self):self.started=True
 def close(self):self.closed=True
 def state(self):
  if not self.started:raise AssertionError('An unstarted engine must never publish')
  return {'server_time':'2026-11-03T12:00:00Z','settings':{},'sources':self.sources}

class CollectorTests(unittest.TestCase):
 def setUp(self):FakeEngine.instances=[]
 def test_restore_failure_closes_engine_before_retry(self):
  with patch.object(collector,'Engine',FakeEngine):
   def unavailable(path):raise urllib.error.URLError('temporary outage')
   with self.assertRaises(urllib.error.URLError):collector.start_engine(unavailable)
   self.assertTrue(FakeEngine.instances[0].closed)
   self.assertFalse(FakeEngine.instances[0].started)
   def missing(path):raise urllib.error.HTTPError('https://example/checkpoint',404,'missing',{},None)
   engine=collector.start_engine(missing)
   self.assertTrue(engine.started);self.assertIsNot(engine,FakeEngine.instances[0])
 def test_checkpoint_preserves_last_known_votes_backoff_events_and_baseline(self):
  source={'payload':{'races':[{'id':'county','votes':25}]},'status':'error','busy':True,'next_due':123456,'last_success':'2026-11-03T11:59:00Z'}
  checkpoint={'sources':{'florida':source},'events':[{'id':'change'}],'baselines':{'market_baseline':{'x':50}}}
  with patch.object(collector,'Engine',FakeEngine):engine=collector.start_engine(lambda path:gzip.compress(json.dumps(checkpoint).encode()))
  self.assertTrue(engine.started);self.assertFalse(engine.sources['florida']['busy'])
  for key in ['payload','status','next_due','last_success']:self.assertEqual(engine.sources['florida'][key],source[key])
  self.assertEqual(engine.events,checkpoint['events']);self.assertEqual(engine.db.get('market_baseline'),{'x':50})
 def test_corrupt_checkpoint_does_not_start_or_publish_an_empty_engine(self):
  with patch.object(collector,'Engine',FakeEngine):
   with self.assertRaises(gzip.BadGzipFile):collector.start_engine(lambda path:b'corrupt')
  self.assertTrue(FakeEngine.instances[0].closed);self.assertFalse(FakeEngine.instances[0].started)
 def test_full_loop_recovers_after_checkpoint_outage_and_releases_lease(self):
  clock=[0];calls=[];restores=[0]
  class Reply:
   def __init__(self,body):self.body=body
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return self.body
  def urlopen(request,timeout):
   path=request.full_url.rsplit('/',1)[1];calls.append(path)
   if path=='checkpoint' and not request.data:
    restores[0]+=1
    if restores[0]==1:raise urllib.error.URLError('temporary outage')
    raise urllib.error.HTTPError(request.full_url,404,'no saved state',{},None)
   return Reply(b'{}')
  def sleep(seconds):clock[0]+=seconds
  with patch.object(collector,'Engine',FakeEngine),patch.object(collector.urllib.request,'urlopen',side_effect=urlopen),patch.object(collector.time,'monotonic',side_effect=lambda:clock[0]),patch.object(collector.time,'sleep',side_effect=sleep),patch.object(collector,'datetime') as date,patch.dict('os.environ',{'ELECTION_PUBLIC_STATE_URL':'https://example/state.json','ELECTION_PUBLISH_TOKEN':'test'}):
   date.now.return_value=datetime(2026,11,3,tzinfo=timezone.utc);collector.run(minutes=3)
  self.assertEqual(len(FakeEngine.instances),2);self.assertTrue(FakeEngine.instances[0].closed);self.assertTrue(FakeEngine.instances[1].started)
  self.assertEqual(calls.count('publish'),2);self.assertEqual(calls[-1],'release');self.assertTrue(FakeEngine.instances[1].closed)
