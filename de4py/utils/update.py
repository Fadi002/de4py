import logging
import requests
from de4py.config.config import settings
def check_update():
    logging.info("Checking for updates")
    if requests.get(settings.version_url,timeout=60).text != settings.version:
        return False
    else:
        return True

