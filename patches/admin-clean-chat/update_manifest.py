from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
PATH="mods/LuneryaAdmin-1.21.1-3.0.0.jar"
URL="https://github.com/AaWell59220/Lunerya-Updates/releases/download/lunerya-launcher-v1.0.42-assets/LuneryaAdmin-1.21.1-3.0.0.jar"
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--sha256",required=True)
    p.add_argument("--size",required=True,type=int)
    a=p.parse_args()
    data=json.loads(a.manifest.read_text(encoding="utf-8"))
    matches=[i for i,e in enumerate(data.get("files",[])) if str(e.get("path","")).lower().startswith("mods/luneryaadmin-")]
    if len(matches)!=1: raise SystemExit("Manifest LuneryaAdmin ambigu.")
    data["files"][matches[0]]={"path":PATH,"url":URL,"sha256":a.sha256.lower(),"size":a.size,"required":True}
    data["generatedAt"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    a.manifest.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
if __name__=="__main__": main()
