RELOAD = True

STATIC_FROM_S3 = False
AWS_ACCESS_KEY_ID = None
AWS_ACCESS_KEY_SECRET = None
S3_BUCKET = None

try:
    from localconfig import *
except ImportError:
    pass
