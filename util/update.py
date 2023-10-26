import logging
import requests
from config.config import __VERSION_URL__, __VERSION__
def check_update():
    logging.info("Checking for updates")
    if requests.get(__VERSION_URL__,timeout=60).text != __VERSION__:
        return False
    else:
        return True

