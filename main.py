#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools

import pkg_resources
import requests
import flask
from flask import Flask, render_template
from flask.ext.bootstrap import Bootstrap
from werkzeug.contrib.cache import SimpleCache

app = Flask(__name__)
Bootstrap(app)
app.config['BOOTSTRAP_USE_CDN'] = True

cache = SimpleCache()

# Because I want a certain order and because adding new ones will take some actual work
platforms = [
    ('auto', 'Automatic'),
    ('ubuntu', 'Ubuntu'),
    ('el', 'Red Hat/Fedora'),
    ('debian', 'Debian'),
    ('solaris', 'Solaris'),
    ('osx', 'Mac OS X'),
    ('windows', 'Windows')
]
platform_aliases = {'solaris': 'solaris2', 'osx': 'mac_os_x'}
arch_ranking = ['x86_64', 'i686', 'i386', 'sparc']

def chef_package_info(*args):
    rv = getattr(flask.g, 'chef_package_info', None)
    if rv is None:
        rv = flask.g.chef_package_info = requests.get('http://www.opscode.com/chef/full_list').json
    if args:
        # Make nicer URLs by hiding the internal names
        args = (platform_aliases.get(args[0], args[0]),) + args[1:]
        rv = reduce(lambda v, key: v.get(key, {}), args, rv)
    return rv

@app.route('/<platform>/<version>/<arch>/<chef_version>/')
def render(platform, version, arch, chef_version):
    versions = []
    raw_versions = chef_package_info(platform)
    if raw_versions:
        for ver, ver_data in sorted(raw_versions.iteritems(), key=lambda v: pkg_resources.parse_version(v[0])):
            for ar in sorted(ver_data.iterkeys(), key=lambda a: arch_ranking.index(a), reverse=True):
                versions.append((ver, ar))
    download_url = 'http://opscode-omnitruck-release.s3.amazonaws.com/%s'%chef_package_info(platform, version, arch, chef_version)
    return render_template('main.html', version_info=chef_package_info(), 
                                        platforms=platforms,
                                        raw_platform=platform,
                                        platform=platform_aliases.get(platform, platform),
                                        versions=versions,
                                        version=version,
                                        arch=arch,
                                        chef_version=chef_version,
                                        download_url=download_url)

@app.route('/<platform>/<version>/<arch>/')
def render_latest_chef_verison(platform, version, arch):
    chef_versions = chef_package_info(platform, version, arch)
    latest = max(itertools.ifilter(lambda v: 'rc' not in v, chef_versions), key=pkg_resources.parse_version) if chef_versions else None
    return render(platform, version, arch, latest)

@app.route('/<platform>/<version>/')
def render_default_arch(platform, version):
    archs = chef_package_info(platform, version)
    default_arch = min(archs, key=lambda a: arch_ranking.index(a)) if archs else None
    return render_latest_chef_verison(platform, version, default_arch)

@app.route('/<platform>/')
def render_latest_version(platform):
    versions = chef_package_info(platform)
    latest = max(versions, key=pkg_resources.parse_version) if versions else None
    return render_default_arch(platform, latest)

@app.route('/')
def render_default():
    return render_latest_version('auto')

if __name__ == '__main__':
    app.run(debug=True)
