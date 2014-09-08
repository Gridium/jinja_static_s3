#!/usr/bin/env python3

from os import path

import jinja2

import static.jinja

# avert your eyes! horrible hacks follow to deal with local filesystem
class GPBundleExtension(static.jinja.BundleExtension):
    def _load_bundle(self, *args, **kwargs):
        tag = super()._load_bundle(*args, **kwargs)
        return tag.replace('"/static/bundles/', '"static/bundles/')
class GPImgExtension(static.jinja.ImgExtension):
    def get_img_url(self, filename, caller):
        url = super().get_img_url(filename, caller)
        if url.startswith('/static/img/'):
            return path.join(static.jinja.static_dir, 'img', filename)
        return url
static.jinja.jinja_env = jinja2.Environment(autoescape=False, cache_size=0, extensions=[GPImgExtension])
# ok you can look now

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
    autoescape=True,
    extensions=[GPBundleExtension, GPImgExtension],
)

template = env.get_template('root.jinja2')
context = {'title': 'Jinja Static S3 demo'}
rendered = template.render(context)
with open('root.html', 'w') as f:
    f.write(rendered)
