"""Election-night context and conservative close-race selection."""
import json
from functools import lru_cache
import config

@lru_cache(maxsize=1)
def night_guide():
    return json.loads((config.ROOT/'data'/'night_guide.json').read_text(encoding='utf-8'))

def competitive_races(races):
    out=[]
    for race in races:
        if race.get('status') not in ('unofficial','recount') or race.get('office_code')=='AMD' or race.get('seats_to_elect',1)!=1 or race.get('result_incomplete'):continue
        cs=sorted(race['candidates'],key=lambda c:c['votes'],reverse=True)
        if len(cs)<2 or any(c.get('votes_available') is False for c in cs):continue
        total=sum(c['votes'] for c in cs)
        if total<100:continue
        margin=100*(cs[0]['votes']-cs[1]['votes'])/total
        if margin<=5:out.append({'race_id':race['id'],'margin_pp':round(margin,3),'margin_votes':cs[0]['votes']-cs[1]['votes'],'total_votes':total})
    return sorted(out,key=lambda r:(r['margin_pp'],r['race_id']))
