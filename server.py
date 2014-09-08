#!/usr/bin/env python3

import subprocess
import sys
from wsgiref.simple_server import make_server

from pyramid.config import Configurator
from pyramid.view import view_config

import config

if config.RELOAD:
    if len(sys.argv) > 1:
        from pyramid.scripts.pserve import install_reloader
        install_reloader()
    else:
        while True:
            proc = subprocess.Popen(['python3', sys.argv[0], 'reloader'])
            try:
                exit_code = proc.wait()
            except KeyboardInterrupt:
                sys.exit()
            if exit_code != 3:
                sys.exit(exit_code)

c = Configurator(
    settings={
        'reload_templates': config.RELOAD,
        'jinja2.extensions': ['static.jinja.BundleExtension', 'static.jinja.ImgExtension'],
    }
)
c.include('pyramid_jinja2')
c.add_jinja2_search_path('templates')

def root_view(request):
    return {'title': 'Jinja Static S3 demo'}
c.add_route('root', '/')
c.add_view(root_view, route_name='root', renderer='root.jinja2')
c.add_static_view(name='static', path='static')

app = c.make_wsgi_app()

if __name__ == '__main__':
    server = make_server('0.0.0.0', 6543, app)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
