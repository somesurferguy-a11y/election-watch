"""Read only the verified public Robinhood election contracts; no accounts or trading."""
import json,math
from datetime import datetime
from html.parser import HTMLParser

CONGRESS_URL='https://robinhood.com/us/en/prediction-markets/midterms/control-of-congress/'
FLORIDA_URL='https://robinhood.com/us/en/prediction-markets/midterms/florida/'
# IDs, names and tickers were observed together in Robinhood's public page on Nov 2, 2026.
EVENTS={
 'b866f4c5-d317-4a52-b388-d57cee1c073e':('2026 U.S. House party winner','CNTRLHOU-26','control-house','congress',{'REP':'3eaa7391-fa0e-4e5b-9593-e5aeaf04a5f7','DEM':'3689dd5d-5503-43f9-b051-9d0340ad3fa9'}),
 '7808f639-eb01-4ad8-81f7-f596f89f52e6':('2026 U.S. Senate party winner','CNTRLSEN-26','control-senate','congress',{'REP':'cc9bce08-a88f-4761-8924-494d738ab368','DEM':'01f1d2d0-21b8-4309-9b84-c74e86afbddc'}),
 '16bea76d-75f2-4ec6-b79a-94649fae00e4':('Florida Governor winner','GOVRACE-26FL','fl-governor','florida',{'DEM':'e1bdb617-0261-4e92-bb83-f51f951f0ce6','REP':'c7f21f58-d76d-4a8e-94cd-30084e50da54'}),
 '2931a5e9-0f8e-4673-906a-4e2b200a54e5':('Florida Senate special election winner','SENRACE-26FL','fl-senate','florida',{'DEM':'1a1f47b1-eee6-4be6-9006-95faec01a4bc','REP':'d95ba277-896b-4996-afc0-d6722ed21ba6'}),
 '027a7efd-a57f-4fc2-a4be-aa71784e8360':('FL-09 House race winner','HOURACE-26FL09','fl-house-09','florida',{'DEM':'b14bb41d-4b5c-4171-8f3c-2ec5556539d2','REP':'3eeb460a-1fc7-4f1d-a2ab-6c7046fada46'}),
}

class NextData(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=False);self.capture=False;self.parts=[];self.count=0
 def handle_starttag(self,tag,attrs):
  if tag=='script' and dict(attrs).get('id')=='__NEXT_DATA__':self.capture=True;self.count+=1
 def handle_endtag(self,tag):
  if tag=='script':self.capture=False
 def handle_data(self,data):
  if self.capture:self.parts.append(data)

def timestamp(value):
 if not isinstance(value,str):raise ValueError('Robinhood quote timestamp missing')
 try:parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
 except ValueError:raise ValueError('Robinhood quote timestamp invalid') from None
 if parsed.tzinfo is None or parsed.year<2025:raise ValueError('Robinhood quote timestamp invalid')
 return value

def price(value):
 if value is None:return None
 if isinstance(value,bool):raise ValueError('Robinhood price must be numeric')
 try:result=float(value)
 except (TypeError,ValueError):raise ValueError('Robinhood price must be numeric') from None
 if not math.isfinite(result) or not 0<=result<=1:raise ValueError('Robinhood price outside zero to one')
 return result

def parse_robinhood(html,market_record,scope=None):
 if scope not in [None,'congress','florida']:raise ValueError('Unknown Robinhood scope')
 parser=NextData();parser.feed(html)
 if parser.count!=1:raise ValueError('Robinhood public page data missing or duplicated')
 try:data=json.loads(''.join(parser.parts))['props']['pageProps']
 except (KeyError,TypeError,json.JSONDecodeError):raise ValueError('Robinhood public page schema changed') from None
 if not isinstance(data.get('events'),list) or not isinstance(data.get('quotes'),dict) or not isinstance(data.get('fundamentals'),dict):raise ValueError('Robinhood public page schema changed')
 required={key:value for key,value in EVENTS.items() if scope is None or value[3]==scope}
 seen=set();records=[]
 for event in data['events']:
  if not isinstance(event,dict):raise ValueError('Robinhood event schema changed')
  eid=event.get('id')
  if eid not in required:continue
  name,prefix,group,event_scope,contracts=required[eid]
  if eid in seen or event.get('name')!=name or event.get('category')!='Elections' or event.get('isSports') is not False:raise ValueError('Robinhood election identity mismatch')
  rows=event.get('eventContracts')
  if not isinstance(rows,dict) or len(rows)!=2:raise ValueError('Robinhood election contract set changed')
  parties=set()
  for contract in rows.values():
   if not isinstance(contract,dict):raise ValueError('Robinhood contract schema changed')
   symbol=contract.get('symbol','');party=symbol.rsplit('-',1)[-1]
   if party not in contracts or symbol!=prefix+'-'+party or contract.get('id')!=contracts[party] or party in parties or contract.get('eventId')!=eid or contract.get('isCombo') is not False:raise ValueError('Robinhood contract identity mismatch')
   if contract.get('exchange')!='EXCHANGE_SOURCE_ROTHERA' or contract.get('exchangeSource')!=3:raise ValueError('Robinhood underlying exchange changed')
   cid=contract['id'];quote=data['quotes'].get(cid)
   if not isinstance(quote,dict) or quote.get('instrument_id')!=cid or quote.get('symbol')!=symbol:raise ValueError('Robinhood quote identity missing or changed')
   bid,ask,last=(price(quote.get(key)) for key in ['yes_bid_price','yes_ask_price','last_trade_price'])
   if bid is not None and ask is not None and bid>ask:raise ValueError('Robinhood crossed quote rejected')
   updated=timestamp(quote.get('updated_at'))
   two_sided=bid is not None and ask is not None
   if not two_sided:
    if last is None:raise ValueError('Robinhood price unavailable')
    timestamp(quote.get('last_trade_venue_timestamp'))
   fundamental=data['fundamentals'].get(cid,{})
   if fundamental and fundamental.get('instrument_id')!=cid:raise ValueError('Robinhood volume identity mismatch')
   volume=fundamental.get('volume')
   if volume is not None:
    try:valid_volume=math.isfinite(float(volume)) and float(volume)>=0
    except (TypeError,ValueError):valid_volume=False
    if not valid_volume:raise ValueError('Robinhood volume invalid')
   status='open' if quote.get('state')=='active' and contract.get('tradability')=='EVENT_CONTRACT_TRADABILITY_TRADABLE' and event.get('state')=='ARSENAL_EVENT_STATE_ACTIVE' else 'closed'
   party_name='Democratic' if party=='DEM' else 'Republican'
   source_url=CONGRESS_URL if event_scope=='congress' else FLORIDA_URL
   record=market_record('Robinhood',cid,contract.get('description') or name,'Yes — '+party_name+' '+('control' if event_scope=='congress' else 'wins'),bid,ask,last,None,volume,None,source_url,event.get('longDescription',''),status,group)
   record['question']={'control-house':'2026 U.S. House control','control-senate':'2026 U.S. Senate control','fl-governor':'Florida governor · 2026','fl-senate':'Florida U.S. Senate special election · 2026','fl-house-09':'Florida U.S. House District 9 · 2026'}[group]
   record.update(quote_updated_at=updated,underlying_exchange='Rothera',underlying_ticker=symbol,event_id=eid,event_name=name,broker='Robinhood',last_trade_at=quote.get('last_trade_venue_timestamp'))
   record['flags']=[flag for flag in record['flags'] if flag!='Quote timestamp unavailable; check time is not trade time']
   record['flags'].append('Robinhood public quote · underlying Rothera exchange; markets are not independent confirmation of polls')
   records.append(record);parties.add(party)
  if parties!={'DEM','REP'}:raise ValueError('Robinhood party outcomes incomplete')
  seen.add(eid)
 if seen!=set(required):raise ValueError('Robinhood expected 2026 election markets missing')
 return records

def robinhood_feed(fetch_url,market_record):
 records=[]
 for url,scope in [(CONGRESS_URL,'congress'),(FLORIDA_URL,'florida')]:
  html,_=fetch_url(url)
  records.extend(parse_robinhood(html,market_record,scope))
 return {'markets':records,'source_updated_at':None,'coverage_note':'Public Robinhood quotes for 2026 U.S. House/Senate control, Florida Governor/Senate special election and FL-09. Underlying exchange: Rothera. Midpoint is our bid/ask convention; page retrieval time is not quote time.'}
