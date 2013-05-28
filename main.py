#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools
import os

import pkg_resources
import requests
import flask
from flask import Flask, render_template
from flask.ext.bootstrap import Bootstrap
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.contrib.cache import SimpleCache

from ordered_set import OrderedSet

app = Flask(__name__)
Bootstrap(app)
app.config['BOOTSTRAP_USE_CDN'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///getchef.db')

db = SQLAlchemy(app)
cache = SimpleCache()

# Because I want a certain order and because adding new ones will take some actual work
all_platforms = [
    ('auto', 'Automatic'),
    ('ubuntu', 'Ubuntu'),
    ('el', 'Red Hat/Fedora'),
    ('debian', 'Debian'),
    ('solaris', 'Solaris'),
    ('osx', 'Mac OS X'),
    ('windows', 'Windows')
]
platform_aliases = {'solaris2': 'solaris', 'mac_os_x': 'osx'}
arch_ranking = ['x86_64', 'i686', 'i386', 'sparc']
arch_ranking.reverse()

class Package(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(255))
    platform_version = db.Column(db.String(255))
    arch = db.Column(db.String(255))
    chef_version = db.Column(db.String(255))
    raw_path = db.Column(db.String(255))
    is_client = db.Column(db.Boolean)
    is_server = db.Column(db.Boolean)
    is_uploaded = db.Column(db.Boolean)

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
        self.platform = platform_aliases.get(self.platform, self.platform)

    def __repr__(self):
        return '<Package %r>' % self.raw_path

    def opscode_url(self):
        return 'https://s3.amazonaws.com/opscode-omnibus-packages'+self.raw_path

    @staticmethod
    def walk_omnitruck(omnitruck_data):
        for platform, platform_data in omnitruck_data.iteritems():
            for platform_version, platform_version_data in platform_data.iteritems():
                for arch, arch_data in platform_version_data.iteritems():
                    for chef_version, raw_path in arch_data.iteritems():
                        yield {
                            'platform': platform,
                            'platform_version': platform_version,
                            'arch': arch,
                            'chef_version': chef_version,
                            'raw_path': raw_path,
                        }

    @classmethod
    def load_omnitruck(cls, omnitruck_data, is_server=False):
        for attributes in cls.walk_omnitruck(omnitruck_data):
            if is_server:
                attributes['is_server'] = True
            else:
                attributes['is_client'] = True
            row = cls.query.filter_by(**attributes).first()
            if row is None:
                db.session.add(cls(**attributes))
        db.session.commit()

    @classmethod
    def load_all_omnitruck(cls):
        cls.load_omnitruck(requests.get('http://www.opscode.com/chef/full_list').json(), False)
        cls.load_omnitruck(requests.get('http://www.opscode.com/chef/full_server_list').json(), True)

def chef_package_info(*args):
    rv = getattr(flask.g, 'chef_package_info', None)
    if rv is None:
        rv = flask.g.chef_package_info = requests.get('http://www.opscode.com/chef/full_list').json
    if args:
        # Make nicer URLs by hiding the internal names
        args = (platform_aliases.get(args[0], args[0]),) + args[1:]
        rv = reduce(lambda v, key: v.get(key, {}), args, rv)
    return rv

@app.route('/')
@app.route('/<platform>/')
@app.route('/<platform>/<version>/')
@app.route('/<platform>/<version>/<arch>/')
@app.route('/<platform>/<platform_version>/<arch>/<chef_version>/')
def render(platform='auto', platform_version=None, arch=None, chef_version=None):
    params = {'platform': platform}
    if platform_version:
        params['platform_version'] = platform_version
    if arch:
        params['arch'] = arch
    if chef_version:
        params['chef_version'] = chef_version
    packages = list(Package.query.filter_by(**params))
    platform_version_archs = sorted(
        db.engine.execute('SELECT DISTINCT platform_version, arch FROM package WHERE platform = :platform', platform=platform),
        reverse=True,
        key=lambda (ver, ar): (pkg_resources.parse_version(ver), arch_ranking.index(ar))
    )
    platform_versions = OrderedSet(ver for ver, ar in platform_version_archs)
    archs = OrderedSet(ar for ver, ar in platform_version_archs)
    chef_versions = sorted(set(pkg.chef_version for pkg in packages), reverse=True, key=pkg_resources.parse_version)
    if not platform_version:
        platform_version = iter(platform_versions).next()
    if not arch:
        arch = iter(archs).next()
    if not chef_version:
        chef_version = chef_versions[0]
    return render_template('main.html', packages=packages,
                                        all_platforms=all_platforms,
                                        platform=platform,
                                        platform_version=platform_version,
                                        arch=arch,
                                        platform_versions=platform_versions,
                                        archs=archs,
                                        platform_version_archs=platform_version_archs,
                                        chef_versions=chef_versions)

if __name__ == '__main__':
    app.run(debug=True)
