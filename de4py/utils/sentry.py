import sentry_sdk
from contextlib import contextmanager
import logging

ENABLED = True

def init():
    if not ENABLED:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn="https://e3abec75d2b4050308637e9354a03fd0@o4510755728982016.ingest.de.sentry.io/4510755731013712",
            send_default_pii=True,
            enable_logs=True,
            traces_sample_rate=0.3,
            profile_session_sample_rate=0.15
        )
    except Exception as e:
        import logging
        logging.warning(f"Sentry initialization failed: {e}")

@contextmanager
def transaction(name, op):
    if not ENABLED:
        yield None
        return
    with sentry_sdk.start_transaction(name=name, op=op) as t:
        yield t

@contextmanager
def span(op, description=None):
    if not ENABLED:
        yield None
        return
    with sentry_sdk.start_span(op=op, description=description) as s:
        yield s

def breadcrumb(msg, category="app", level="info", **data):
    if ENABLED:
        sentry_sdk.add_breadcrumb(
            message=msg,
            category=category,
            level=level,
            data=data
        )

def set_user_context(user_id=None, email=None, username=None):
    if ENABLED:
        sentry_sdk.set_user({"id": user_id, "email": email, "username": username})

def set_extra_context(key, value):
    if ENABLED:
        sentry_sdk.set_context(key, value)
