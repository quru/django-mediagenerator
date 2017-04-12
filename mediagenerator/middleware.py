from .settings import DEV_MEDIA_URL, MEDIA_DEV_MODE, UNIT_TESTING

TEXT_MIME_TYPES = (
    'application/x-javascript',
    'application/xhtml+xml',
    'application/xml',
)

# Only load other dependencies if they're needed
if MEDIA_DEV_MODE:
    import atexit
    import time
    import threading
    from django.http import HttpResponse, Http404
    from django.utils.cache import patch_cache_control
    from django.utils.http import http_date
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    from .utils import get_backend, get_media_dirs, refresh_dev_names

    _refresh_names_lock = threading.Lock()
    _middleware_instance = None

    @atexit.register
    def cleanup_middleware():
        # v1.14 remove observers when restarting in dev mode
        global _middleware_instance
        if _middleware_instance:
            _middleware_instance.cleanup()

    class RefreshingEventHandler(FileSystemEventHandler):
        def on_any_event(self, event):
            with _refresh_names_lock:
                refresh_dev_names()


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
        self._observer_started = False
        self._cleaned_up = False

        # Go no further if not in dev mode
        if not MEDIA_DEV_MODE:
            return

        # v1.14 register ourselves for cleanup on exit
        global _middleware_instance
        _middleware_instance = self

        # Need an initial refresh to prevent errors on the first request
        refresh_dev_names()

        # Monitor static files for changes (v1.13 - when not unit testing)
        if not UNIT_TESTING:
            self.filesystem_event_handler = RefreshingEventHandler()
            self.filesystem_observer = Observer()
            for static_dir in get_media_dirs():
                self.filesystem_observer.schedule(
                    self.filesystem_event_handler,
                    path=static_dir,
                    recursive=True
                )
            self.filesystem_observer.start()
            self._observer_started = True

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        if not self._cleaned_up:
            if hasattr(self, 'filesystem_observer'):
                self.filesystem_observer.unschedule_all()
                # Only try to stop if __init__ ran a successful start()
                if self._observer_started:
                    self.filesystem_observer.stop()
                    self.filesystem_observer.join()
        self._cleaned_up = True

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
