# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from pypresence import Presence
import threading
import time
import logging
from de4py.config.config import settings

RPC = None
KILL_THREAD = False


def _rpc_loop():
    global RPC
    global KILL_THREAD
    start = int(time.time())
    while not KILL_THREAD:
        try:
            RPC.update(
                large_image="de4py",
                large_text="De4py",
                details=f"De4py {settings.version}",
                state="Python reverse engineering toolkit",
                start=start,
                buttons=[
                    {"label": "Download", "url": "https://de4py.000.pe/"},
                    {"label": "Github", "url": "https://github.com/Fadi002"},
                ],
            )
            time.sleep(3)
        except Exception as e:
            logging.debug(f"RPC update failed: {e}")
            break


def start_RPC():
    global RPC
    try:
        RPC = Presence("1190392428247650466")
        RPC.connect()
        t = threading.Thread(target=_rpc_loop, daemon=True)
        t.start()
    except Exception as e:
        logging.debug(f"RPC connection failed: {e}")

