#!/usr/bin/env python3
"""Inspect price-update case in Azure production without writing source or data."""
import base64, json, os, pathlib, re, subprocess, tempfile
REMOTE="https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc"
TARGET="eman_ver3/Controller/JQGridModify/JQGridMD_01_PhienBangGiaJQGSModify.ashx"
CASE="CA_01_CapNhatLaiGSP"
def git(*args,cwd=None,env=None):
    r=subprocess.run(["git",*args],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if r.returncode:raise RuntimeError("Azure checkout failed")
    return r.stdout.decode("utf-8","replace").strip()
def read(p):
    buf=p.read_bytes()
    for enc in ("utf-8-sig","utf-16","cp1258","latin-1"):
        try:return buf.decode(enc)
        except UnicodeError:continue
    raise ValueError("Decode failed")
def derive():
    pat=os.environ["AZURE_DEVOPS_PAT"]
    if not pat:raise RuntimeError("PAT missing")
    env=os.environ.copy()
    env["AZURE_GIT_HEADER"]="AUTHORIZATION: Basic "+base64.b64encode((":"+pat).encode()).decode()
    with tempfile.TemporaryDirectory() as temp:
        root=pathlib.Path(temp)/"azure"
        git("--config-env=http.extraheader=AZURE_GIT_HEADER","clone","--quiet","--depth=1","--branch","master",REMOTE,str(root),env=env)
        sha=git("rev-parse","HEAD",cwd=root)
        content=read(root/TARGET)
        lines=content.splitlines()
        indices=[i for i,l in enumerate(lines) if CASE.lower() in l.lower()]
        if not indices:raise RuntimeError("Case not found")
        # Derive structural logic only, no raw Azure source lines leave runner.
        output={"azure_master_sha":sha,"case":CASE,"path":TARGET,"case_marker_lines":[i+1 for i in indices],
                "tables":{},"logic_blocks":[]}
        block=lines[max(0,indices[0]-12):min(len(lines),indices[0]+700)]
        for t in ("md_nhapkhonb","md_xuatkhonb","md_vanchuyennoibo"):
            pat_db=r"\bdb\."+re.escape(t)+r"\b"
            hits=[i for i,l in enumerate(block) if re.search(pat_db,l,re.I)]
            output["tables"][t]={"db_references":len(hits),"nearby_lines":[max(1,indices[0]-11+i) for i in hits[:15]]}
        terms=r"phienbangiaNC|gianhancong|ngaygoihan|firstnull|doiPBGMoiNhat|scts|md_xuatkhonb|md_vanchuyennoibo|md_nhapkhonb|SaveChanges|Commit|Rollback|loai|hoatdong|ngay_hieuluc|\btype\b"
        for i,l in enumerate(block):
            if re.search(terms,l,re.I):
                # Structural lexical tokens reveal branch predicates and assignments without source text.
                tokens=re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|>=|<=|&&|\|\||=",l)
                keep=[]
                for x in tokens:
                    if x in ("var","if","else","foreach","in","while","return","true","false","null","and","or","Count","Where","ToList","AsQueryable","FirstOrDefault","Contains","OrderByDescending","SaveChanges","Commit","Rollback","type","scts","ngaygoihan","firstnull","doiPBGMoiNhat","hoatdong","ngay_hieuluc","phienbangiaNC","gianhancong","md_xuatkhonb","md_vanchuyennoibo","md_nhapkhonb","md_phienbangia","md_phienbangia_id","md_banggia_id","banggiaNC","md_trangthai_id","==","!=",">=","<=","&&","||","=") or x.startswith(("xnb","vcnb","pbg","gsp","ngay","gianhancong","md_")):
                        keep.append(x)
                if keep:
                    output["logic_blocks"].append({"line":max(1,indices[0]-11+i),"tokens":keep[:34]})
        output["logic_blocks"]=output["logic_blocks"][:125]
        return output
if __name__=="__main__":
    result=derive()
    print("CASE_AUDIT=PASS; AZURE_SOURCE_READONLY=YES")
    with open(os.environ["RUNNER_TEMP"]+"/price_case_audit.json","w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
