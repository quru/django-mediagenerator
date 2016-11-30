import functools
import threading
from . import settings as media_settings
from .settings import (GLOBAL_MEDIA_DIRS, PRODUCTION_MEDIA_URL,
    IGNORE_APP_MEDIA_DIRS, MEDIA_GENERATORS, DEV_MEDIA_URL,
    GENERATED_MEDIA_NAMES_MODULE)
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from django.utils.http import urlquote
import os
import re

try:
    NAMES = import_module(GENERATED_MEDIA_NAMES_MODULE).NAMES
except (ImportError, AttributeError):
    NAMES = None

_generated_names = {}
_backend_mapping = {}
_refresh_dev_names_lock = threading.Lock()

def memoize(func):
    cache = {}
    @functools.wraps(func)
    def memoized(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return memoized

@memoize
def _load_generators():
    return [load_backend(name)() for name in MEDIA_GENERATORS]

def refresh_dev_names():
    global _generated_names, _backend_mapping

    generated_names = {}
    backend_mapping = {}
    for backend in _load_generators():
        for key, url, hash in backend.get_dev_output_names():
            versioned_url = urlquote(url)
            if hash:
                versioned_url += '?version=' + hash
            generated_names.setdefault(key, [])
            generated_names[key].append(versioned_url)
            backend_mapping[url] = backend

    with _refresh_dev_names_lock:
        _generated_names, _backend_mapping = generated_names, backend_mapping


def get_backend(filename):
    return _backend_mapping[filename]

class _MatchNothing(object):
    def match(self, content):
        return False

def prepare_patterns(patterns, setting_name):
    """Helper function for patter-matching settings."""
    if isinstance(patterns, basestring):
        patterns = (patterns,)
    if not patterns:
        return _MatchNothing()
    # First validate each pattern individually
    for pattern in patterns:
        try:
            re.compile(pattern, re.U)
        except re.error:
            raise ValueError("""Pattern "%s" can't be compiled """
                             "in %s" % (pattern, setting_name))
    # Now return a combined pattern
    return re.compile('^(' + ')$|^('.join(patterns) + ')$', re.U)

def get_production_mapping():
    if NAMES is None:
        raise ImportError('Could not import %s. This '
                          'file is needed for production mode. Please '
                          'run manage.py generatemedia to create it.'
                          % GENERATED_MEDIA_NAMES_MODULE)
    return NAMES

def get_media_mapping():
    if media_settings.MEDIA_DEV_MODE:
        return _generated_names
    return get_production_mapping()

def get_media_url_mapping():
    if media_settings.MEDIA_DEV_MODE:
        base_url = DEV_MEDIA_URL
    else:
        base_url = PRODUCTION_MEDIA_URL

    mapping = {}
    for key, value in get_media_mapping().items():
        if isinstance(value, basestring):
            value = (value,)
        mapping[key] = [base_url + url for url in value]

    return mapping

def media_urls(key, refresh=False):
    if media_settings.MEDIA_DEV_MODE:
        if refresh:
            refresh_dev_names()
        return [DEV_MEDIA_URL + url for url in _generated_names[key]]
    return [PRODUCTION_MEDIA_URL + get_production_mapping()[key]]

def media_url(key, refresh=False):
    urls = media_urls(key, refresh=refresh)
    if len(urls) == 1:
        return urls[0]
    raise ValueError('media_url() only works with URLs that contain exactly '
        'one file. Use media_urls() (or {% include_media %} in templates) instead.')

@memoize
def get_media_dirs():
    media_dirs = GLOBAL_MEDIA_DIRS[:]
    for app in settings.INSTALLED_APPS:
        if app in IGNORE_APP_MEDIA_DIRS:
            continue
        for name in (u'static', u'media'):
            app_root = os.path.dirname(import_module(app).__file__)
            media_dir = os.path.join(app_root, name)
            # Only process dirs that actually exist
            if os.path.isdir(media_dir):
                media_dirs.append(media_dir)
    return media_dirs

def find_file(name, media_dirs=None):
    if media_dirs is None:
        media_dirs = get_media_dirs()
    for root in media_dirs:
        path = os.path.normpath(os.path.join(root, name))
        if os.path.isfile(path):
            return path

def read_text_file(path):
    fp = open(path, 'r')
    output = fp.read()
    fp.close()
    return output.decode('utf8')

@memoize
def load_backend(path):
    module_name, attr_name = path.rsplit('.', 1)
    try:
        mod = import_module(module_name)
    except (ImportError, ValueError), e:
        raise ImproperlyConfigured('Error importing backend module %s: "%s"' % (module_name, e))
    try:
        return getattr(mod, attr_name)
    except AttributeError:
        raise ImproperlyConfigured('Module "%s" does not define a "%s" backend' % (module_name, attr_name))
