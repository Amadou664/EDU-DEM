import urllib.request
import urllib.error
import traceback

try:
    resp = urllib.request.urlopen('http://127.0.0.1:5000/payments')
    text = resp.read().decode('utf-8')
    print(text[:2000])
except urllib.error.HTTPError as e:
    print('HTTPError', e.code)
    print(e.read().decode('utf-8')[:2000])
except Exception:
    traceback.print_exc()
