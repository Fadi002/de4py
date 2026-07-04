# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import threading
import time
import logging
from de4py.config.config import settings

_RPC = None
_rpc_lock = threading.Lock()
_stop_event = threading.Event()

KILL_THREAD = False


def _rpc_loop():
    start = int(time.time())
    details = f"De4py {settings.version}"
    while not _stop_event.is_set():
        try:
            with _rpc_lock:
                rpc = _RPC
            if rpc is None:
                break
            rpc.update(
                large_image="de4py",
                large_text="De4py",
                details=details,
                state="Python reverse engineering toolkit",
                start=start,
                buttons=[
                    {"label": "Download", "url": "https://de4py.000.pe/"},
                    {"label": "Github", "url": "https://github.com/Fadi002"},
                ],
            )
            _stop_event.wait(3)
        except Exception as e:
            logging.debug(f"RPC update failed: {e}")
            break


def start_rpc():
    global _RPC, KILL_THREAD
    with _rpc_lock:
        if _RPC is not None:
            return
    KILL_THREAD = False
    _stop_event.clear()
    try:
        from pypresence import Presence
        rpc = Presence("1190392428247650466")
        rpc.connect()
        with _rpc_lock:
            _RPC = rpc
        t = threading.Thread(target=_rpc_loop, daemon=True)
        t.start()
    except Exception as e:
        logging.debug(f"RPC connection failed: {e}")


def stop_rpc():
    global _RPC, KILL_THREAD
    KILL_THREAD = True
    _stop_event.set()
    with _rpc_lock:
        rpc = _RPC
        _RPC = None
    if rpc is not None:
        try:
            rpc.close()
        except Exception:
            pass
