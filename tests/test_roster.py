import copy,json,tempfile,unittest
from pathlib import Path
from roster import load_roster,compose_roster,merge_race
from store import Engine

class BallotRosterTests(unittest.TestCase):
    def setUp(self):self.roster=load_roster()
    def find(self,suffix):return next(r for r in self.roster['races'] if r['id'].endswith(suffix))
    def test_all_known_races_available_without_any_results_feed(self):
        races=compose_roster(self.roster,[])
        self.assertEqual(len([r for r in races if r['scope']=='florida']),177)
        self.assertEqual(len([r for r in races if r['scope']=='indian_river']),26)
        self.assertTrue(all(r['results_pending'] for r in races))
    def test_actual_commission_candidates_and_write_in(self):
        names=[c['name'] for c in self.find('commission-2')['candidates']]
        self.assertEqual(names,['Robert (Robbie) D. Hardingham','Jennifer Pippin','Nicole Paradiso (qualified write-in)'])
        self.assertFalse(any('McPartlan' in n or 'Robinson' in n for n in names))
    def test_withdrawn_sebastian_candidate_not_present(self):
        r=self.find('sebastian-council');self.assertEqual(len(r['candidates']),5);self.assertEqual(r['seats_to_elect'],2)
        self.assertNotIn('Todd Clifton',[c['name'] for c in r['candidates']])
    def test_vero_eight_candidates_three_seats(self):
        r=self.find('vero-council');self.assertEqual(len(r['candidates']),8);self.assertEqual(r['seats_to_elect'],3)
        self.assertIn('Tracey Lockwood Zudans',[c['name'] for c in r['candidates']])
    def test_fellsmere_names_match_questionnaire_not_transcript_typo(self):
        names=[c['name'] for c in self.find('fellsmere-council')['candidates']]
        self.assertIn('Fernando R. Herrera',names);self.assertIn('Jose M. Zamarripa',names)
        self.assertFalse(any('Zammaripa' in n for n in names))
    def test_full_governor_ticket_names_without_changing_poll_ids(self):
        races=[r for r in self.roster['races'] if r.get('office_code')=='GOV']
        self.assertEqual(len(races),2)
        self.assertIn('Byron Donalds / Bryan Avila',[c['name'] for c in races[0]['candidates']])
        self.assertIn('David Jolly / Gwen Graham',[c['name'] for c in races[0]['candidates']])
        seed=json.loads((Path(__file__).resolve().parents[1]/'data'/'polls_baseline.json').read_text())
        govpoll=next(p for p in seed['polls'] if p['id'].endswith('-gov'))
        r=next(r for r in races if r['id']==govpoll['race_id'])
        self.assertTrue(all(s['candidate_id'] in {c['id'] for c in r['candidates']} for s in govpoll['shares']))
    def test_settled_offices_not_mixed_into_november_ballot(self):
        settled=self.roster['settled_races'];self.assertEqual(len(settled),8)
        self.assertTrue(all(r['on_ballot'] is False for r in settled))
        rosario=next(r for r in settled if 'Jacqueline Rosario' in [c['name'] for c in r['candidates']])
        self.assertEqual(rosario['status'],'elected_earlier')
        self.assertFalse(any('School Board' in r['name'] for r in self.roster['races'] if r['scope']=='indian_river'))
    def test_three_sebastian_questions_present(self):
        questions=[r for r in self.roster['races'] if 'Sebastian Referendum' in r['name']]
        self.assertEqual(len(questions),3)
        self.assertTrue(all('Full question wording is not transcribed' in r['coverage_note'] for r in questions))
    def test_results_attach_using_reviewed_race_and_candidate_aliases(self):
        base=self.find('commission-4')
        result=copy.deepcopy(base);result.update(id='irc:enr:123',name='Board of County Commissioners, District 4',status='unofficial',source_name='County ENR')
        result['candidates'][1].update(id='other-id',name='Deryl Loar',votes=200)
        result['candidates'][0]['votes']=100
        merged=compose_roster({'races':[base]},[result])
        self.assertEqual(len(merged),1);self.assertEqual(merged[0]['id'],base['id'])
        self.assertEqual(merged[0]['candidates'][1]['name'],'Deryl Byron Loar')
        self.assertEqual(merged[0]['candidates'][1]['votes'],200)
    def test_partial_county_feed_does_not_remove_other_roster_contests(self):
        base=self.find('commission-2');result=copy.deepcopy(base);result['candidates'][0]['votes']=20
        races=compose_roster(self.roster,[result]);self.assertEqual(len(races),203)
        self.assertTrue(any(r['id'].endswith('vero-council') for r in races))
    def test_repeated_providers_do_not_add_votes(self):
        base=self.find('commission-4');a=copy.deepcopy(base);a['candidates'][0]['votes']=100
        b=copy.deepcopy(a);b.update(id='irc:enr:456',name='Board of County Commissioners, District 4',source_name='County ENR');b['candidates'][0]['votes']=200
        races=compose_roster({'races':[base]},[a,b]);self.assertEqual(len(races),1);self.assertEqual(races[0]['candidates'][0]['votes'],200)
    def test_missing_candidate_counts_are_unknown_not_zero_share(self):
        base=self.find('commission-4');result=copy.deepcopy(base);result['candidates']=result['candidates'][:1];result['candidates'][0]['votes']=10
        merged=merge_race(base,result)
        self.assertTrue(merged['result_incomplete']);self.assertIsNone(merged['candidates'][1]['percentage']);self.assertFalse(merged['candidates'][1]['votes_available'])
    def test_multi_seat_single_winner_call_not_treated_as_full_race_call(self):
        base=self.find('vero-council');result=copy.deepcopy(base);result.update(status='projected',winner_id=base['candidates'][0]['id'],call_source='Test desk')
        merged=merge_race(base,result);self.assertEqual(merged['status'],'unofficial')
    def test_canonical_identifiers_unique(self):
        records=self.roster['races']+self.roster['settled_races']
        self.assertEqual(len(records),len({r['id'] for r in records}))
    def test_fresh_install_without_network_still_has_complete_reviewed_roster(self):
        runtime=Path(__file__).resolve().parent/'runtime';runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as temp:
            engine=Engine(temp)
            try:
                engine.update_settings({'mode':'live'});state=engine.state()
                self.assertEqual(len(state['races']),203);self.assertEqual(len(state['settled_races']),8)
                self.assertTrue(all(c['votes']==0 for r in state['races'] for c in r['candidates']))
            finally:engine.close();engine.db.conn.close()

if __name__=='__main__':unittest.main()
