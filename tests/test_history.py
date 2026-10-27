import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import config
from history import finish,parse_state_history,parse_county_history,load_history
from roster import load_roster


class HistoryTests(unittest.TestCase):
    def test_primary_parties_are_separate_electorates(self):
        header='ElectionDate\tPartyCode\tRaceCode\tRaceName\tCountyCode\tJuris1num\tJuris2num\tCanNameFirst\tCanNameMiddle\tCanNameLast\tCanVotes\n'
        rows=['08/18/2026\tREP\tUSS\tSenate\tIND\t \t \tAlice\t\tAble\t80',
              '08/18/2026\tREP\tUSS\tSenate\tIND\t \t \tBob\t\tBaker\t20',
              '08/18/2026\tDEM\tUSS\tSenate\tIND\t \t \tCarol\t\tCole\t40']
        result=parse_state_history(header+'\n'.join(rows),'2026-08-18','primary','https://example.org/official')
        republican=next(r for r in result if r['party']=='REP' and r['scope']=='florida')
        self.assertEqual(republican['total_votes'],100)
        self.assertEqual(republican['candidates'][0]['percentage'],80)
        self.assertEqual(len(result),4)
        with self.assertRaises(ValueError):parse_state_history(header+'\n'.join(rows+[rows[0]]),'2026-08-18','primary','https://example.org/official')

    def test_zero_archives_rejected(self):
        with self.assertRaises(ValueError):finish({'candidates':[{'votes':0}]})

    def test_tied_rank_does_not_invent_a_winner(self):
        result=finish({'candidates':[{'votes':5},{'votes':5}]})
        self.assertEqual([c['rank'] for c in result['candidates']],[1,1])
        self.assertNotIn('winner_id',result)

    def test_negative_counts_rejected(self):
        with self.assertRaises(ValueError):finish({'candidates':[{'votes':-1},{'votes':4}]})

    def test_missing_bundle_is_explicit(self):
        load_history.cache_clear()
        with tempfile.TemporaryDirectory() as directory,patch.object(config,'ROOT',Path(directory)):
            self.assertEqual(load_history()['candidates'],[])
        load_history.cache_clear()

    def test_installed_results_match_roster_and_arithmetic(self):
        data=load_history();roster=load_roster()
        candidates={(r['id'],c['id']) for r in roster['races']+roster['settled_races'] for c in r['candidates']}
        self.assertGreater(len(data['candidates']),100)
        for record in data['candidates']:
            self.assertIn((record['race_id'],record['candidate_id']),candidates)
            self.assertLess(record['date'],config.ELECTION_DATE)
            self.assertAlmostEqual(record['percentage'],100*record['votes']/record['total_votes'])
            self.assertEqual(record['total_votes'],record['votes']+sum(c['votes'] for c in record['opponents']))
            self.assertNotIn(record['historical_name'].casefold(),['yes','no','write-in'])

    def test_verified_local_results(self):
        records=load_history()['candidates']
        pippin=next(r for r in records if r['candidate_name']=='Jennifer Pippin' and r['date']=='2026-08-18')
        self.assertEqual(pippin['votes'],8713)
        self.assertAlmostEqual(pippin['percentage'],8713/20960*100)
        herrera=next(r for r in records if r['candidate_name']=='Fernando R. Herrera' and r['date']=='2024-11-05')
        self.assertEqual((herrera['votes'],herrera['rank']),(280,2))

    def test_county_and_statewide_never_summed(self):
        records=[r for r in load_history()['candidates'] if r['candidate_name']=='Ashley Moody' and r['date']=='2026-08-18']
        self.assertEqual(sorted(r['votes'] for r in records),[17376,1320734])
        self.assertEqual({r['scope'] for r in records},{'florida','indian_river'})

    def test_senate_cycle_wins_and_total_held_are_distinct(self):
        data=load_history()['senate']
        self.assertEqual([r['democratic_aligned_won']+r['republican_won'] for r in data],[34,35,35])
        self.assertTrue(all(r['democratic_aligned_held']+r['republican_held']==100 for r in data))
        self.assertEqual(data[0]['democratic_aligned_won'],19)
        self.assertEqual(data[0]['republican_held'],53)

    def test_invalid_history_cannot_impersonate_current_results(self):
        payload=copy.deepcopy(load_history());payload['candidates'][0]['date']=config.ELECTION_DATE
        load_history.cache_clear()
        with tempfile.TemporaryDirectory() as directory,patch.object(config,'ROOT',Path(directory)):
            path=Path(directory)/'data';path.mkdir();(path/'history.json').write_text(json.dumps(payload),encoding='utf-8')
            with self.assertRaises(ValueError):load_history()
        load_history.cache_clear()

    def test_live_roster_remains_zero_before_returns(self):
        self.assertTrue(all(c['votes']==0 for r in load_roster()['races'] for c in r['candidates']))


if __name__=='__main__':unittest.main()
