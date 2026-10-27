"""Build the public display; never export local host controls or credentials."""
import json,shutil,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from store import Engine
import config

def build():
 out=config.ROOT/'public';out.mkdir(exist_ok=True)
 engine=Engine(config.ROOT/'.pages-cache')
 try:
  due=[key for key,source in engine.sources.items() if time.time()>=source['next_due']]
  with ThreadPoolExecutor(max_workers=7) as pool:list(pool.map(engine.refresh_one,due))
  snapshot=engine.state()
  snapshot['settings']['view']='indian_river'
  snapshot['settings_revision']=0
  snapshot['settings']['pins']=[]
  (out/'state.json').write_text(json.dumps(snapshot,ensure_ascii=False,allow_nan=False),encoding='utf-8')
 finally:engine.close()
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
 app=app.replace("fetch('/api/v1/state'","fetch('./state.json?t='+Date.now()")
 app=app.replace('state=incoming;online=true;',"state=incoming;Object.assign(state.settings,JSON.parse(localStorage.getItem('election-watch-prefs')||'{}'));online=true;")
 app=app.replace('setInterval(load,5000)','setInterval(load,30000)')
 (out/'static/js/app.js').write_text(app,encoding='utf-8')
 profile=out/'static/js/candidate-profiles.js'
 profile.write_text(profile.read_text(encoding='utf-8').replace('${esc(path)}','${esc("."+path)}'),encoding='utf-8')
 (out/'static/js/pages-status.js').write_text('''function pagesStatus(){if(!state)return;const age=Math.max(0,(Date.now()-Date.parse(state.server_time))/60000);const stale=age>15;const b=document.getElementById('mode-banner');b.className=stale?'error':'';b.textContent=(stale?'DELAYED SNAPSHOT':'AUTOMATIC SNAPSHOT')+' · '+Math.floor(age)+' minutes old · Scheduled checks about every 5 minutes; publishing may be delayed. Source times in Source health.';document.getElementById('connection').textContent=online?'Public snapshot connected':'Disconnected · saved snapshot';document.getElementById('checked').textContent='Snapshot generated '+time(state.server_time);}setInterval(pagesStatus,1000);''',encoding='utf-8')
 print('Public display built:',out)
if __name__=='__main__':build()
