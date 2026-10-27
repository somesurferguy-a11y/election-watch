"""Reviewed personal metadata stays separate from vote totals and call status."""
import copy,json
from functools import lru_cache
import config

@lru_cache(maxsize=1)
def profiles():
    path=config.ROOT/'data'/'candidate_profiles.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'records':{},'coverage_note':'Service and photos not verified.'}

def enrich_candidates(races):
    rows=copy.deepcopy(races);records=profiles()['records']
    for race in rows:
        for candidate in race['candidates']:
            record=records.get(race['id']+'|'+candidate['id'],{})
            candidate['service']=copy.deepcopy(record.get('service'))
            photo=record.get('photo')
            if photo and photo['path'].startswith('/static/portraits/') and '..' not in photo['path']:
                candidate['photo']=copy.deepcopy(photo)
    return rows
