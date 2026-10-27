"""Regenerate fictional fixtures. Never uses actual candidates or pollsters."""
import json
from pathlib import Path

def race(rid,name,scope,people,**extra):
    total=sum(p[2] for p in people)
    return {'id':rid,'name':name,'scope':scope,'jurisdiction':'Fictional demonstration','status':'unofficial','is_complete':False,
        'source_name':'Fictional demo fixture','source_url':'','source_updated_at':None,'demo':True,'precincts_reporting':32,'precincts_total':50,
        'candidates':[{'id':rid+':'+str(i),'name':n,'party':p,'votes':v,'percentage':v/total*100} for i,(n,p,v) in enumerate(people)],**extra}
races=[
 race('demo:fl-governor','Florida governor — sample contest','florida',[('Jordan Ellis','DEM',4238117),('Casey Monroe','REP',4027441),('Taylor Brooks','NPA',141322)]),
 race('demo:us-senate','U.S. Senate — sample state','national',[('Morgan Lee','REP',1502118),('Alex Ramirez','DEM',1339004),('Riley Cross','NPA',92441)],chamber='senate'),
 race('demo:us-house','U.S. House — sample district','national',[('Drew Whitaker','REP',198442),('Jamie Rivers','DEM',176593)],chamber='house'),
 race('demo:fl-ag','Florida attorney general — sample','florida',[('Sam Rivera','DEM',3942000),('Avery Lane','REP',4108000)]),
 race('demo:irc-school','School board — sample district','indian_river',[('Quinn Harper','NON',15910),('Robin Wells','NON',14923)]),
 race('demo:irc-city','City council — sample seat','indian_river',[('Cameron Reed','NON',4200),('Dakota Hayes','NON',4085)]),
 race('demo:irc-measure','Local referendum — sample measure','indian_river',[('Yes','NON',21400),('No','NON',19350)]),
]
markets=[]
for provider,prob in [('Polymarket',64.5),('Kalshi',63.5)]:
 for chamber in ['house','senate']:
  markets.append({'id':'demo:'+provider+chamber,'provider':provider+' · DEMO','contract_id':'fictional','question':'Fictional Democratic '+chamber+' control contract','outcome':'Yes — Democratic control',
      'probability':prob if chamber=='senate' else prob+8,'bid':.63,'ask':.66,'spread_pp':3,'price_convention':'fictional midpoint','metadata_updated_at':None,'quote_updated_at':None,
      'volume':None,'liquidity':None,'source_url':'','rules':'Demonstration contract; not an actual market.','status':'sample','comparison_group':'control-'+chamber,'flags':['Fictional sample, not actual odds'],'demo':True})
payload={'demo':True,'election_date':'2026-11-03','description':'Entirely fictional candidates, polls, prices and counts. No historical results are reused.',
 'races':races,'markets':markets,'polls':[{'id':'demo:poll','race_id':'demo:fl-governor','pollster':'Fictional Research Co.','sponsor':'Demo fixture',
 'field_start':'2026-10-15','field_end':'2026-10-18','sample_size':1000,'population':'Fictional likely voters','method':'Sample fixture',
 'shares':[{'candidate_id':'demo:fl-governor:0','share':49},{'candidate_id':'demo:fl-governor:1','share':48},{'candidate_id':'demo:fl-governor:2','share':3}],
 'source_url':'','retrieved_at':None,'demo':True}],
 'chambers':[{'chamber':'house','total':435,'threshold':218,'seats':{'DEM':205,'REP':201,'OTHER':0},'unresolved_or_unprovided':29,'note':'Fictional seat totals for layout demonstration.'},
 {'chamber':'senate','total':100,'threshold':51,'seats':{'DEM':47,'REP':47,'OTHER':0},'unresolved_or_unprovided':6,'note':'Fictional totals. A 50–50 Senate also depends on the vice president.'}],
 'ticker_events':[{'id':'demo:ticker1','text':'DEMO: Fictional Florida governor contest remains close. These are not real votes.','source':'Fictional demo fixture','demo':True,'scope':'florida','at':None},
 {'id':'demo:ticker2','text':'DEMO: Sample Indian River school board totals illustrate the local-race view.','source':'Fictional demo fixture','demo':True,'scope':'indian_river','at':None},
 {'id':'demo:ticker3','text':'DEMO: Poll vote share and market win probability measure different things.','source':'Display guide','demo':True,'scope':'national','at':None}]}
if __name__=='__main__':
 dest=Path(__file__).parent/'data'/'demo_data.json';dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(payload,indent=2),encoding='utf-8')
