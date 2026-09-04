"""Free domain preparation using existing Heroku CLI authentication, never Doppler.

Old CLI omits API-required sni_endpoint. No DNS/config vars/dynos are changed here.
Auth stays in process memory and is never emitted or stored in a file.
"""
import json
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

APP = 'student-os-ernar-beta'
DOMAIN = 'student-os.dev'


def main():
    result = subprocess.run([r'C:\Program Files\heroku\bin\heroku.cmd', 'auth:token'],
                            capture_output=True, text=True, timeout=30)
    if result.returncode or not result.stdout.strip():
        print('Existing Heroku authentication unavailable; no login attempted')
        return 1
    headers = {'Authorization': 'Bearer ' + result.stdout.strip(),
               'Accept': 'application/vnd.heroku+json; version=3',
               'Content-Type': 'application/json'}
    result = None
    endpoint = 'https://api.heroku.com/apps/' + APP + '/domains'
    try:
        with urlopen(Request(endpoint, headers=headers), timeout=30) as response:
            domains = json.load(response)
        domain = next((item for item in domains if item.get('hostname') == DOMAIN), None)
        if domain is None:
            body = json.dumps({'hostname': DOMAIN, 'sni_endpoint': None}).encode()
            with urlopen(Request(endpoint, data=body, headers=headers, method='POST'), timeout=30) as response:
                domain = json.load(response)
        print(json.dumps({key: domain.get(key) for key in ('hostname', 'cname', 'status')}))
        return 0
    except HTTPError as error:
        print('Domain preparation failed; HTTP status:', error.code)
    except (URLError, TimeoutError, ValueError):
        print('Domain preparation incomplete; details suppressed')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
