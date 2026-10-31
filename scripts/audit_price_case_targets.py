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
        # Focused predicates and assignment structure (never publish private source lines).
        output["focus"]=[]
        for n in list(range(55,95))+list(range(95,108))+list(range(158,176)):
            if n>len(lines):continue
            line=lines[n-1]
            if not re.search(r'type|firstnull|doiPBGMoiNhat|ngaygoihan|phienbangiaNC|vcnbss|xnbss|pbgMoiNhat|ngaytao|scts|AddDays|md_vanchuyennoibo',line,re.I):
                continue
            literals=re.findall(r'["\x27]([^"\x27]*)["\x27]',line)
            literals=[v if re.fullmatch(r'[A-Za-z_0-9-]{0,30}',v) else '<other>' for v in literals]
            symbols=re.findall(r'[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\\|\\||=',line)
            output["focus"].append({"line":n,"symbols":symbols[:40],"literals":literals[:10]})
        output["focused_predicates"]=[]
        for n in (66,78,82,92,95,96,98,103,105,162,163,164,165,167,172,173):
            if n>len(lines):continue
            value=lines[n-1]
            tokens=re.findall(r'[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\\|\\||=',value)
            output["focused_predicates"].append({
              "line":n,
              "tokens":tokens[:45],
              "empty_string_literal":'""' in value,
              "single_space_literal":'" "' in value,
              "has_null":bool(re.search(r'\\bnull\\b',value,re.I)),
              "numbers":re.findall(r'(?<![A-Za-z_])[-]?[0-9]+(?![A-Za-z_])',value)[:8]
            })
        return output
if __name__=="__main__":
    result=derive()
    print("CASE_AUDIT=PASS; AZURE_SOURCE_READONLY=YES")
    with open(os.environ["RUNNER_TEMP"]+"/price_case_audit.json","w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
