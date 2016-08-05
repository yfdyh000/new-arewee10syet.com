A generator for arewee10syet.com. Uses data from a couple of sources:

* mozilla telemetry, which is stored on S3
* data from addons.mozilla.org which it pulls using an API
* data from addons-server-mirror generated and stored in mcp-overall.json
* data stored in data.json (static data in github)


To create your own personal list with your Firefox's addons:
  * get jq, python2, python-requests, python-jinja2
  $ cat ~/.mozilla/firefox/*.default/addons.json|jq '.addons | sort_by(.dailyUsers) | reverse | .[] |= {users: .dailyUsers, name: .name, guid: .id,bugs: [],testing: []}'
    * maybe adapt path
  $ mkdir cache
  $ python2 build.py
  * enjoy index.html
  
