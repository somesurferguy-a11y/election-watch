import tempfile,time,unittest
from unittest.mock import patch
import config
from feeds import irc_home_result_urls,irc_feed,NotPublished
from store import Engine
HOME=config.IRC_HOME_URL
ARCHIVE=config.IRC_ARCHIVE_URL
URL='https://enr.electionsfl.org/IND/4444/Summary/'
class CountyDiscoveryTests(unittest.TestCase):
 def test_real_scrolling_banner_link_normalizes_to_summary(self):
  self.assertEqual(irc_home_result_urls('<a href="https://enr.electionsfl.org/IND/4096/Summary/Scrolling/Banner/">Election Results</a>'),['https://enr.electionsfl.org/IND/4096/Summary/'])
 def test_exact_published_links_only(self):
  html='''<iframe src="//enr.electionsfl.org/IND/4444/Summary/"></iframe><a href="https://enr.electionsfl.org/IND/4444/Summary/">Results</a><iframe data-src="https://enr.electionsfl.org/IND/5555/Summary/"></iframe>'''
  self.assertEqual(irc_home_result_urls(html),[URL,'https://enr.electionsfl.org/IND/5555/Summary/'])
 def test_turnout_poll_lookup_other_county_and_spoofed_hosts_ignored(self):
  urls=['https://tqv.vrswebapps.com/?state=FL&county=IND&election=103','https://vls.vrswebapps.com/#county=Indian-River','https://enr.electionsfl.org/AAA/4444/Summary/','https://enr.electionsfl.org.evil.test/IND/4444/Summary/','https://user@enr.electionsfl.org/IND/4444/Summary/','http://enr.electionsfl.org/IND/4444/Summary/','https://enr.electionsfl.org:9000/IND/4444/Summary/']
  for url in urls:self.assertEqual(irc_home_result_urls('<iframe src="'+url+'"></iframe>'),[])
 def test_home_embed_wins_before_archive_is_published(self):
  def fetch(url):
   return ('<iframe src="'+URL+'"></iframe>',None) if url==HOME else ('results','stamp') if url==URL else self.fail('Unexpected archive request')
  with patch('feeds.config.IRC_GENERAL_ID',''),patch('feeds.fetch_url',side_effect=fetch),patch('feeds.parse_irc',return_value={'valid':True}) as parse:
   self.assertEqual(irc_feed(),{'valid':True});parse.assert_called_once_with('results',URL,'stamp')
 def test_archive_fallback_when_home_still_contains_turnout(self):
  def fetch(url):return ('<option value="IND|4444">11/03/2026 General Election</option>',None) if url==ARCHIVE else ('<iframe src="https://tqv.vrswebapps.com/"></iframe>',None) if url==HOME else ('returns',None)
  with patch('feeds.config.IRC_GENERAL_ID',''),patch('feeds.fetch_url',side_effect=fetch),patch('feeds.parse_irc',return_value={'ok':True}):self.assertEqual(irc_feed(),{'ok':True})
 def test_actual_parser_rejects_old_home_election_then_stays_pending(self):
  def fetch(url):return ('<iframe src="'+URL+'"></iframe>',None) if url==HOME else ('Election Date: 8/18/2026 Primary Election',None) if url==URL else ('',None)
  with patch('feeds.config.IRC_GENERAL_ID',''),patch('feeds.fetch_url',side_effect=fetch):
   with self.assertRaises(NotPublished):irc_feed()
 def test_empty_home_and_archive_never_use_turnout(self):
  with patch('feeds.config.IRC_GENERAL_ID',''),patch('feeds.fetch_url',return_value=('<iframe src="https://tqv.vrswebapps.com/"></iframe>',None)):
   with self.assertRaises(NotPublished):irc_feed()
 def test_home_network_failure_can_use_valid_archive(self):
  def fetch(url):
   if url==HOME:raise OSError('offline')
   return ('<option value="IND|4444">11/3/2026 General Election</option>',None) if url==ARCHIVE else ('returns',None)
  with patch('feeds.config.IRC_GENERAL_ID',''),patch('feeds.fetch_url',side_effect=fetch),patch('feeds.parse_irc',return_value={'ok':True}):self.assertEqual(irc_feed(),{'ok':True})
 def test_pending_discovery_does_not_back_off_to_fifteen_minutes(self):
  with tempfile.TemporaryDirectory() as path:
   engine=Engine(path)
   try:
    engine.sources['indian_river']['failures']=20
    with patch.dict('store.ADAPTERS',{'indian_river':lambda:(_ for _ in ()).throw(NotPublished('pending'))}):engine.refresh_one('indian_river')
    self.assertLessEqual(engine.sources['indian_river']['next_due']-time.time(),61)
   finally:engine.close();engine.db.conn.close()
