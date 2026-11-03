import copy,math,unittest
from forecast_audit import update,freeze_due,summary,rules_hash

BEFORE='2026-11-03T04:59:00Z';REFERENCE='2026-11-03T05:00:00Z';AFTER='2026-11-03T05:00:01Z';NOW='2026-11-04T18:00:00Z'
def market(provider='Robinhood',group='control-house',probability=80):
 value=probability/100
 return {'provider':provider,'comparison_group':group,'contract_id':provider+'-'+group,'rules':'Verified exact 2026 contract rules','outcome':'Yes — Democratic control','status':'open','bid':value-.01,'ask':value+.01,'probability':probability,'price_convention':'bid/ask midpoint'}
def outcome(forecast,value=1):
 return {**{key:forecast[key] for key in ['provider','comparison_group','contract_id','rules_hash']},'verified':True,'outcome':value,'resolved_at':'2026-11-04T12:00:00Z','source_url':'https://official.example/results'}
def provider_row(result,name='Robinhood'):return next(row for row in result['providers'] if row['provider']==name)

class ForecastAuditTests(unittest.TestCase):
 def test_update_freezes_previous_observation_before_late_quote(self):
  ledger=update({},[market()],BEFORE);ledger=update(ledger,[market(probability=20)],AFTER)
  self.assertEqual(ledger['checkpoints']['midnight']['forecasts'][0]['probability'],80)
  self.assertEqual(ledger['latest']['Robinhood|control-house']['probability'],20)
 def test_exact_checkpoint_boundary_is_eligible(self):
  ledger=update({},[market()],REFERENCE)
  self.assertEqual(ledger['checkpoints']['midnight']['status'],'frozen')
  self.assertEqual(ledger['checkpoints']['midnight']['forecasts'][0]['observed_at'],REFERENCE)
 def test_missed_checkpoint_never_backfills_from_future_or_retroactive_update(self):
  ledger=update({},[market()],AFTER)
  self.assertEqual(ledger['checkpoints']['midnight']['status'],'missed')
  ledger=update(ledger,[market()],BEFORE)
  self.assertEqual(ledger['checkpoints']['midnight']['status'],'missed')
  self.assertEqual(ledger['checkpoints']['midnight']['forecasts'],[])
 def test_stale_and_future_observations_are_not_frozen(self):
  stale=freeze_due(update({},[market()],'2026-11-03T04:49:59Z'),REFERENCE)
  self.assertEqual(stale['checkpoints']['midnight']['status'],'missed')
  exact=freeze_due(update({},[market()],'2026-11-03T04:50:00Z'),REFERENCE)
  self.assertEqual(exact['checkpoints']['midnight']['status'],'frozen')
  ledger={'latest':{'x':{'observed_at':'2026-11-03T05:00:01Z'}}}
  self.assertEqual(freeze_due(ledger,REFERENCE)['checkpoints']['midnight']['status'],'missed')
 def test_one_democratic_outcome_per_provider_group(self):
  dem=market();rep={**dem,'outcome':'Yes — Republican control','contract_id':'rep'}
  ledger=update({},[dem,rep,copy.deepcopy(dem)],BEFORE)
  self.assertEqual(len(ledger['latest']),1)
  conflicting={**dem,'contract_id':'another-dem-contract'}
  self.assertEqual(update({},[dem,conflicting],BEFORE)['latest'],{})
 def test_invalid_closed_or_non_midpoint_quotes_are_excluded(self):
  for patch in [{'probability':math.nan},{'probability':101},{'probability':False},{'bid':math.inf},{'bid':.9,'ask':.1},{'bid':None},{'probability':70},{'status':'closed'},{'price_convention':'last trade'},{'rules':''},{'quote_updated_at':'2026-11-03T05:00:01Z'},{'quote_updated_at':'not-a-date'}]:
   with self.subTest(patch=patch):self.assertEqual(update({},[{**market(),**patch}],BEFORE)['latest'],{})
 def test_frozen_snapshot_and_input_are_independent_copies(self):
  original=market();ledger=update({},[original],BEFORE);saved=copy.deepcopy(ledger)
  frozen=freeze_due(ledger,REFERENCE)
  self.assertEqual(ledger,saved)
  original['probability']=5;frozen['latest']['Robinhood|control-house']['probability']=6
  self.assertEqual(frozen['checkpoints']['midnight']['forecasts'][0]['probability'],80)
  finalized=copy.deepcopy(frozen['checkpoints'])
  self.assertEqual(freeze_due(frozen,NOW)['checkpoints']['midnight'],finalized['midnight'])
 def test_older_updates_do_not_replace_latest_observation(self):
  ledger=update({},[market(probability=20)],BEFORE)
  ledger=update(ledger,[market(probability=80)],'2026-11-03T04:58:00Z')
  self.assertEqual(ledger['latest']['Robinhood|control-house']['probability'],20)
 def test_three_fixed_checkpoints_and_all_provider_rows_are_present(self):
  result=summary({},[],'2026-11-03T04:00:00Z')
  self.assertEqual([row['reference_at'] for row in result['checkpoints']],[REFERENCE,'2026-11-03T17:00:00Z','2026-11-03T23:00:00Z'])
  self.assertTrue(all(row['status']=='upcoming' for row in result['checkpoints']))
  self.assertEqual({row['provider'] for row in result['providers']},{'Kalshi','Polymarket','Robinhood'})
  self.assertTrue(all(row['brier_score'] is None and row['captured']==0 for row in result['providers']))
 def test_latest_observation_count_is_available_before_checkpoints(self):
  markets=[market(provider,group) for provider in ['Kalshi','Polymarket','Robinhood'] for group in ['control-house','control-senate','fl-governor']]
  ledger=update({},markets,'2026-11-02T23:00:00Z')
  result=summary(ledger,[],'2026-11-02T23:00:01Z')
  self.assertEqual(result['latest_observations'],9);self.assertTrue(all(row['captured']==0 for row in result['providers']))
 def test_known_brier_scores_and_pending_counts(self):
  ledger=freeze_due(update({},[market(),market(group='control-senate',probability=20)],BEFORE),REFERENCE)
  forecasts=ledger['checkpoints']['midnight']['forecasts']
  result=summary(ledger,[outcome(forecast) for forecast in forecasts],NOW)
  row=provider_row(result);self.assertEqual(row['brier_score'],.34);self.assertEqual(row['scored'],2);self.assertEqual(row['pending'],0)
  row=provider_row(summary(ledger,[outcome(forecasts[0])],NOW))
  self.assertEqual(row['scored'],1);self.assertEqual(row['pending'],1);self.assertTrue(row['small_sample_warning'])
 def test_calibration_bins_use_scored_pairs_with_zero_one_and_hundred_boundaries(self):
  values=[0,1,20,40,60,80,100];markets=[]
  for value in values:
   row=market(group='test-'+str(value),probability=value);row.update(bid=value/100,ask=value/100);markets.append(row)
  markets.append(market(group='unresolved',probability=10))
  ledger=freeze_due(update({},markets,BEFORE),REFERENCE)
  verified=[]
  for forecast in ledger['checkpoints']['midnight']['forecasts']:
   if forecast['comparison_group']!='unresolved':verified.append(outcome(forecast,1 if forecast['probability'] in [1,40,80,100] else 0))
  result=summary(ledger,verified,NOW);row=next(row for row in result['checkpoints'][0]['providers'] if row['provider']=='Robinhood');bins=row['calibration_bins']
  self.assertEqual([bucket['count'] for bucket in bins],[2,1,1,1,2])
  self.assertEqual(bins[0]['mean_probability'],.5);self.assertEqual(bins[0]['outcome_rate'],50)
  self.assertEqual(bins[1]['mean_probability'],20);self.assertEqual(bins[1]['outcome_rate'],0)
  self.assertEqual(bins[4]['mean_probability'],90);self.assertEqual(bins[4]['outcome_rate'],100)
  self.assertEqual(row['scored'],7);self.assertEqual(row['pending'],1);self.assertTrue(row['small_sample_warning'])
  self.assertNotIn('calibration_bins',provider_row(result))
 def test_empty_calibration_bins_have_null_means(self):
  ledger=freeze_due(update({},[market()],BEFORE),REFERENCE)
  for row in summary(ledger,[],NOW)['checkpoints'][0]['providers']:
   self.assertEqual(len(row['calibration_bins']),5)
   self.assertTrue(all(bucket['count']==0 and bucket['mean_probability'] is None and bucket['outcome_rate'] is None for bucket in row['calibration_bins']))
 def test_outcomes_require_exact_identity_and_rules_fingerprint(self):
  ledger=freeze_due(update({},[market()],BEFORE),REFERENCE);forecast=ledger['checkpoints']['midnight']['forecasts'][0];valid=outcome(forecast)
  for patch in [{'provider':'Kalshi'},{'comparison_group':'another'},{'contract_id':'different'},{'rules_hash':rules_hash('changed rules')},{'verified':False},{'source_url':'http://official.example/results'},{'source_url':'https://user:secret@official.example/results'},{'resolved_at':'2026-11-05T12:00:00Z'},{'resolved_at':'2026-11-03T04:00:00Z'},{'outcome':True},{'outcome':.5}]:
   with self.subTest(patch=patch):self.assertEqual(provider_row(summary(ledger,[{**valid,**patch}],NOW))['scored'],0)
  self.assertEqual(provider_row(summary(ledger,[valid],NOW))['brier_score'],.04)
 def test_conflicting_verified_outcomes_are_not_scored(self):
  ledger=freeze_due(update({},[market()],BEFORE),REFERENCE);forecast=ledger['checkpoints']['midnight']['forecasts'][0]
  self.assertEqual(provider_row(summary(ledger,[outcome(forecast,1),outcome(forecast,0)],NOW))['scored'],0)
 def test_only_actually_scored_outcome_sources_are_listed(self):
  ledger=freeze_due(update({},[market()],BEFORE),REFERENCE);forecast=ledger['checkpoints']['midnight']['forecasts'][0]
  matched=outcome(forecast);unmatched={**matched,'contract_id':'unrelated','source_url':'https://official.example/unrelated'}
  sources=summary(ledger,[matched,unmatched],NOW)['checkpoints'][0]['outcome_sources']
  self.assertEqual(sources,[{field:matched[field] for field in ['provider','comparison_group','source_url','resolved_at']}])
  self.assertEqual(summary(ledger,[unmatched],NOW)['checkpoints'][0]['outcome_sources'],[])
 def test_summary_never_mutates_or_infers_outcomes(self):
  ledger=update({},[market()],BEFORE);before=copy.deepcopy(ledger)
  result=summary(ledger,[],NOW)
  self.assertEqual(ledger,before);self.assertEqual(provider_row(result)['scored'],0);self.assertEqual(provider_row(result)['pending'],1)
  self.assertEqual(result['checkpoints'][0]['total_scored'],0)
 def test_rules_hash_changes_with_exact_rule_text(self):
  self.assertEqual(len(rules_hash('rules')),64);self.assertNotEqual(rules_hash('rules'),rules_hash('rules '))
  with self.assertRaises(ValueError):rules_hash('')
 def test_naive_clock_and_unknown_ledger_version_are_rejected(self):
  with self.assertRaises(ValueError):update({},[],'2026-11-03T05:00:00')
  with self.assertRaises(ValueError):freeze_due({'version':2},REFERENCE)
