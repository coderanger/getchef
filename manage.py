from flask.ext.script import Manager, Server, Shell, prompt_bool

import main
from main import app, db, Package

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

if __name__ == '__main__':
    manager.run()
