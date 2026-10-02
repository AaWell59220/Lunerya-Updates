from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, tempfile, zipfile
from pathlib import Path

BASE_SHA256="39256ce059eb551fe83b2a300ff979ff9419367b7a8d5b6e0c6a837008e044b0"
BASE_SIZE=281273426
PATCH_SHA256="a1d10688a7933eefcdd24a73de0b6fab6482877ddc1d6cb94f058c92f5732f39"
REQUIRED={
"fr/lunerya/adminmod/LuneryaShopRewards.class",
"fr/lunerya/adminmod/LuneryaChatCleaner.class",
}

def sha256_file(path: Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--base",required=True,type=Path)
    p.add_argument("--patch",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    a.base=a.base.resolve(); a.patch=a.patch.resolve(); a.out=a.out.resolve()
    if a.base.stat().st_size!=BASE_SIZE or sha256_file(a.base)!=BASE_SHA256:
        raise SystemExit("Refus: base launcher inattendue.")
    if sha256_file(a.patch)!=PATCH_SHA256:
        raise SystemExit("Refus: patch clean-chat corrompu.")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(a.base,a.out)
    with zipfile.ZipFile(a.patch) as pz:
        meta=json.loads(pz.read("patch-meta.json").decode())
        names=set(pz.namelist())-{"patch-meta.json"}
        if names!=REQUIRED: raise SystemExit("Liste patch inattendue.")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name in REQUIRED:
                data=pz.read(name); exp=meta["entries"][name]
                if len(data)!=exp["size"] or hashlib.sha256(data).hexdigest()!=exp["sha256"]:
                    raise SystemExit("Classe patch invalide: "+name)
                f=root/name; f.parent.mkdir(parents=True,exist_ok=True); f.write_bytes(data)
            subprocess.run(["zip","-q","-X",str(a.out)]+sorted(REQUIRED),cwd=root,check=True)
    with zipfile.ZipFile(a.out) as z:
        if z.testzip() is not None: raise SystemExit("JAR corrompu.")
        names=z.namelist()
        if len(names)!=len(set(names)): raise SystemExit("Entrees dupliquees.")
        for name in REQUIRED:
            data=z.read(name); exp=meta["entries"][name]
            if len(data)!=exp["size"] or hashlib.sha256(data).hexdigest()!=exp["sha256"]:
                raise SystemExit("Verification finale echouee: "+name)
    print("FINAL_SHA256="+sha256_file(a.out))
    print("FINAL_SIZE="+str(a.out.stat().st_size))
if __name__=="__main__": main()
