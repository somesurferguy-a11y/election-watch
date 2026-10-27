#!/usr/bin/env python3
"""Election Watch: dependency-free local TV dashboard (Python 3.10+)."""
import argparse
import base64
import hmac
import json
import logging
import mimetypes
import secrets
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
import config
from store import Engine
from validation import validate_results, validate_polls

class DashboardServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,engine):
        self.engine=engine;self.csrf=secrets.token_urlsafe(32)
        self.allowed_hosts={'localhost','127.0.0.1','::1',socket.gethostname().lower(),address[0]}
        try:self.allowed_hosts.update(socket.gethostbyname_ex(socket.gethostname())[2])
        except OSError:pass
        super().__init__(address,Handler)

class Handler(BaseHTTPRequestHandler):
    server_version='ElectionWatch/2.0'
    def log_message(self,fmt,*args):logging.info(fmt,*args)
    def send_body(self,body,status=200,ctype='application/json; charset=utf-8',extra=None):
        if isinstance(body,(dict,list)):body=json.dumps(body,allow_nan=False).encode()
        elif isinstance(body,str):body=body.encode('utf-8')
        self.send_response(status)
        for key,value in {'Content-Type':ctype,'Content-Length':str(len(body)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",**(extra or {})}.items():self.send_header(key,value)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)
    def valid_host(self):
        try:return urlsplit('//'+self.headers.get('Host','')).hostname.lower() in self.server.allowed_hosts
        except (ValueError,AttributeError):return False
    def authorized(self):
        if not config.HOST_PASSWORD:return self.client_address[0] in ['127.0.0.1','::1']
        auth=self.headers.get('Authorization','')
        try:
            decoded=base64.b64decode(auth.split(' ',1)[1],validate=True).decode()
            return auth.startswith('Basic ') and hmac.compare_digest(decoded.split(':',1)[1],config.HOST_PASSWORD)
        except (ValueError,IndexError,UnicodeError):return False
    def require_admin(self):
        if not self.authorized():
            self.send_body({'error':'Host password required'},401,extra={'WWW-Authenticate':'Basic realm="Election Watch Host"'});return False
        return True
    def do_GET(self):
        if not self.valid_host():return self.send_body({'error':'Unrecognized host'},403)
        path=urlsplit(self.path).path
        try:
            if path in ['/api/v1/state','/api/v1/elections/general_2026/results']:return self.send_body(self.server.engine.state())
            if path=='/api/v1/polls':
                s=self.server.engine.state();return self.send_body({'demo':s['demo'],'polls':s['polls']})
            if path=='/api/v1/markets':
                s=self.server.engine.state();return self.send_body({'demo':s['demo'],'markets':s['markets']})
            if path in ['/health','/health/live','/api/v1/health']:
                sources=self.server.engine.public_sources()
                return self.send_body({'server':'running','data_status':'degraded' if any(s['status'] not in ['connected','imported'] for s in sources) else 'connected','sources':sources})
            if path=='/api/v1/admin':
                if self.require_admin():self.send_body({'csrf':self.server.csrf,'settings':self.server.engine.settings})
                return
            if path in ['/host','/host/']:
                if not self.require_admin():return
                file=config.ROOT/'templates'/'host.html'
            elif path=='/':file=config.ROOT/'templates'/'index.html'
            elif path.startswith('/static/'):
                base=(config.ROOT/'static').resolve();file=(base/unquote(path[8:])).resolve()
                if not file.is_relative_to(base):return self.send_body({'error':'Forbidden'},403)
            elif path=='/favicon.ico':return self.send_body(b'',204,'image/x-icon')
            else:return self.send_body({'error':'Not found'},404)
            if not file.is_file():return self.send_body({'error':'Not found'},404)
            self.send_body(file.read_bytes(),ctype=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        except (ValueError,OSError,KeyError) as exc:
            logging.exception('GET failed');self.send_body({'error':'Unable to load dashboard; see server log'},500)
    def do_POST(self):
        if not self.valid_host():return self.send_body({'error':'Unrecognized host'},403)
        if not self.require_admin():return
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host'):return self.send_body({'error':'Cross-origin request rejected'},403)
        if self.headers.get('Sec-Fetch-Site')=='cross-site':return self.send_body({'error':'Cross-site request rejected'},403)
        if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),self.server.csrf):return self.send_body({'error':'Missing host token'},403)
        if self.headers.get_content_type()!='application/json':return self.send_body({'error':'JSON required'},415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2_000_000:return self.send_body({'error':'Request must be between 1 byte and 2 MB'},413)
            payload=json.loads(self.rfile.read(length))
            path=urlsplit(self.path).path
            if path=='/api/v1/settings':return self.send_body({'settings':self.server.engine.update_settings(payload)})
            if path=='/api/v1/refresh':return self.send_body({'queued':self.server.engine.check_now(),'message':'Due sources queued. Provider retry windows are respected.'})
            if path=='/api/v1/import':
                source=payload.get('source');data=payload.get('data')
                if source not in ['national','indian_river','polls']:raise ValueError('Import source must be national, indian_river or polls')
                data=validate_polls(data) if source=='polls' else validate_results(data)
                if source!='polls' and any(r['scope']!=source for r in data['races']):raise ValueError('Imported race scope must match the selected source')
                if source=='national':
                    from store import chamber_summary
                    chamber_summary(data['races'])
                self.server.engine.accept(source,data,imported=True)
                return self.send_body({'message':'Sourced snapshot imported; host imports are labeled and do not imply a live connection.'})
            return self.send_body({'error':'Not found'},404)
        except (ValueError,KeyError,TypeError,AttributeError) as exc:return self.send_body({'error':str(exc)},400)
    do_HEAD=do_GET

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=config.PORT);parser.add_argument('--host',default=config.HOST);parser.add_argument('--no-feeds',action='store_true',help='Offline demo/testing; no external requests')
    args=parser.parse_args()
    if args.host not in ['127.0.0.1','localhost','::1'] and not config.HOST_PASSWORD:parser.error('Set ELECTION_HOST_PASSWORD before enabling LAN access')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    engine=Engine();server=DashboardServer((args.host,args.port),engine)
    if not args.no_feeds:engine.start()
    print(f'Election Watch: http://{args.host}:{args.port} | Host controls: /host',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();engine.close()

if __name__=='__main__':main()
