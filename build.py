# -*- coding: utf-8 -*-
import hashlib
import json
import os
import sys

from jinja2 import Environment, FileSystemLoader

import requests

amo_server = os.getenv('AMO_SERVER', 'https://addons.mozilla.org')
bugzilla_server = os.getenv('BUGZILLA_SERVER', 'https://bugzilla.mozilla.org')

addons = json.load(open('data.json', 'r'))

tm_root = 'https://s3-us-west-2.amazonaws.com/telemetry-public-analysis'
addon_perf = [
    ['shim', tm_root + '/e10s-addon-perf/data/shim-data.json'],
    ['cpow', tm_root + '/e10s-addon-perf/data/cpow-data.json']
]


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
    results = []
    for bug in bugs:
        data = None
        url = bugzilla_server + '/rest/bug/{}'.format(bug)
        cached = get_cache(url)
        if cached:
            data = cached

        else:
            print 'Fetching', url
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            set_cache(url, data)

        results.append({
            'id': bug,
            'state': data['bugs'][0]['status'],
            'url': 'https://bugzilla.mozilla.org/show_bug.cgi?id={}'.format(bug)
        })

    return results


def fetch_all():
    data = {}
    for k, addon in enumerate(addons):
        about = addon
        about.update(amo(addon['guid']))
        about['number'] = k
        about['cpow'] = 0
        about['bugs'] = bugzilla(addon['bugs'])
        data[addon['guid']] = about

    telemetry = fetch_telemetry()
    for key, values in telemetry.items():
        for value in values:
            # guid
            if len(value) == 2:
                guid = value[0][0]
                v = int(value[1])
            # shim
            elif len(value) == 3:
                guid = value[1][0]
                v = value[2]
            else:
                raise ValueError('Unknown telemetry')

            if guid in data:
                data[guid][key] = v

    return data


def fetch_telemetry():
    results = {}

    for key, url in addon_perf:
        cached = get_cache(url)
        if cached:
            data = cached

        else:
            print 'Fetching', url
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            set_cache(url, data)

        results[key] = data

    return results


def build():
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('template.html')

    addons = fetch_all()
    sorted_addons = sorted([[v['users'], v] for v in addons.values()])
    sorted_addons = reversed([v for _, v in sorted_addons])

    data = {
        'addons': sorted_addons
    }
    output = template.render(data)
    open('index.html', 'w').write(output.encode('utf-8'))


if __name__=='__main__':
    if 'clear-cache' in sys.argv:
        print 'Removing cached data.'
        for root, _, files in os.walk(os.path.join('cache')):
            for filename in files:
                full_filename = os.path.join('cache', filename)
                if full_filename.endswith('.json'):
                    os.remove(full_filename)

    build()
