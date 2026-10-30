"""Overlapping free runners, one leased publisher; no laptop dependency."""
import os,time,json,gzip,uuid,urllib.request,urllib.error,logging,copy,re,signal,threading
from datetime import datetime,timezone
from store import Engine

def start_engine(send):
 """Publish only after a complete restore and successful scheduler startup."""
 engine=Engine()
 try:
  try:
   checkpoint=json.loads(gzip.decompress(send('/checkpoint')))
   for key,source in checkpoint['sources'].items():
    if key in engine.sources:engine.sources[key].update(source);engine.sources[key]['busy']=False
   engine.events=checkpoint.get('events',[])
   for key,value in checkpoint.get('baselines',{}).items():engine.db.put(key,value)
  except urllib.error.HTTPError as exc:
   if exc.code!=404:raise
  engine.start()
  return engine
 except BaseException:
  engine.close()
  raise

def dispatch_successor():
 """Use only this run's ephemeral GitHub token; never send it to Cloudflare."""
 token=os.environ.get('GITHUB_TOKEN','')
 repo=os.environ.get('GITHUB_REPOSITORY','')
 if not token or not repo:return False
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+',repo) or repo.rsplit('/',1)[1] in ['.','..']:
  raise ValueError('Invalid GitHub repository')
 if datetime.now(timezone.utc).date().isoformat()>'2026-11-10':return False
 request=urllib.request.Request('https://api.github.com/repos/'+repo+'/actions/workflows/live.yml/dispatches',data=json.dumps({'ref':'main'}).encode(),method='POST',headers={'User-Agent':'ElectionWatch/2.0','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=15) as response:
  if response.status!=204:raise ValueError('Unexpected workflow dispatch response')
 print('Successor collector requested',flush=True)
 return True

def run(minutes=345,stop_event=None):
 if not 0<minutes<=350:raise ValueError('Collector duration must be between 1 and 350 minutes')
 endpoint=os.environ['ELECTION_PUBLIC_STATE_URL'].removesuffix('/state.json')
 if not endpoint.startswith('https://'):raise ValueError('HTTPS endpoint required')
 token=os.environ['ELECTION_PUBLISH_TOKEN'];owner=uuid.uuid4().hex;engine=None
 deadline=time.monotonic()+minutes*60
 successor_dispatched=False;last_dispatch_attempt=float('-inf')
 previous_handler=None
 if stop_event is not None and threading.current_thread() is threading.main_thread():
  previous_handler=signal.signal(signal.SIGTERM,lambda *_:stop_event.set())
 def send(path,body=b'',extra=None):
  req=urllib.request.Request(endpoint+path,data=body,method='POST',headers={'User-Agent':'ElectionWatch/2.0','Authorization':'Bearer '+token,'X-Collector-ID':owner,**(extra or {})})
  with urllib.request.urlopen(req,timeout=5 if path=='/release' else 25) as response:return response.read()
 try:
  while not (stop_event and stop_event.is_set()) and time.monotonic()<deadline and datetime.now(timezone.utc).date().isoformat()<='2026-11-10':
   cycle=time.monotonic()
   try:
    send('/lease')
    if engine is None:
     engine=start_engine(send)
    state=engine.state();state['settings'].update(view='indian_river',pins=[]);state['settings_revision']=0
    with engine.lock:
     checkpoint={'sources':copy.deepcopy(engine.sources),'events':copy.deepcopy(engine.events),'baselines':{key:engine.db.get(key,{}) for key in ['market_baseline','poll_baseline']}}
    checkpoint_raw=gzip.compress(json.dumps(checkpoint,allow_nan=False).encode())
    send('/checkpoint',checkpoint_raw,{'Content-Encoding':'gzip','X-Snapshot-Time':state['server_time']})
    raw=json.dumps(state,ensure_ascii=False,allow_nan=False).encode()
    send('/publish',gzip.compress(raw),{'Content-Encoding':'gzip','Content-Type':'application/json','X-Snapshot-Time':state['server_time']})
    print('Published snapshot',state['server_time'],flush=True)
    now=time.monotonic()
    if not (stop_event and stop_event.is_set()) and not successor_dispatched and 0<deadline-now<=3600 and now-last_dispatch_attempt>=300:
     last_dispatch_attempt=now
     try:successor_dispatched=dispatch_successor()
     except urllib.error.HTTPError as exc:logging.warning('Successor dispatch HTTP %s',exc.code)
     except Exception as exc:logging.warning('Successor dispatch %s',type(exc).__name__)
   except urllib.error.HTTPError as exc:
    if exc.code==409:
     if engine:engine.close();engine=None
     print('Standby: another collector holds the publishing lease',flush=True)
    else:logging.warning('Publish HTTP %s',exc.code)
   except Exception as exc:logging.warning('Collector %s',type(exc).__name__)
   delay=max(0,min(60-(time.monotonic()-cycle),deadline-time.monotonic()))
   if stop_event:stop_event.wait(delay)
   else:time.sleep(delay)
 finally:
  try:send('/release')
  except Exception:pass
  if engine:engine.close()
  if previous_handler is not None:signal.signal(signal.SIGTERM,previous_handler)
if __name__=='__main__':run(int(os.environ.get('COLLECTOR_MINUTES','345')),threading.Event())
