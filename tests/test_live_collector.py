import gzip,json,threading,unittest,urllib.error,signal
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
 def simulated_run(self,minutes,dispatch_result=True,standby=False,stop_event=None,publish_error=False,stop_on_publish=False):
  clock=[0];calls=[];attempts=[]
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return b'{}'
  def urlopen(request,timeout):
   path=request.full_url.rsplit('/',1)[1];calls.append(path)
   if standby and path=='lease':raise urllib.error.HTTPError(request.full_url,409,'standby',{},None)
   if publish_error and path=='publish':raise urllib.error.HTTPError(request.full_url,503,'unavailable',{},None)
   if stop_on_publish and path=='publish':stop_event.set()
   if path=='checkpoint' and not request.data:raise urllib.error.HTTPError(request.full_url,404,'missing',{},None)
   return Reply()
  def dispatch():
   attempts.append(clock[0])
   if callable(dispatch_result):return dispatch_result(len(attempts))
   return dispatch_result
  with patch.object(collector,'Engine',FakeEngine),patch.object(collector.urllib.request,'urlopen',side_effect=urlopen),patch.object(collector.time,'monotonic',side_effect=lambda:clock[0]),patch.object(collector.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),patch.object(collector,'dispatch_successor',side_effect=dispatch),patch.object(collector,'datetime') as date,patch.dict('os.environ',{'ELECTION_PUBLIC_STATE_URL':'https://example/state.json','ELECTION_PUBLISH_TOKEN':'test'}),patch('builtins.print'):
   date.now.return_value=datetime(2026,11,3,tzinfo=timezone.utc);collector.run(minutes,stop_event)
  return calls,attempts
 def test_short_rehearsal_dispatches_one_successor_after_publishing(self):
  calls,attempts=self.simulated_run(3)
  self.assertEqual(calls.count('publish'),3);self.assertEqual(attempts,[0]);self.assertEqual(calls[-1],'release')
 def test_successor_retry_waits_five_minutes(self):
  def response(attempt):
   if attempt==1:raise urllib.error.HTTPError('https://api.github.com',503,'retry',{},None)
   return True
  _,attempts=self.simulated_run(12,response)
  self.assertEqual(attempts,[0,300])
 def test_long_run_dispatches_only_in_last_hour(self):
  _,attempts=self.simulated_run(345)
  self.assertEqual(attempts,[285*60])
 def test_standby_never_dispatches(self):
  calls,attempts=self.simulated_run(3,standby=True)
  self.assertEqual(attempts,[]);self.assertNotIn('publish',calls)
 def test_failed_publication_never_dispatches_successor(self):
  calls,attempts=self.simulated_run(3,publish_error=True)
  self.assertEqual(attempts,[]);self.assertEqual(calls.count('publish'),3)
 def test_shutdown_during_publish_releases_without_dispatch(self):
  stop=threading.Event()
  calls,attempts=self.simulated_run(3,stop_event=stop,stop_on_publish=True)
  self.assertTrue(stop.is_set());self.assertEqual(calls.count('publish'),1)
  self.assertEqual(attempts,[]);self.assertEqual(calls[-1],'release')
 def test_runtime_is_bounded(self):
  for minutes in [0,-1,351]:
   with self.assertRaises(ValueError):collector.run(minutes)
 def test_dispatch_uses_only_fixed_github_api_and_main_ref(self):
  class Reply:
   status=204
   def __enter__(self):return self
   def __exit__(self,*args):pass
  with patch.dict('os.environ',{'GITHUB_TOKEN':'ephemeral-test','GITHUB_REPOSITORY':'owner/election-watch'}),patch.object(collector,'datetime') as date,patch.object(collector.urllib.request,'urlopen',return_value=Reply()) as open_url,patch('builtins.print'):
   date.now.return_value=datetime(2026,11,3,tzinfo=timezone.utc)
   self.assertTrue(collector.dispatch_successor())
   request=open_url.call_args.args[0]
   self.assertEqual(request.full_url,'https://api.github.com/repos/owner/election-watch/actions/workflows/live.yml/dispatches');self.assertEqual(json.loads(request.data),{'ref':'main'})
   date.now.return_value=datetime(2026,11,11,tzinfo=timezone.utc)
   self.assertFalse(collector.dispatch_successor());self.assertEqual(open_url.call_count,1)
 def test_dispatch_rejects_unsafe_repository_and_missing_token(self):
  with patch.object(collector.urllib.request,'urlopen') as open_url:
   for repo in ['owner/repo/extra','owner/repo?query=x','owner/..','https://evil.example/repo']:
    with patch.dict('os.environ',{'GITHUB_TOKEN':'test','GITHUB_REPOSITORY':repo}):
     with self.assertRaises(ValueError):collector.dispatch_successor()
   with patch.dict('os.environ',{'GITHUB_TOKEN':'','GITHUB_REPOSITORY':'owner/repo'}):self.assertFalse(collector.dispatch_successor())
   open_url.assert_not_called()
 def test_sigterm_interrupts_idle_wait_and_releases_lease(self):
  class Stop:
   stopped=False
   def is_set(self):return self.stopped
   def set(self):self.stopped=True
   def wait(self,delay):signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
  previous=signal.getsignal(signal.SIGTERM)
  calls,_=self.simulated_run(3,stop_event=Stop())
  self.assertEqual(calls.count('publish'),1);self.assertEqual(calls[-1],'release');self.assertIs(signal.getsignal(signal.SIGTERM),previous)
