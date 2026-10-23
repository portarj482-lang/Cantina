import shutil
import os

def find_tool(name: str) -> str | None:
    t = shutil.which(name)
    if t:
        return t
    home = os.path.expanduser("~")
    for d in [".local/bin", ".cargo/bin", ".foundry/bin"]:
        p = os.path.join(home, d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None
