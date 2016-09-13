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
mcp_overall = json.load(open('mcp-overall.json', 'r'))

tm_root = 'https://s3-us-west-2.amazonaws.com/telemetry-public-analysis-2'
addon_perf = [
    ['shim', tm_root + '/e10s-addon-perf/data/shim-data.json'],
    ['cpow', tm_root + '/e10s-addon-perf/data/cpow-data.json']
]


fixups = {
    'testpilot@labs.mozilla.com': 'Test Pilot (old one)',
    '{20a82645-c095-46ed-80e3-08825760534b}': 'Microsoft .NET framework assistant',
}


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


def process_amo(result, compat):
    try:
        name = result['name']['en-US']
    except KeyError:
        name = result['slug']
    return {
        'name': name,
        'url': result['url'],
        'guid': result['guid'],
        # This doesn't exist yet.
        'status': compat['e10s'],
        'id': result['id']
    }


def amo(guid):
    addon_url = amo_server + '/api/v3/addons/addon/{}/'.format(guid)
    addon_data = get_cache(addon_url)

    compat_url = amo_server + '/api/v3/addons/addon/{}/feature_compatibility/'.format(guid)
    compat_data = get_cache(compat_url)
    if addon_data and compat_data:
        return process_amo(addon_data, compat_data)

    data = []
    for url in (addon_url, compat_url):
        print 'Fetching', url
        res = requests.get(url)
        if res.status_code != 200:
            return {
                'name': fixups.get(
                    guid, '{} error fetching data from AMO'.format(res.status_code)),
                'url': '',
                'guid': guid,
                'status': 'error',
                'id': 0
            }

        res.raise_for_status()
        res_json = res.json()
        set_cache(url, res_json)
        data.append(res_json)

    return process_amo(*data)


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
        about['shim'] = {}
        about['cpow'] = {}
        about['bugs'] = bugzilla(addon['bugs'])
        data[addon['guid']] = about

    telemetry = fetch_telemetry()
    for key, values in telemetry.items():
        for value in values:
            # cpow     
            if len(value) == 2:
                guid = value[0][0]
                version = value[0][1]
                v = int(value[1])
            # shim
            elif len(value) == 3:
                try:
                    guid = value[1][0]
                    version = value[1][1]
                    v = value[2]
                except IndexError:
                    print 'Skipping bad {} data'.format(key)
            else:
                raise ValueError('Unknown telemetry')

            if guid in data:
                data[guid][key][version] = v

    return data


def featured():
    # Fast, no need to cache.
    url = amo_server + '/api/v3/addons/featured/'
    res = requests.get(url, params={'app': 'firefox', 'type': 'extension'})
    res.raise_for_status()
    res_json = res.json()
    return [r['id'] for r in res_json['results']]


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
    sorted_addons = sorted([[v.get('users', 0), v] for v in addons.values()])
    sorted_addons = reversed([v for _, v in sorted_addons])

    data = {
        'addons': sorted_addons,
        'featured': featured(),
        'mcp_overall': mcp_overall
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
