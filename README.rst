Improve your user experience with fast page loads by combining,
compressing, and versioning your JavaScript & CSS files and images.
django-mediagenerator_ eliminates unnecessary HTTP requests
and maximizes cache usage.

Supports App Engine, Sass_, HTML5 offline manifests,  Jinja2_,
Python/pyjs_, CoffeeScript_, and much more. Visit the
`project site`_ for more information.

Quru fork (v1.12+)
------------------
This fork adds a modified version of pull request #11 to v1.11,
to fix performance problems when ``MEDIA_DEV_MODE`` is ``True``.

Instead of walking the file system on every request, this version uses the
Watchdog_ package to monitor the media directories, and only walks the file
system again when a change is known to have been made.

In addition for ``COPY_MEDIA_FILETYPES`` (defaults to images, icons, fonts),
the file modification time is used as a hash instead of reading the file contents.

v1.13 looks for a ``TESTING`` setting when ``MEDIA_DEV_MODE`` is ``True``,
and disables the monitoring of media files when it is set.

See `CHANGELOG.rst`_ for the complete changelog.

.. _django-mediagenerator: http://www.allbuttonspressed.com/projects/django-mediagenerator
.. _project site: django-mediagenerator_
.. _Sass: http://sass-lang.com/
.. _pyjs: http://pyjs.org/
.. _CoffeeScript: http://coffeescript.org/
.. _Jinja2: http://jinja.pocoo.org/
.. _Watchdog: https://github.com/gorakhargosh/watchdog/
.. _CHANGELOG.rst: https://github.com/quru/django-mediagenerator/blob/master/CHANGELOG.rst
