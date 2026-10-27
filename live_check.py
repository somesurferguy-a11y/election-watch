"""Explicit read-only connectivity check; writes real snapshots to local app data."""
import json
from store import Engine

if __name__=='__main__':
    engine=Engine()
    futures=[engine.pool.submit(engine.refresh_one,key) for key in engine.sources]
    for future in futures:future.result()
    state=engine.state()
    print(json.dumps({'sources':[{k:s.get(k) for k in ['id','status','last_success','source_updated_at','error']} for s in state['sources']],
        'races':len(state['races']),'county_races':len([r for r in state['races'] if r['scope']=='indian_river']),
        'markets':len(state['markets']),'total_votes':sum(c['votes'] for r in state['races'] for c in r['candidates']),
        'market_outcomes':[(m['provider'],m['outcome'],m['comparison_group'],m['probability']) for m in state['markets']]},indent=2))
    engine.close()
