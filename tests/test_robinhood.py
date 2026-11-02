import copy,json,unittest
from pathlib import Path
from feeds import market_record
from robinhood import parse_robinhood,robinhood_feed,CONGRESS_URL,FLORIDA_URL

class RobinhoodTests(unittest.TestCase):
 def setUp(self):self.data=json.loads((Path(__file__).parent/'fixtures/robinhood.json').read_text(encoding='utf-8'))
 def html(self):return '<html><script id="__NEXT_DATA__" type="application/json">'+json.dumps(self.data)+'</script></html>'
 def props(self):return self.data['props']['pageProps']
 def quote(self):return self.props()['quotes']['3eaa7391-fa0e-4e5b-9593-e5aeaf04a5f7']
 def parse(self,scope=None):return parse_robinhood(self.html(),market_record,scope)
 def test_exact_ten_election_contracts_have_unique_provider_ids(self):
  records=self.parse();self.assertEqual(len(records),10);self.assertEqual(len({r['id'] for r in records}),10)
  self.assertEqual({r['comparison_group'] for r in records},{'control-house','control-senate','fl-governor','fl-senate','fl-house-09'})
  self.assertTrue(all(r['provider']=='Robinhood' and r['underlying_exchange']=='Rothera' for r in records))
 def test_two_fixed_public_pages_are_fetched_and_scoped_without_duplicates(self):
  calls=[]
  def fetch(url):calls.append(url);return self.html(),'2026-11-02T23:59:00Z'
  payload=robinhood_feed(fetch,market_record)
  self.assertEqual(calls,[CONGRESS_URL,FLORIDA_URL]);self.assertEqual(len(payload['markets']),10);self.assertIsNone(payload['source_updated_at'])
 def test_midpoint_uses_yes_bid_ask_and_source_quote_time(self):
  quote=self.quote();quote.update(yes_bid_price='0.2',yes_ask_price='0.4',bid_price='0.9',ask_price='0.99',last_trade_price='0.8')
  record=self.parse('congress')[0]
  self.assertEqual(record['probability'],30);self.assertEqual(record['price_convention'],'bid/ask midpoint')
  self.assertEqual(record['quote_updated_at'],quote['updated_at']);self.assertIsNone(record['metadata_updated_at']);self.assertEqual(record['underlying_ticker'],'CNTRLHOU-26-REP')
  self.assertFalse(any(flag.startswith('Quote timestamp unavailable') for flag in record['flags']))
 def test_one_sided_quote_uses_only_attributed_last_trade(self):
  quote=self.quote();quote.update(yes_bid_price=None,yes_ask_price='0.4',last_trade_price='0.3')
  record=self.parse('congress')[0]
  self.assertEqual(record['probability'],30);self.assertEqual(record['price_convention'],'last trade');self.assertIn('No valid two-sided quote; showing last trade',record['flags'])
  quote['last_trade_venue_timestamp']='1754-08-30T22:43:41Z'
  with self.assertRaises(ValueError):self.parse('congress')
 def test_crossed_quote_is_rejected_instead_of_silently_using_last(self):
  self.quote().update(yes_bid_price='0.7',yes_ask_price='0.2',last_trade_price='0.5')
  with self.assertRaisesRegex(ValueError,'crossed'):self.parse()
 def test_invalid_prices_fail_closed(self):
  for value in ['NaN','Infinity',-0.01,1.01,True,'not-a-price']:
   with self.subTest(value=value):
    self.quote()['yes_bid_price']=value
    with self.assertRaises(ValueError):self.parse()
 def test_missing_quote_or_mismatched_instrument_is_rejected(self):
  cid=self.quote()['instrument_id'];saved=self.props()['quotes'].pop(cid)
  with self.assertRaises(ValueError):self.parse()
  self.props()['quotes'][cid]={**saved,'instrument_id':'wrong'}
  with self.assertRaises(ValueError):self.parse()
 def test_missing_or_invalid_quote_timestamp_is_not_replaced_by_retrieval_time(self):
  for value in [None,'','2026-11-02','1754-01-01T00:00:00Z','invalid']:
   self.quote()['updated_at']=value
   with self.assertRaises(ValueError):self.parse()
 def test_sports_combinations_and_other_years_do_not_enter_election_records(self):
  for key,value in [('isSports',True),('name','2024 U.S. House party winner')]:
   original=self.props()['events'][0][key];self.props()['events'][0][key]=value
   with self.assertRaises(ValueError):self.parse()
   self.props()['events'][0][key]=original
  contract=next(iter(self.props()['events'][0]['eventContracts'].values()));contract['isCombo']=True
  with self.assertRaises(ValueError):self.parse()
 def test_changed_contract_ticker_or_exchange_fails_closed(self):
  contract=next(iter(self.props()['events'][0]['eventContracts'].values()))
  contract['symbol']='CNTRLHOU-24-REP'
  with self.assertRaises(ValueError):self.parse()
  contract['symbol']='CNTRLHOU-26-REP';contract['exchange']='EXCHANGE_SOURCE_KALSHI'
  with self.assertRaises(ValueError):self.parse()
 def test_stale_page_shape_or_missing_expected_event_is_rejected(self):
  for html in ['<html>Sign in</html>','<script id="__NEXT_DATA__">{}</script>','<script id="__NEXT_DATA__">broken</script>']:
   with self.assertRaises(ValueError):parse_robinhood(html,market_record)
  self.props()['events'].pop()
  with self.assertRaises(ValueError):self.parse()
 def test_extra_unrelated_events_are_ignored(self):
  self.props()['events'].append({'id':'unrelated-sports-event','isSports':True,'name':'2026 Super Bowl'})
  self.assertEqual(len(self.parse()),10)
 def test_closed_contract_is_labeled_closed(self):
  self.quote()['state']='closed';record=self.parse('congress')[0]
  self.assertEqual(record['status'],'closed');self.assertIn('Trading closed or suspended',record['flags'])
 def test_invalid_volume_does_not_pass_to_display(self):
  cid=self.quote()['instrument_id'];self.props()['fundamentals'][cid]['volume']='NaN'
  with self.assertRaises(ValueError):self.parse()
 def test_fetch_failure_propagates_without_substituting_fixture(self):
  def fetch(url):raise OSError('offline')
  with self.assertRaises(OSError):robinhood_feed(fetch,market_record)
