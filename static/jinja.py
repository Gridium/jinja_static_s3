#!/usr/bin/env python3

import hashlib
import http.client
import os
from os import path
import shutil
import subprocess
import sys

import jinja2
from jinja2.ext import Extension

if __name__ == '__main__':
    sys.path.insert(0, path.normpath(path.join(path.dirname(path.abspath(__file__)), '..')))

import config
from static.bundles import bundles

static_dir = path.dirname(path.abspath(__file__))
compiled_css_path = os.path.join(static_dir, 'css', 'compiled')

class BundleExtension(Extension): # for pyramid/html templates
    tags = set(['js_bundle', 'css_bundle'])

    def parse(self, parser):
        tag = parser.stream.current.value
        bundle_type = tag[:len(tag)-len('_bundle')]
        lineno = next(parser.stream).lineno
        args = [jinja2.nodes.Const(bundle_type), parser.parse_expression()]
        cb = jinja2.nodes.CallBlock(self.call_method('_load_bundle', args), [], [], '')
        cb.set_lineno(lineno)
        return cb

    def _load_bundle(self, bundle_type, name, caller):
        if config.STATIC_FROM_S3:
            digest = bundle_hashes[bundle_type][name]
            if bundle_type == 'js':
                fmtstr = '<script src="https://{}.s3.amazonaws.com/js/{}_{}.js"></script>'
            elif bundle_type == 'css':
                fmtstr = '<link href="https://{}.s3.amazonaws.com/css/{}_{}.css" rel="stylesheet">'
            return fmtstr.format(config.S3_BUCKET, name, digest)

        files = bundles[bundle_type][name]
        bundle_dir = path.join(static_dir, 'bundles', bundle_type)

        if not os.path.exists(bundle_dir):
            os.makedirs(bundle_dir, exist_ok=True)

        rebuild = False
        bundle_path = path.join(bundle_dir, '{}.{}'.format(name, bundle_type))
        try:
            bundle_mtime = os.stat(bundle_path).st_mtime_ns
        except FileNotFoundError:
            bundle_mtime = 0
            rebuild = True
        if bundle_type == 'js' and not rebuild: # check js mtimes
            for filename in files:
                mtime = os.stat(path.join(static_dir, 'js', filename)).st_mtime_ns
                if mtime > bundle_mtime:
                    rebuild = True
                    break
        elif bundle_type == 'css': # recompile less if any files have changed (because @import)
            if not os.path.exists(compiled_css_path):
                os.makedirs(compiled_css_path, exist_ok=True)
            less_mtime = preprocess_less()
            if less_mtime > bundle_mtime:
                rebuild = True

        if rebuild:
            if bundle_type == 'js':
                bundle_js(bundle_path, files)
            elif bundle_type == 'css':
                with open(bundle_path, 'wb') as out:
                    try:
                        for filename in files:
                            out.write(compile_less(filename) + b'\n')
                    except:
                        os.remove(bundle_path)
                        raise

        if bundle_type == 'js':
            fmtstr = '<script src="/static/bundles/js/{}.js"></script>'
        elif bundle_type == 'css':
            fmtstr = '<link href="/static/bundles/css/{}.css" rel="stylesheet">'
        return fmtstr.format(name)

class ImgExtension(Extension):
    tags = set(['img'])

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        args = [parser.parse_expression()]
        cb = jinja2.nodes.CallBlock(self.call_method('get_img_url', args), [], [], '')
        cb.set_lineno(lineno)
        return cb

    def get_img_url(self, filename, caller):
        if config.STATIC_FROM_S3:
            root, ext = path.splitext(filename)
            digest = bundle_hashes['img'][filename]
            return 'https://{}.s3.amazonaws.com/img/{}_{}{}'.format(config.S3_BUCKET, root, digest, ext)
        else:
            return '/static/img/' + filename

def bundle_js(bundle_path, files):
    with open(bundle_path, 'wb') as out:
        for filename in files:
            if filename.startswith('templates/') and filename.endswith('.hbs'):
                js_templates_path = path.join(static_dir, 'js', 'templates')
                command = [path.join(static_dir, 'etc', 'bin', 'compiler'), filename[len('templates/'):]]
                lessc = subprocess.Popen(command, cwd=js_templates_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                output = lessc.communicate()[0]
                if lessc.returncode != 0:
                    raise subprocess.CalledProcessError(lessc.returncode, command)
                out.write(output)
            else:
                with open(path.join(static_dir, 'js', filename), 'rb') as f:
                    out.write(f.read() + b'\n')

jinja_env = jinja2.Environment(autoescape=False, cache_size=0, extensions=[ImgExtension])
def preprocess_less(dirpath=None):
    css_path = path.join(static_dir, 'css')
    if dirpath is None:
        dirpath = css_path
    latest_mtime = 0
    for node in os.listdir(dirpath):
        if node == 'compiled':
            continue
        abspath = path.join(dirpath, node)
        if path.isdir(abspath):
            time = preprocess_less(abspath)
            if time > latest_mtime:
                latest_mtime = time
        else:
            preprocessed_path = path.join(compiled_css_path, path.relpath(abspath, css_path))
            preprocess = True
            less_mtime = os.stat(abspath).st_mtime_ns
            if path.exists(preprocessed_path):
                preprocessed_mtime = os.stat(preprocessed_path).st_mtime_ns
                if less_mtime <= preprocessed_mtime:
                    preprocess = False
                if less_mtime > latest_mtime:
                    latest_mtime = less_mtime
            else:
                latest_mtime = float('inf')
            if preprocess:
                with open(abspath, 'r') as infile, open(preprocessed_path, 'w') as outfile:
                    less_stream = jinja_env.from_string(infile.read()).stream()
                    less_stream.dump(outfile)
    return latest_mtime

def compile_less(infile):
    command = [path.join(static_dir, 'less', 'bin', 'lessc'), infile]
    lessc = subprocess.Popen(command, cwd=compiled_css_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output = lessc.communicate()[0]
    if lessc.returncode != 0:
        raise subprocess.CalledProcessError(lessc.returncode, command)
    return output

def hash_bundles(img_only):
    rval = {}
    if not img_only:
        for bundle_type in bundles:
            rval[bundle_type] = {}
            for bundle in bundles[bundle_type]:
                filename = '{}.{}'.format(bundle, bundle_type)
                with open(path.join(static_dir, 'bundles', bundle_type, filename), 'rb') as f:
                    contents = f.read()
                digest = hashlib.md5(contents).hexdigest()
                rval[bundle_type][bundle] = digest
    rval['img'] = {}
    for dirpath, _, filenames in os.walk(path.join(static_dir, 'img')):
        for filename in filenames:
            img_path = path.join(dirpath, filename)
            rel_path = img_path[len(path.commonprefix([path.join(static_dir, 'img'), img_path]))+1:]
            with open(img_path, 'rb') as f:
                digest = hashlib.md5(f.read()).hexdigest()
            rval['img'][rel_path] = digest
    return rval

def s3_upload(bucket, filename, contents):
    from _sha1 import sha1
    from base64 import b64encode
    import hmac
    import mimetypes
    import time
    from wsgiref.handlers import format_date_time

    mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    timestamp = time.time()
    date = format_date_time(timestamp)
    string_to_sign = '\n'.join(['PUT', '', mimetype, date, '/{}/{}'.format(bucket, filename)])
    signature = hmac.new(config.AWS_ACCESS_KEY_SECRET.encode(), string_to_sign.encode(), sha1).digest()
    signature = b64encode(signature).decode()
    headers = {
        'Authorization': 'AWS {}:{}'.format(config.AWS_ACCESS_KEY_ID, signature),
        'Content-Length': len(contents),
        'Content-Type': mimetype,
        'Date': date,
        'Expires': format_date_time(timestamp + 365 * 24 * 60 * 60),
    }
    conn = http.client.HTTPSConnection(bucket + '.s3.amazonaws.com')
    conn.request('PUT', '/' + filename, contents, headers)
    response = conn.getresponse()
    if response.status != 200:
        raise RuntimeError('s3 upload failed with {} {}: {}'.format(response.status, response.reason, response.read()))

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ['compile', 'deploy']:
        print('usage: {} [compile|deploy]'.format(sys.argv[0]))
        sys.exit(1)
    elif not config.STATIC_FROM_S3:
        print('STATIC_FROM_S3 is False!')
        sys.exit(1)

    if not os.path.exists(path.join(static_dir, 'bundles', 'js')):
        os.makedirs(path.join(static_dir, 'bundles', 'js'), exist_ok=True)

    if not os.path.exists(path.join(static_dir, 'bundles', 'css')):
        os.makedirs(path.join(static_dir, 'bundles', 'css'), exist_ok=True)

    if sys.argv[1] == 'compile':
        for bundle, files in bundles['js'].items():
            print('bundling {}.js'.format(bundle))
            bundle_path = path.join(static_dir, 'bundles', 'js', bundle + '.js')
            bundle_js(bundle_path, files)
        shutil.rmtree(compiled_css_path, ignore_errors=True)
        os.makedirs(compiled_css_path)
        preprocess_less()
        for bundle, files in bundles['css'].items():
            print('bundling {}.css'.format(bundle))
            bundle_path = path.join(static_dir, 'bundles', 'css', bundle + '.css')
            with open(bundle_path, 'wb') as out:
                try:
                    for filename in files:
                        out.write(compile_less(filename) + b'\n')
                except:
                    os.remove(bundle_path)
                    raise
    elif sys.argv[1] == 'deploy':
        # upload js and css files
        for bundle_type in bundles:
            for bundle in bundles[bundle_type]:
                filename = '{}.{}'.format(bundle, bundle_type)
                with open(path.join(static_dir, 'bundles', bundle_type, filename), 'rb') as f:
                    contents = f.read()
                digest = bundle_hashes[bundle_type][bundle]
                s3_filename = '{}/{}_{}.{}'.format(bundle_type, bundle, digest, bundle_type)
                print('uploading', s3_filename)
                s3_upload(config.S3_BUCKET, s3_filename, contents)
        # upload images
        conn = http.client.HTTPSConnection(config.S3_BUCKET + '.s3.amazonaws.com')
        for dirpath, _, filenames in os.walk(path.join(static_dir, 'img')):
            for filename in filenames:
                img_path = path.join(dirpath, filename)
                rel_path = img_path[len(path.commonprefix([static_dir, img_path]))+1:]
                print('checking', rel_path, end=' ... ')
                with open(img_path, 'rb') as f:
                    contents = f.read()
                digest = bundle_hashes['img'][rel_path[len('img/'):]]
                root, ext = path.splitext(filename)
                s3_path = path.join(path.dirname(rel_path), '{}_{}{}'.format(root, digest, ext))
                conn.request('HEAD', '/' + s3_path)
                response = conn.getresponse()
                if response.status == http.client.FORBIDDEN:
                    print('uploading', s3_path, '...')
                    s3_upload(config.S3_BUCKET, s3_path, contents)
                elif response.status == http.client.OK and response.headers['ETag'].strip('"') == digest:
                    print(s3_path, 'already up to date')
                else:
                    raise RuntimeError(
                        'unexpected s3 response to HEAD: {status} {reason}\n{headers}'.format(**response.__dict__)
                    )
                response.close()

if config.STATIC_FROM_S3:
    img_only = (len(sys.argv) == 2 and sys.argv[1] == 'compile')
    bundle_hashes = hash_bundles(img_only)
if __name__ == '__main__':
    main()
