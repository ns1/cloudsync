import os
import sys

# Make the SAM app root and the shared layer importable so the handler under
# test resolves (`from src.dns_updates.app import ...` and its `from common
# import ...`) regardless of the directory pytest is invoked from.
SAM_APP_ROOT = os.path.dirname(os.path.dirname(__file__))
for path in (SAM_APP_ROOT, os.path.join(SAM_APP_ROOT, "src", "shared_layer")):
    if path not in sys.path:
        sys.path.insert(0, path)

# Regional boto3 clients (e.g. Secrets Manager) are created at handler import
# time and require a region; set a default so importing handlers is hermetic
# and does not depend on the developer's local AWS configuration.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
