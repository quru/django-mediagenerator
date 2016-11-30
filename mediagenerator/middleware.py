from .settings import DEV_MEDIA_URL, MEDIA_DEV_MODE
# Only load other dependencies if they're needed
if MEDIA_DEV_MODE:
    import time
    import threading
    from django.http import HttpResponse, Http404
    from django.utils.cache import patch_cache_control
    from django.utils.http import http_date
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    from .utils import get_backend, get_media_dirs, refresh_dev_names 
    _refresh_names_lock = threading.Lock()


TEXT_MIME_TYPES = (
    'application/x-javascript',
    'application/xhtml+xml',
    'application/xml',
)


class MediaMiddleware(object):
    """
    Middleware for serving and browser-side caching of media files.

    This MUST be your *first* entry in MIDDLEWARE_CLASSES. Otherwise, some
    other middleware might add ETags or otherwise manipulate the caching
    headers which would result in the browser doing unnecessary HTTP
    roundtrips for unchanged media.
    """
    MAX_AGE = 60 * 60 * 24 * 365

    def __init__(self):
        if not MEDIA_DEV_MODE:
            return

        # Need an initial refresh to prevent errors on the first request
        refresh_dev_names()

        # Monitor static files for changes
        self.filesystem_event_handler = RefreshingEventHandler()
        self.filesystem_observer = Observer()
        for static_dir in get_media_dirs():
            self.filesystem_observer.schedule(
                self.filesystem_event_handler,
                path=static_dir,
                recursive=True
            )
        self.filesystem_observer.start()

    def __del__(self):
        if hasattr(self, 'filesystem_observer'):
            self.filesystem_observer.stop()
            self.filesystem_observer.join()

    def process_request(self, request):
        if not MEDIA_DEV_MODE:
            return
        if not request.path.startswith(DEV_MEDIA_URL):
            return

        filename = request.path[len(DEV_MEDIA_URL):]
        try:
            backend = get_backend(filename)
        except KeyError:
            raise Http404('The mediagenerator could not find the media file "%s"' % filename)
        with _refresh_names_lock:  # Don't serve while still refreshing
            content, mimetype = backend.get_dev_output(filename)
        if not mimetype:
            mimetype = 'application/octet-stream'
        if isinstance(content, unicode):
            content = content.encode('utf-8')
        if mimetype.startswith('text/') or mimetype in TEXT_MIME_TYPES:
            mimetype += '; charset=utf-8'
        response = HttpResponse(content, content_type=mimetype)
        response['Content-Length'] = len(content)

        # Cache manifest files MUST NEVER be cached or you'll be unable to update
        # your cached app!!!
        if response['Content-Type'] != 'text/cache-manifest' and \
                response.status_code == 200:
            patch_cache_control(response, public=True, max_age=self.MAX_AGE)
            response['Expires'] = http_date(time.time() + self.MAX_AGE)
        return response


class RefreshingEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        with _refresh_names_lock:
            refresh_dev_names()
