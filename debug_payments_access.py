import http.cookiejar
import urllib.request
import urllib.parse
from urllib.error import HTTPError

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
login_data = urllib.parse.urlencode({'email': 'admin@example.com', 'mot_de_passe': 'admin123'}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:5000/login', data=login_data)
try:
    resp = opener.open(req)
    print('login status', resp.getcode())
except HTTPError as e:
    print('login error', e.code)
    print(e.read().decode('utf-8')[:2000])
    raise

try:
    resp = opener.open('http://127.0.0.1:5000/payments')
    text = resp.read().decode('utf-8')
    print(text[:2000])
except HTTPError as e:
    print('payments error', e.code)
    print(e.read().decode('utf-8')[:4000])
    raise
except Exception as ex:
    import traceback
    traceback.print_exc()
