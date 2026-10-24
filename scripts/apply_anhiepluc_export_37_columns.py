#!/usr/bin/env python3
"""AnHiepLuc 37-column product export: correct DHD and SOANTHAO only.

Clones production Azure source in an ephemeral GitHub Actions runner.
Does not publish private source to GitHub or stdout.
"""
import base64
import codecs
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

REMOTE = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc"
API = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_apis/git/repositories/AnHiepLuc"
BRANCH = "ai/anhiepluc-excel-37-cot-xuong-to-20261025"
PLAN = "plans/AnHiepLuc_Product_Export_41_Column_Alignment_PLAN.md"
ROOT = "eman_ver3/Controller/JQGridModify/"
ST = ROOT + "JQGridMD_00_DSHangHoa_SOANTHAOModify.ashx"
DHD = ROOT + "JQGridMD_00_DSHangHoaVGModify.ashx"
EXPECTED_LAST = ("Xưởng SX", "Tổ SX", "Thuế", "Bán TP")

def git(*args, cwd=None, env=None):
    p = subprocess.run(["git",*args], cwd=cwd, env=env, capture_output=True)
    if p.returncode:
        raise RuntimeError("Git operation failed (details suppressed)")
    return p.stdout.decode("utf-8","replace").strip()

def read_file(path):
    data=path.read_bytes()
    if data.startswith(codecs.BOM_UTF16_LE): enc="utf-16"
    elif data.startswith(codecs.BOM_UTF8): enc="utf-8-sig"
    elif data[:100].count(b"\x00")>20: enc="utf-16-le"
    else:
        try: data.decode("utf-8"); enc="utf-8"
        except UnicodeDecodeError: enc="cp1258"
    content=data.decode(enc)
    end="\r\n" if content.count("\r\n")>=content.count("\n")/2 else "\n"
    return content.replace("\r\n","\n"),enc,end

def write_file(path, text, enc, end):
    path.write_bytes(text.replace("\r\n","\n").replace("\n",end).encode(enc))

def excel_col(index):
    result=""
    while index>=0:
        result=chr(65+index%26)+result
        index=index//26-1
    return result

def plan_headers():
    text=pathlib.Path(PLAN).read_text("utf-8")
    rows=[]
    for line in text.splitlines():
        m=re.match(r"^\| ([A-Z]{1,2}) \| ([^|]+) \|",line)
        if m: rows.append((m.group(1),m.group(2).strip()))
    if len(rows)!=37: raise RuntimeError("Plan header count is not 37")
    if any(col!=excel_col(i) for i,(col,_) in enumerate(rows)):
        raise RuntimeError("Plan header sequence invalid")
    headers=[h for _,h in rows]
    if tuple(headers[-4:])!=EXPECTED_LAST:
        raise RuntimeError("Plan workshop/team/tax order invalid")
    for name in ("Mã thô","vd","vn","vl","ghichu_vachngan"):
        if name in headers: raise RuntimeError("Removed column remains in plan")
    return headers

def patch_export(original,prefix,expected_headers):
    h_pat=r"(private static readonly string\[\] "+prefix+r"ExportHeaders = new string\[\] \{)(.*?)(\};)"
    h_match=re.search(h_pat,original,re.S)
    if not h_match: raise RuntimeError(prefix+" headers not found")
    old_headers=re.findall(r'"([^"]+)"',h_match.group(2))
    if len(old_headers)!=37: raise RuntimeError(prefix+" prior headers not 37")
    already=(old_headers==expected_headers)
    if not already and (old_headers[1]!="Mã thô" or "Tổ SX" in old_headers):
        raise RuntimeError(prefix+" source headers drifted")
    if already:
        # Subsequent checks cover SQL/width. Never rerun a partial patch.
        sql_info=read_export_sql(original,prefix)
        check_export_sql(sql_info[1],expected_headers,prefix)
        return original,False
    widths_pat=r"(private static readonly int\[\] "+prefix+r"ExportWidths = new int\[\] \{)([^{}]*)(\};)"
    width_match=re.search(widths_pat,original,re.S)
    if not width_match: raise RuntimeError(prefix+" widths absent")
    width_values=[int(x) for x in re.findall(r"\d+",width_match.group(2))]
    if len(width_values)!=37: raise RuntimeError(prefix+" width count invalid")
    named_widths=dict(zip(old_headers,width_values))
    named_widths["Tổ SX"]=17
    new_widths=[named_widths[h] for h in expected_headers]
    new_headers_text="\n"+''.join('            "'+h+'"'+("," if i<len(expected_headers)-1 else "")+"\n" for i,h in enumerate(expected_headers))+"    "
    out=original[:h_match.start(2)]+new_headers_text+original[h_match.end(2):]
    width_match=re.search(widths_pat,out,re.S)
    out=out[:width_match.start(2)]+" "+", ".join(map(str,new_widths))+" "+out[width_match.end(2):]
    _,sql=read_export_sql(out,prefix)
    if "maTho.ma_tho" not in sql: raise RuntimeError(prefix+" raw code SQL absent")
    # Drop raw-code projection and related BOM correlates completely (no longer used).
    lines=sql.split("\n")
    keep=[line for line in lines if "maTho.ma_tho" not in line]
    sql="\n".join(keep)
    start=sql.find("-- Phiên bản BOM")
    end=sql.find("-- Không JOIN thẳng",start)
    if start<0 or end<0: raise RuntimeError(prefix+" BOM block anchors absent")
    sql=sql[:start]+sql[end:]
    # Replace Anco1 department-based 'Xưởng SX' with actual AnHiepLuc production workshop and team.
    workshop=r"(?m)^[ \t]*pb\.ten_phongban[ \t]+AS \[Xưởng SX\],[^\n]*"
    sql,n=re.subn(workshop,"    px.ten_phanxuong                                AS [Xưởng SX],\n    pxt.ten_to                                      AS [Tổ SX],",sql)
    if n!=1: raise RuntimeError(prefix+" workshop projection not found")
    dep=r"LEFT JOIN dbo\.ad_department AS pb\s+ON pb\.md_phongban_id = sp\.phongbanId"
    replace=("LEFT JOIN dbo.md_phanxuong AS px\n"
             "    ON px.md_phanxuong_id = sp.md_phanxuong_id\n"
             "LEFT JOIN dbo.md_phanxuong_to AS pxt\n"
             "    ON pxt.md_to_id = sp.md_to_id")
    sql,n=re.subn(dep,lambda _:replace,sql,count=1)
    if n!=1: raise RuntimeError(prefix+" workshop join not found")
    # Drop obsolete Excel-column comments inherited from Anco1 so they cannot become misleading.
    sql=re.sub(r"(?m)([ \t]+)-- [A-Z]{1,2}(?=\s*$)","",sql)
    check_export_sql(sql,expected_headers,prefix)
    match,_=read_export_sql(out,prefix)
    out=out[:match.start(2)]+sql+out[match.end(2):]
    if out==original: raise RuntimeError("Unexpected no-op")
    return out,True

def read_export_sql(text,prefix):
    p=r'(private const string '+prefix+r'ExportSql = @")(.*?)(";)'
    m=re.search(p,text,re.S)
    if not m: raise RuntimeError(prefix+" SQL block absent")
    return m,m.group(2)

def check_export_sql(sql,headers,prefix):
    split=sql.split("FROM dbo.md_sanpham AS sp",1)
    if len(split)!=2: raise RuntimeError("Missing FROM md_sanpham")
    projected=re.findall(r"\bAS \[([^\]]+)\]",split[0])
    if projected!=headers:
        raise RuntimeError(prefix+" SQL projection does not match 37 required columns")
    must=[
        "px.ten_phanxuong", "pxt.ten_to",
        "LEFT JOIN dbo.md_phanxuong AS px",
        "ON px.md_phanxuong_id = sp.md_phanxuong_id",
        "LEFT JOIN dbo.md_phanxuong_to AS pxt",
        "ON pxt.md_to_id = sp.md_to_id",
        "/*EXPORT_FILTER_IDS*/",
        "OUTER APPLY ("
    ]
    if any(v not in sql for v in must):
        raise RuntimeError(prefix+" missing required join/batching condition")
    if "maTho." in sql or "AS maTho" in sql or "md_sanpham_bom" in sql or "dbo.ad_department" in sql:
        raise RuntimeError(prefix+" obsolete Anco1 export mapping still present")
    state="N'DHD'" if prefix=="Dhd" else "N'SOANTHAO'"
    if "sp.trangthai = "+state not in sql:
        raise RuntimeError(prefix+" product state filter incorrect")
    if prefix=="Dhd":
        for v in ("WHERE sp.vattu = 0","(sp.sanpham = 1 OR sp.ban_thanhpham = 1)"):
            if v not in sql: raise RuntimeError("DHD product eligibility missing")
    if "md_donggoisanpham_ancotrading" not in sql or "md_donggoi_ancotrading" not in sql:
        raise RuntimeError(prefix+" packaging lookup missing")
    return True

def verify_source(root,headers):
    for path,prefix in ((ST,"Draft"),(DHD,"Dhd")):
        source=read_file(root/path)[0]
        h=re.search(r"private static readonly string\[\] "+prefix+r"ExportHeaders = new string\[\] \{(.*?)\};",source,re.S)
        w=re.search(r"private static readonly int\[\] "+prefix+r"ExportWidths = new int\[\] \{(.*?)\};",source,re.S)
        if not h or not w: raise RuntimeError(prefix+" headers/widths missing")
        actual=re.findall(r'"([^"]+)"',h.group(1))
        widths=[int(v) for v in re.findall(r"\d+",w.group(1))]
        if actual!=headers or len(widths)!=37:
            raise RuntimeError(prefix+" workbook output 37-column mismatch")
        check_export_sql(read_export_sql(source,prefix)[1],headers,prefix)
        if "new HSSFWorkbook()" not in source or "sheet.CreateRow(0)" not in source:
            raise RuntimeError(prefix+" XLS generation missing")
        if "ExportWorkbook" not in source or "/*EXPORT_FILTER_IDS*/" not in source:
            raise RuntimeError(prefix+" POST export missing")
        case="CA_01_ExportHHVG" if prefix=="Dhd" else "CA01ExportHHVG_MD00DSHangHoaSOANTHAO"
        if 'case "'+case+'":' not in source:
            raise RuntimeError(prefix+" case route absent")
        if "Security.PhanQuyen_ChucNang" not in source:
            raise RuntimeError(prefix+" permissions absent")
    print("VALIDATION=PASS; MODULES=SOANTHAO,DHD; HEADER_COUNT=37; WORKSHOP_TEAM=CORRECT")

def api_call(path,pat,method="GET",body=None):
    auth="Basic "+base64.b64encode((":"+pat).encode()).decode()
    payload=None if body is None else json.dumps(body).encode("utf-8")
    headers={"Authorization":auth,"Accept":"application/json"}
    if payload is not None: headers["Content-Type"]="application/json"
    req=urllib.request.Request(API+path,headers=headers,method=method,data=payload)
    try:
        with urllib.request.urlopen(req,timeout=45) as x:
            return json.load(x)
    except urllib.error.HTTPError as err:
        raise RuntimeError("Azure API failure HTTP "+str(err.code)) from None

def main():
    mode=os.environ.get("EXPORT_MODE","preview")
    if mode not in ("preview","apply"): raise RuntimeError("Invalid export mode")
    pat=os.environ.get("AZURE_DEVOPS_PAT","")
    if not pat: raise RuntimeError("Missing Azure PAT")
    headers=plan_headers()
    env=os.environ.copy()
    env["AZURE_GIT_HEADER"]="AUTHORIZATION: Basic "+base64.b64encode((":"+pat).encode()).decode()
    with tempfile.TemporaryDirectory(prefix="anhiepluc-export-37-") as tmp:
        root=pathlib.Path(tmp)/"azure"
        git("--config-env=http.extraheader=AZURE_GIT_HEADER","clone","--quiet","--depth=1",REMOTE,str(root),env=env)
        base=git("rev-parse","HEAD",cwd=root)
        if git("branch","--show-current",cwd=root)!="master":
            raise RuntimeError("Target source is not Azure master")
        print("AZURE_BASE_SHA="+base)
        changed=[]
        for path,prefix in ((ST,"Draft"),(DHD,"Dhd")):
            f=root/path
            if not f.is_file(): raise RuntimeError("Missing Azure handler "+path)
            source,enc,end=read_file(f)
            revised,did_change=patch_export(source,prefix,headers)
            if did_change:
                write_file(f,revised,enc,end)
                changed.append(path)
        verify_source(root,headers)
        expected_paths=set((ST,DHD))
        actual=set(git("diff","--name-only",cwd=root).splitlines())
        if actual!=set(changed) or not actual.issubset(expected_paths):
            raise RuntimeError("Unexpected changed source paths")
        if subprocess.run(["git","diff","--check"],cwd=root,capture_output=True).returncode:
            raise RuntimeError("Whitespace check failed")
        print("CHANGED_FILES="+str(len(changed)))
        for item in changed: print("CHANGED_PATH="+item)
        if mode=="preview":
            print("RESULT=PREVIEW_PASS; MASTER_UNCHANGED=YES")
            return
        if not changed:
            print("RESULT=ALREADY_PRESENT; MASTER_UNCHANGED=YES")
            return
        existing=git("--config-env=http.extraheader=AZURE_GIT_HEADER",
                     "ls-remote","--heads","origin",BRANCH,cwd=root,env=env)
        if existing: raise RuntimeError("Feature branch already exists, abort no-force")
        git("checkout","-b",BRANCH,cwd=root)
        git("config","user.name","AnHiepLuc Automation",cwd=root)
        git("config","user.email","37570235+ngocnhanvo@users.noreply.github.com",cwd=root)
        git("add","--",*changed,cwd=root)
        staged=set(git("diff","--cached","--name-only",cwd=root).splitlines())
        if staged!=set(changed): raise RuntimeError("Unexpected staging")
        git("commit","-m","fix(products): match 37-column AnHiepLuc XLS and workshop/team sources",cwd=root)
        sha=git("rev-parse","HEAD",cwd=root)
        git("--config-env=http.extraheader=AZURE_GIT_HEADER","push",
            "origin","HEAD:refs/heads/"+BRANCH,cwd=root,env=env)
        print("AZURE_PUSH=PASS; COMMIT="+sha)
        pr=api_call("/pullrequests?api-version=7.1",pat,"POST",{
            "sourceRefName":"refs/heads/"+BRANCH,
            "targetRefName":"refs/heads/master",
            "title":"AnHiepLuc: XLS 37 columns for DHD and SOANTHAO, correct workshop and team",
            "description":"Both handlers aligned to 37 physical columns. Remove raw code and 4 legacy hidden columns, add Tổ SX. Xưởng SX from md_phanxuong; Tổ SX from md_phanxuong_to. Preserve authorization, module states and NPOI XLS. Source/static contract checks passed. Runtime DB and Excel download still require verification."
        })
        print("AZURE_PR_ID="+str(pr.get("pullRequestId")))
        print("RESULT=PR_CREATED; MASTER_UNCHANGED=YES")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("RESULT=FAILED; REASON="+str(e))
        sys.exit(1)
