"""Reviewed unofficial Guam report; a changed document requires explicit review."""
import hashlib,json,urllib.request
import config
from validation import validate_results
REPORT_URL='https://npr.brightspotcdn.com/ee/81/3dba243f4963980c09345e3d632d/2026-guam-general-election-unofficial-results.pdf'
def reviewed_payload(data):
 if data.get('source_url')!=REPORT_URL:raise ValueError('Unexpected Guam report source')
 if len(data.get('races',[]))!=3:raise ValueError('Unexpected reviewed Guam race set')
 for race in data['races']:
  if race.get('chamber') is not None or race.get('territory') is not True or race.get('status')!='unofficial' or race.get('source_url')!=REPORT_URL:raise ValueError('Guam snapshot cannot establish chamber seats or calls')
  if sum(c['votes'] for c in race['candidates'])!=race.get('report_total'):raise ValueError('Guam candidate totals do not match report')
 return validate_results(data)
def guam_feed():
 data=reviewed_payload(json.loads((config.ROOT/'data'/'guam_reviewed.json').read_text(encoding='utf-8')))
 req=urllib.request.Request(REPORT_URL,headers={'User-Agent':'ElectionWatch/2.0 (read-only report verification)','Cache-Control':'no-cache'})
 with urllib.request.urlopen(req,timeout=config.HTTP_TIMEOUT) as response:raw=response.read(config.MAX_RESPONSE_BYTES+1)
 if len(raw)>config.MAX_RESPONSE_BYTES:raise ValueError('Guam report exceeds size limit')
 if hashlib.sha256(raw).hexdigest()!=data['verification_sha256']:raise ValueError('Guam report changed; retaining last reviewed unofficial snapshot until reviewed')
 return data
