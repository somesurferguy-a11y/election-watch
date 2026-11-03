"""Freeze observed forecasts at fixed cutoffs; score only verified exact-contract outcomes."""
import copy,hashlib,math,re
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit

CHECKPOINTS=(('midnight','Midnight ET','2026-11-03T05:00:00Z'),('noon','Noon ET','2026-11-03T17:00:00Z'),('evening','6 PM ET','2026-11-03T23:00:00Z'))
PROVIDERS=('Kalshi','Polymarket','Robinhood')
MAX_AGE_SECONDS=600

def _time(value):
 if not isinstance(value,str):raise ValueError('A timezone-aware timestamp is required')
 try:result=datetime.fromisoformat(value.replace('Z','+00:00'))
 except ValueError:raise ValueError('Invalid forecast timestamp') from None
 if result.tzinfo is None:raise ValueError('Forecast timestamp requires a timezone')
 return result.astimezone(timezone.utc)

def _stamp(value):return value.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def rules_hash(rules):
 """An exact-text fingerprint; changed contract rules cannot inherit old outcomes."""
 if not isinstance(rules,str) or not rules.strip():raise ValueError('Contract rules are required')
 return hashlib.sha256(rules.encode('utf-8')).hexdigest()

def _finite(value,low,high):
 if isinstance(value,bool):raise ValueError('Boolean is not a forecast number')
 number=float(value)
 if not math.isfinite(number) or not low<=number<=high:raise ValueError('Forecast number outside valid range')
 return number

def _ledger(ledger):
 result=copy.deepcopy(ledger or {})
 if not isinstance(result,dict):raise ValueError('Invalid forecast ledger')
 if result.get('version',1)!=1:raise ValueError('Unsupported forecast ledger version')
 result['version']=1;result.setdefault('latest',{});result.setdefault('checkpoints',{})
 if not isinstance(result['latest'],dict) or not isinstance(result['checkpoints'],dict):raise ValueError('Invalid forecast ledger')
 for checkpoint in result['checkpoints'].values():
  if not isinstance(checkpoint,dict) or not isinstance(checkpoint.get('forecasts'),list) or not all(isinstance(row,dict) for row in checkpoint['forecasts']):raise ValueError('Invalid frozen forecast archive')
 return result

def _snapshot(market,observed):
 try:
  if market.get('provider') not in PROVIDERS or market.get('status')!='open' or market.get('price_convention')!='bid/ask midpoint':return None
  if not re.match(r'^Yes\s*[—–-]\s*Democratic(?:\s|$)',market.get('outcome','')):return None
  group=market.get('comparison_group');cid=market.get('contract_id')
  if not isinstance(group,str) or not group or not isinstance(cid,str) or not cid:return None
  bid=_finite(market['bid'],0,1);ask=_finite(market['ask'],0,1);probability=_finite(market['probability'],0,100)
  if bid>ask or abs(probability-(bid+ask)*50)>0.011:return None
  quote_time=market.get('quote_updated_at')
  if quote_time is not None and _time(quote_time)>observed:return None
  return {'provider':market['provider'],'comparison_group':group,'contract_id':cid,'rules_hash':rules_hash(market.get('rules')),'probability':probability,'bid':bid,'ask':ask,'observed_at':_stamp(observed),'quote_updated_at':quote_time,'rules':market.get('rules'),'source_url':market.get('source_url'),'question':market.get('question'),'outcome':market.get('outcome')}
 except (ValueError,TypeError,KeyError):return None

def freeze_due(ledger,now):
 """Finalize due checkpoints from prior observations. Never fill an already missed cutoff."""
 result=_ledger(ledger);current=_time(now)
 for key,label,reference_at in CHECKPOINTS:
  reference=_time(reference_at)
  if current<reference or key in result['checkpoints']:continue
  forecasts=[]
  for latest in result['latest'].values():
   try:
    age=(reference-_time(latest['observed_at'])).total_seconds()
    if 0<=age<=MAX_AGE_SECONDS:forecasts.append(copy.deepcopy(latest))
   except (ValueError,TypeError,KeyError):continue
  forecasts.sort(key=lambda row:(row['provider'],row['comparison_group'],row['contract_id']))
  result['checkpoints'][key]={'key':key,'label':label,'reference_at':reference_at,'status':'frozen' if forecasts else 'missed','frozen_at':_stamp(current),'forecasts':forecasts}
 return result

def update(ledger,markets,observed_at):
 """Return a new ledger. Exactly-on-cutoff observations qualify; later ones never backfill."""
 observed=_time(observed_at)
 # Freeze older checkpoints before replacing their only stored prior observation.
 result=freeze_due(ledger,_stamp(observed-timedelta(microseconds=1)))
 candidates={};ambiguous=set()
 for market in markets:
  if not isinstance(market,dict):continue
  snapshot=_snapshot(market,observed)
  if snapshot is None:continue
  key=snapshot['provider']+'|'+snapshot['comparison_group']
  if key in candidates and candidates[key]!=snapshot:ambiguous.add(key)
  candidates[key]=snapshot
 for key,snapshot in candidates.items():
  if key in ambiguous:continue
  previous=result['latest'].get(key)
  if previous:
   try:
    if _time(previous['observed_at'])>observed:continue
   except (ValueError,TypeError,KeyError):pass
  result['latest'][key]=snapshot
 return freeze_due(result,_stamp(observed))

def _verified_outcomes(outcomes,now):
 index={};conflicts=set()
 for row in outcomes if isinstance(outcomes,list) else []:
  try:
   if not isinstance(row,dict) or row.get('verified') is not True or isinstance(row.get('outcome'),bool) or row.get('outcome') not in [0,1]:continue
   resolved=_time(row['resolved_at']);source=urlsplit(row['source_url'])
   if resolved>now or source.scheme!='https' or not source.hostname or source.username or source.password:continue
   key=tuple(row[field] for field in ['provider','comparison_group','contract_id','rules_hash'])
   if not all(isinstance(value,str) and value for value in key) or not re.fullmatch('[a-f0-9]{64}',key[3]):continue
   if key in index and index[key]['outcome']!=row['outcome']:conflicts.add(key)
   index[key]=row
  except (ValueError,TypeError,KeyError):continue
 return {key:value for key,value in index.items() if key not in conflicts}

def _calibration(pairs):
 """Lower-inclusive percentage bins; only the final bin includes its upper bound."""
 bins=[]
 for index in range(5):
  matched=[pair for pair in pairs if min(int(pair[0]/20),4)==index]
  bins.append({'label':str(index*20)+'–'+str((index+1)*20)+'%','count':len(matched),'mean_probability':round(sum(pair[0] for pair in matched)/len(matched),6) if matched else None,'outcome_rate':round(100*sum(pair[1] for pair in matched)/len(matched),6) if matched else None})
 return bins

def _rows(forecasts,outcomes,reference,now):
 rows=[]
 for provider in PROVIDERS:
  captured=[row for row in forecasts if row.get('provider')==provider];scores=[];sources=[];pairs=[]
  for forecast in captured:
   try:
    key=tuple(forecast[field] for field in ['provider','comparison_group','contract_id','rules_hash']);outcome=outcomes.get(key)
    if outcome is None or _time(outcome['resolved_at'])<reference:continue
    probability=_finite(forecast['probability'],0,100)/100
    scores.append((probability-outcome['outcome'])**2)
    pairs.append((probability*100,outcome['outcome']))
    sources.append({field:outcome[field] for field in ['provider','comparison_group','source_url','resolved_at']})
   except (ValueError,TypeError,KeyError):continue
  rows.append({'provider':provider,'captured':len(captured),'scored':len(scores),'pending':len(captured)-len(scores),'brier_score':round(sum(scores)/len(scores),6) if scores else None,'calibration_bins':_calibration(pairs),'small_sample_warning':len(scores)<30,'_scores':scores,'_outcome_sources':sources})
 return rows

def summary(ledger,outcomes,now):
 """Outcomes is a list of manually verified rows, never winner calls or market prices."""
 current=_time(now);frozen=freeze_due(ledger,now);verified=_verified_outcomes(outcomes,current);checkpoints=[];totals={provider:[] for provider in PROVIDERS};captured={provider:0 for provider in PROVIDERS}
 for key,label,reference_at in CHECKPOINTS:
  checkpoint=copy.deepcopy(frozen['checkpoints'].get(key,{'key':key,'label':label,'reference_at':reference_at,'status':'upcoming','frozen_at':None,'forecasts':[]}))
  providers=_rows(checkpoint['forecasts'],verified,_time(reference_at),current)
  sources=[]
  for row in providers:
   totals[row['provider']].extend(row.pop('_scores'));captured[row['provider']]+=row['captured'];sources.extend(row.pop('_outcome_sources'))
  checkpoint.update(captured=sum(row['captured'] for row in providers),total_scored=sum(row['scored'] for row in providers),providers=providers,outcome_sources=sources)
  checkpoints.append(checkpoint)
 providers=[]
 for provider in PROVIDERS:
  scores=totals[provider];count=captured[provider]
  providers.append({'provider':provider,'captured':count,'scored':len(scores),'pending':count-len(scores),'brier_score':round(sum(scores)/len(scores),6) if scores else None,'small_sample_warning':len(scores)<30})
 return {'checkpoints':checkpoints,'providers':providers,'latest_observations':len(frozen['latest']),'method':'Mean Brier score: (forecast probability / 100 - verified outcome) squared; lower is better. One Democratic outcome per provider and comparison group at each checkpoint.','warning':'Small sample; repeated checkpoints on the same contracts are correlated. This is a prospective ledger, not a historical accuracy claim.'}
