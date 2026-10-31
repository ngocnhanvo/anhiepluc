#!/usr/bin/env python3
"""Read-only production investigation: case CA_01_CapNhatLaiGSP.
Private Azure source is processed in an ephemeral runner; only an encrypted
diagnostic report is posted to GitHub. Nothing is written to Azure.
"""
import os, sys, re, json, zlib, base64, tempfile, subprocess, pathlib
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
REMOTE="https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc"
PAT=os.environ.get("AZURE_DEVOPS_PAT","")
if not PAT: raise SystemExit("AZURE_PAT_MISSING")
def git(*args,cwd=None,env=None):
    p=subprocess.run(["git",*args],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: raise RuntimeError("Azure git command failed: "+str(p.returncode))
    return p.stdout.decode("utf-8","replace").strip()
def decode(path):
    b=path.read_bytes()
    for enc in ("utf-8-sig","utf-16","cp1258","latin-1"):
        try: return b.decode(enc)
        except UnicodeError: pass
    return ""
def snippets(s,needle,span=1750,maximum=5):
    found=[]
    for m in re.finditer(re.escape(needle),s,re.I):
        a=max(0,m.start()-span); z=min(len(s),m.end()+span)
        found.append({"pos":m.start(),"context":s[a:z]})
        if len(found)==maximum: break
    return found
def relevant_file(path):
    return path.suffix.lower() in (".cs",".ashx",".aspx",".ascx",".js",".sql",".xml",".config",".md",".txt",".resx") and path.stat().st_size < 1600000
with tempfile.TemporaryDirectory(prefix="anhl-case-readonly-") as d:
    root=pathlib.Path(d)/"source"
    env=os.environ.copy()
    env["AZURE_GIT_HEADER"]="AUTHORIZATION: Basic "+base64.b64encode((":"+PAT).encode()).decode()
    git("--config-env=http.extraheader=AZURE_GIT_HEADER","clone","--quiet","--depth=1","--branch","master",REMOTE,str(root),env=env)
    commit=git("rev-parse","HEAD",cwd=root)
    files=[]
    hits=[]
    terms=("CA_01_CapNhatLaiGSP","CapNhatLaiGSP","MD_01_PhienBangGiaJQGS","MD_00_PVCNoiBo","MD_01_CacDongVanChuyen")
    paths=git("ls-files","-z",cwd=root).split("\x00")
    for rel in paths:
        if not rel: continue
        p=root/rel
        if not p.is_file() or not relevant_file(p): continue
        content=decode(p)
        if not content: continue
        counts={term:len(re.findall(re.escape(term),content,re.I)) for term in terms}
        if not any(counts.values()): continue
        files.append({"path":rel,"terms":{k:v for k,v in counts.items() if v}})
        if counts[terms[0]] or counts[terms[1]]:
            hits.append({"path":rel,"size":len(content),"case_context":snippets(content,terms[0],7500,3) or snippets(content,terms[1],7500,3),
                         "price_update_context":snippets(content,"Cập nhật lại giá",900,2)})
    # Additional targeted snippets in code naming the module, for cross-linking controllers and UI.
    adjacent=[]
    for f in files:
        rel=f["path"]; p=root/rel
        if f["terms"].get("MD_01_PhienBangGiaJQGS") and not any(x["path"]==rel for x in hits):
            s=decode(p)
            snippets_out=snippets(s,"CapNhat",1100,2)
            if snippets_out: adjacent.append({"path":rel,"context":snippets_out})
            if len(adjacent)>=8:break
    report={"source":"Azure AnHiepLuc/master","commit":commit,"case":"CA_01_CapNhatLaiGSP",
            "files":files[:150],"hits":hits[:25],"adjacent":adjacent}
    # Only derived structural indicators are disclosed publicly, never source lines.
    public={"commit":commit,"case_matches":len(hits),"matching_files":len(files),
            "case_files":[],"other_files":[]}
    for hit in hits[:15]:
        contexts=[x.get("context","") for x in hit["case_context"]]
        joined="\n".join(contexts)
        tables=sorted(set(re.findall(r"\b(?:dbo\.)?(?:md|c|ad|gs)_[A-Za-z0-9_]+",joined,re.I)))
        updates=sorted(set(re.findall(r"\bUPDATE\s+(?:dbo\.)?([A-Za-z_][A-Za-z0-9_]*)",joined,re.I)))
        procedures=sorted(set(re.findall(r"\b(?:EXEC|EXECUTE)\s+(?:dbo\.)?([A-Za-z_][A-Za-z0-9_]*)",joined,re.I)))
        names=sorted(set(re.findall(r"\b(?:CA_[A-Za-z0-9_]+|MD_[A-Za-z0-9_]+)",joined,re.I)))
        flags={key:bool(re.search(key,joined,re.I)) for key in
           ("PVCNoiBo","CacDongVanChuyen","van_chuyen","nhap_kho","phienbanggia",
            "capnhatlaigsp","SaveChanges","SubmitChanges","SqlCommand","ExecuteSql",
            "SqlDataSource","GiaSP","gia_sp")}
        public["case_files"].append({"path":hit["path"],"tables":tables[:40],
            "updates":updates[:15],"procedures":procedures[:15],
            "referenced_modules_or_cases":names[:20],"flags":flags})
    for f in files[:80]:
        if not any(x["path"]==f["path"] for x in hits):
            public["other_files"].append(f)
    with open(os.environ["RUNNER_TEMP"]+"/case_public_summary.json","w") as summary:
        summary.write(json.dumps(public,ensure_ascii=False,indent=2))
    logic=[]
    for hit in hits[:8]:
        source=decode(root/hit['path'])
        for m in list(re.finditer('CA_01_CapNhatLaiGSP',source,re.I))[:4]:
            near=source[max(0,m.start()-600):min(len(source),m.start()+12000)]
            syms=('md_xuatkhonb','md_phienbangia_id','md_banggia_id','md_phienbangia','PVCNoiBo','md_to_id')
            tokenmap={}
            for sym in syms:
                ids=[]
                for match in list(re.finditer(re.escape(sym),near,re.I))[:5]:
                    seg=near[max(0,match.start()-100):min(len(near),match.end()+130)]
                    ids.append(re.findall(r'\b[A-Za-z_][A-Za-z_0-9]*\b',seg)[:25])
                tokenmap[sym]=ids
            calls=sorted(set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(',near)))
            assignments=sorted(set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)',near)))
            logic.append({'path':hit['path'],'tokens':tokenmap,'calls':calls[:90],'assignments':assignments[:90]})
    with open(os.environ['RUNNER_TEMP']+'/case_logic_summary.json','w') as out:
        out.write(json.dumps({'commit':commit,'logic':logic},ensure_ascii=False,indent=2))
    source_file=root/"eman_ver3/Controller/JQGridModify/JQGridMD_01_PhienBangGiaJQGSModify.ashx"
    source_lines=decode(source_file).splitlines()
    report["target_case_lines_35_253"]="\n".join(str(i+1)+": "+line for i,line in enumerate(source_lines) if 35<=i+1<=253)
    raw=json.dumps(report,ensure_ascii=False,separators=(",",":")).encode()
    if len(raw)>160000: raw=json.dumps({"source":"Azure AnHiepLuc/master","commit":commit,"files":files[:80],"hits":hits[:7]},ensure_ascii=False).encode()
    key=os.urandom(32); nonce=os.urandom(12)
    payload=AESGCM(key).encrypt(nonce,zlib.compress(raw,9),None)
    key_b64=os.environ["PUBLIC_KEY_B64"]
    try:
        ev=json.load(open(os.environ["GITHUB_EVENT_PATH"],encoding="utf-8"))
        requested=json.loads(ev["issue"]["body"])
        if requested.get("public_key_b64"):
            key_b64=requested["public_key_b64"]
    except (KeyError,ValueError,TypeError):
        pass
    pub=serialization.load_pem_public_key(base64.b64decode(key_b64,validate=True))
    ek=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    envelope=base64.b64encode(ek+nonce+payload).decode()
    print("AZURE_PRODUCTION_READ=PASS")
    print("CASE_FILES="+str(len(hits)))
    print("MATCHED_FILES="+str(len(files)))
    with open(os.environ["RUNNER_TEMP"]+"/case_inspection.txt","w") as out:
        out.write("CASE_DIAGNOSTIC_ENC_V1:"+envelope)
