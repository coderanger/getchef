import posixpath
from cStringIO import StringIO

import depot
import requests
from flask.ext.script import Manager, Server, prompt_bool

import main
from main import app, db, Package

APT_PLATFORMS = ['ubuntu', 'debian']
APT_CODENAMES = {
    'ubuntu': {
        '10.04': 'lucid',
        '10.10': 'maverick',
        '11.04': 'natty',
        '11.10': 'oneiric',
        '12.04': 'precise',
        '12.10': 'quantal',
        '13.04': 'raring',
    },
    'debian': {
        '5': 'lenny',
        '6': 'squeeze',
        '7': 'wheezy',
    },
}

manager = Manager(app)
manager.add_command('server', Server())

@manager.shell
def shell():
    return main.__dict__

@manager.command
def syncdb():
    db.create_all()

@manager.command
def dropdb():
    if prompt_bool('This will delete all data, are you sure'):
        db.drop_all()

@manager.command
def omnitruck():
    Package.load_all_omnitruck()

@manager.command
def packages():
    storage = depot.StorageWrapper('s3://apt.getchef.org')
    for platform in APT_PLATFORMS:
        for pkg in Package.query.filter_by(platform=platform, is_uploaded=False):
            if pkg.is_prerelease:
                continue
            codename = APT_CODENAMES.get(pkg.platform, {}).get(pkg.platform_version)
            if not codename:
                continue
            print 'Uploading %s for %s %s'%(pkg.opscode_url, pkg.platform, codename)
            repo = depot.AptRepository(storage, None, codename, architecture=pkg.arch)
            data = requests.get(pkg.opscode_url)
            repo.add_package(posixpath.basename(pkg.raw_path), StringIO(data.content))


if __name__ == '__main__':
    manager.run()
