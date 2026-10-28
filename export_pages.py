"""Build the public display; never export local host controls or credentials."""
import json,shutil,time,os,gzip,urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from store import Engine
import config

def build():
 live_url=os.environ.get('ELECTION_PUBLIC_STATE_URL','').strip()
 if live_url:
  parsed=urlsplit(live_url)
  if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
   raise ValueError('Public live-data URL must be HTTPS without credentials, query, or fragment')
 out=config.ROOT/'public';out.mkdir(exist_ok=True)
 if live_url:
  with urllib.request.urlopen(urllib.request.Request(live_url,headers={'User-Agent':'ElectionWatch/2.0'}),timeout=25) as response:
   raw=response.read(12000001)
   if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
  snapshot=json.loads(raw)
  if snapshot.get('demo') is not False or not isinstance(snapshot.get('races'),list):raise ValueError('Live service did not provide an election snapshot')
 else:
  engine=Engine(config.ROOT/'.pages-cache')
  try:
   due=[key for key,source in engine.sources.items() if time.time()>=source['next_due']]
   with ThreadPoolExecutor(max_workers=7) as pool:list(pool.map(engine.refresh_one,due))
   snapshot=engine.state()
  finally:engine.close()
 snapshot['settings']['view']='indian_river'
 snapshot['settings_revision']=0
 snapshot['settings']['pins']=[]
 (out/'state.json').write_text(json.dumps(snapshot,ensure_ascii=False,allow_nan=False),encoding='utf-8')
 shutil.copytree(config.ROOT/'static',out/'static',dirs_exist_ok=True,ignore=shutil.ignore_patterns('templates','host.js'))
 for extra in ['host.js']:
  (out/'static/js'/extra).unlink(missing_ok=True)
 html=(config.ROOT/'templates/index.html').read_text(encoding='utf-8').replace('href="/static/','href="./static/').replace('src="/static/','src="./static/')
 html=html.replace('<a href="/host" target="_blank" rel="noopener">Host controls</a>','<span>Public TV display</span>')
 html=html.replace('</head>','<script defer src="./static/js/pages-status.js"></script></head>')
 (out/'index.html').write_text(html,encoding='utf-8');(out/'.nojekyll').touch()
 app=(out/'static/js/app.js').read_text(encoding='utf-8')
 start=app.index('async function post(');end=app.index('\n',start)
 app=app[:start]+'''async function post(path,body){if(path!=='/api/v1/settings')throw Error('Public display only');const prefs=JSON.parse(localStorage.getItem('election-watch-prefs')||'{}');Object.assign(prefs,body);localStorage.setItem('election-watch-prefs',JSON.stringify(prefs));return {ok:true};}'''+app[end:]
 endpoint=json.dumps(live_url or './state.json')
 app=app.replace("fetch('/api/v1/state'",'fetch('+endpoint+"+'?t='+Date.now()")
 app=app.replace('state=incoming;online=true;',"state=incoming;Object.assign(state.settings,JSON.parse(localStorage.getItem('election-watch-prefs')||'{}'));online=true;")
 app=app.replace('setInterval(load,5000)','setInterval(load,60000)')
 app=app.replace('updateFreshness();updateCountdowns();}',"updateFreshness();updateCountdowns();if(typeof pagesStatus==='function')pagesStatus();}")
 (out/'static/js/app.js').write_text(app,encoding='utf-8')
 profile=out/'static/js/candidate-profiles.js'
 profile.write_text(profile.read_text(encoding='utf-8').replace('${esc(path)}','${esc("."+path)}'),encoding='utf-8')
 note='Live-data checks every 60 seconds; source publishing may be delayed.' if live_url else 'Scheduled snapshots; publishing may be delayed.'
 status=(config.ROOT/'static/js/pages-status.js').read_text(encoding='utf-8')
 (out/'static/js/pages-status.js').write_text('const PAGE_SNAPSHOT_LIMIT='+str(3 if live_url else 15)+';\nconst PAGE_REFRESH_NOTE='+json.dumps(note)+';\n'+status,encoding='utf-8')
 print('Public display built:',out)
if __name__=='__main__':build()
