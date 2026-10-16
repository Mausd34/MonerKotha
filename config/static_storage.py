from whitenoise.storage import CompressedManifestStaticFilesStorage


class CompressedManifestStaticFilesStorageWithFallback(CompressedManifestStaticFilesStorage):
    manifest_strict = False
