### Static files for [Jinja2](http://jinja2.pocoo.org/) with [S3](https://aws.amazon.com/s3/)/[Pyramid](http://www.pylonsproject.org/)/[LESS](http://lesscss.org/) integration

This repo demonstrates how Gridium handles static files in some of our apps.
It has a number of nice features:

#### In development:
* LESS is compiled to CSS and both JS and CSS are bundled when the page loads, so you
  1. don't have to wait the half second for your "watch" tool to compile after saving
  2. get an actual error when there's a compilation error
* This only happens if the mtimes of your LESS/JS files change (switching branches in git updates the mtimes of any files that are different)

#### In production:
* The same LESS/JS files are compiled with a just config change and uploaded to S3, so your static files are now served from a CDN with the same jinja2 templates
* Uploaded filenames become `[name]_[md5].[ext]` where `[md5]` is the digest of the *contents*. S3 is told to serve them with a max Expires header ([365 days](http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.21)), so you get all the benefits of browser caching and none of the problems
* Images are only uploaded if they have changed
* The `ImgExtension` gets applied to LESS files too, so image `url()`s in your CSS are served from S3 too

Now that you are convinced this is the best way to handle static files, here's how to get started:

#### with pyramid, jinja2, pyramid-jinja2 installed
1. Run `./server`. Visit [http://localhost:6543](http://localhost:6543).
2. Read `config.py` and create a `localconfig.py` with AWS credentials and `STATIC_FROM_S3 = True`. Run `static/jinja.py compile && static/jinja.py deploy`. Repeat step 1.

#### with pyramid, jinja2, pyramid-jinja2, gunicorn, nginx installed
1. Configure nginx (or your webserver of choice) to serve `/static/*` from the `static/` directory and reverse-proxy everything else to `localhost:6543`
2. Run `gunicorn -b 127.0.0.1:6543 -w 2 server:app`. Visit [http://localhost](http://localhost).
3. Perform step 2 above.

This is how we do things in production. In this configuration, the `add_static_view` line of `server.py` never gets used. (In development, we use a hybrid of these two.)

#### with just jinja2 installed
1. Run `./gen_page.py`. Ignore the horrible monkey-patching in that file. Load `root.html` in your browser.
2. Perform step 3 immediately above.
