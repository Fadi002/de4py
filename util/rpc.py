from pypresence import Presence
import threading, os, time
from config import config
import ctypes

RPC = None
KILL_THREAD = None

def __RPC_THREAD__():
    global RPC
    global KILL_THREAD
    start = int(time.time())
    while True:
        if KILL_THREAD:
            break
        try:
            RPC.update(
                large_image = "de4py",
                large_text = "De4py",
                details = f"De4py {config.__VERSION__}",
                state ="Python reverse engineering toolkit",
                start = start,
                buttons = [{"label": "Download", "url": "https://de4py.000.pe/"}, {"label": "Github", "url": "https://github.com/Fadi002"}]
            )
            time.sleep(3)
        except:
            break

def start_RPC():
    global RPC
    try:
        RPC = Presence("1190392428247650466")
        RPC.connect()
        threading.Thread(target=__RPC_THREAD__).start()
    except:
        pass

