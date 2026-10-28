"""Overlapping free runners, one leased publisher; no laptop dependency."""
import os,time,json,gzip,uuid,urllib.request,urllib.error,logging,copy
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

def run(minutes=125):
 endpoint=os.environ['ELECTION_PUBLIC_STATE_URL'].removesuffix('/state.json')
 if not endpoint.startswith('https://'):raise ValueError('HTTPS endpoint required')
 token=os.environ['ELECTION_PUBLISH_TOKEN'];owner=uuid.uuid4().hex;engine=None
 deadline=time.monotonic()+minutes*60
 def send(path,body=b'',extra=None):
  req=urllib.request.Request(endpoint+path,data=body,method='POST',headers={'User-Agent':'ElectionWatch/2.0','Authorization':'Bearer '+token,'X-Collector-ID':owner,**(extra or {})})
  with urllib.request.urlopen(req,timeout=25) as response:return response.read()
 try:
  while time.monotonic()<deadline and datetime.now(timezone.utc).date().isoformat()<='2026-11-10':
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
   except urllib.error.HTTPError as exc:
    if exc.code==409:
     if engine:engine.close();engine=None
     print('Standby: another collector holds the publishing lease',flush=True)
    else:logging.warning('Publish HTTP %s',exc.code)
   except Exception as exc:logging.warning('Collector %s',type(exc).__name__)
   time.sleep(max(0,60-(time.monotonic()-cycle)))
 finally:
  try:send('/release')
  except Exception:pass
  if engine:engine.close()
if __name__=='__main__':run(int(os.environ.get('COLLECTOR_MINUTES','125')))
