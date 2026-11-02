import gzip,io,unittest
from unittest.mock import patch
from feeds import fetch_robinhood_url
from robinhood import CONGRESS_URL
class Response(io.BytesIO):
 def __init__(self,data,encoding='gzip'):super().__init__(data);self.headers={'Content-Encoding':encoding}
class RobinhoodTransportTests(unittest.TestCase):
 def test_gzip_public_page_decoded(self):
  with patch('feeds.urllib.request.urlopen',return_value=Response(gzip.compress(b'public page'))) as request:
   self.assertEqual(fetch_robinhood_url(CONGRESS_URL),('public page',None))
   self.assertEqual(request.call_args.args[0].get_header('Accept-encoding'),'gzip')
 def test_compressed_and_decompressed_limits(self):
  for data in [gzip.compress(b'x'*101),b'x'*101]:
   with self.subTest(data=len(data)),patch('feeds.config.MAX_RESPONSE_BYTES',100),patch('feeds.urllib.request.urlopen',return_value=Response(data)):
    with self.assertRaises(ValueError):fetch_robinhood_url(CONGRESS_URL)
 def test_only_reviewed_public_urls_requested(self):
  with patch('feeds.urllib.request.urlopen') as request:
   for url in ['https://robinhood.com/login/','https://example.com/','https://robinhood.com@evil.example/']:
    with self.assertRaises(ValueError):fetch_robinhood_url(url)
   request.assert_not_called()
