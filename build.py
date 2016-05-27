# -*- coding: utf-8 -*-
import hashlib
import json
import os

from jinja2 import Environment, FileSystemLoader

import requests

amo_server = os.getenv('AMO_SERVER', 'https://addons.mozilla.org')
bugzilla_server = os.getenv('BUGZILLA_SERVER', 'https://bugzilla.mozilla.org')

addons = json.load(open('data.json', 'r'))


def url_hash(url):
    hsh = hashlib.md5()
    hsh.update(url)
    return hsh.hexdigest()


def set_cache(url, result):
    filename = os.path.join('cache', url_hash(url) + '.json')
    json.dump(result, open(filename, 'w'))


def get_cache(url):
    filename = os.path.join('cache', url_hash(url) + '.json')
    if os.path.exists(filename):
        return json.load(open(filename, 'r'))


def process_amo(result):
    return {
        'name': result['name']['en-US'],
        'url': result['url'],
        'guid': result['guid'],
        # This doesn't exist yet.
        'status': 'compatible'
    }


def amo(guid):
    url = amo_server + '/api/v3/addons/addon/{}/'.format(guid)
    cached = get_cache(url)
    if cached:
        return process_amo(get_cache(url))

    print 'Fetching', url
    res = requests.get(url)
    if res.status_code == 401:
        return {
            'name': 'Unknown',
            'url': '',
            'guid': guid,
            'status': 'unknown'
        }

    res.raise_for_status()
    res_json = res.json()
    set_cache(url, res_json)
    return process_amo(res_json)


def bugzilla(bugs):
    res = []
    for bug in bugs:
        data = None
        url = bugzilla_server + '/rest/bug/{}'.format(bug)
        cached = get_cache(url)
        if cached:
            data = get_cache(url)

        else:
            print 'Fetching', url
            req = requests.get(url)
            req.raise_for_status()
            data = req.json()
            set_cache(url, data)

        res.append({
            'id': bug,
            'state': data['bugs'][0]['status'],
            'url': 'https://bugzilla.mozilla.org/show_bug.cgi?id={}'.format(bug)
        })

    return res

def fetch_all():
    data = []
    for k, addon in enumerate(addons):
        about = addon
        about.update(amo(addon['guid']))
        about['shimmed'] = addon['shimmed']
        about['number'] = k
        about['bugs'] = bugzilla(addon['bugs'])
        data.append(about)

    return data


def build():
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('template.html')

    data = {
        'addons': fetch_all()
    }
    output = template.render(data)
    open('index.html', 'w').write(output.encode('utf-8'))


if __name__=='__main__':
    build()
