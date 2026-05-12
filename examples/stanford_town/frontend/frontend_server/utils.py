# MetaGPT vendor patch: original GA file imported S3 backends from
# django-storages-redux for production deployment. That package is
# Django-2.x only and is unused in the local MetaGPT integration, so
# the imports have been removed to keep the project installable on
# Django 4.x without pulling in unmaintained dependencies. Restore the
# original two-line module if you need S3 static/media uploads.
