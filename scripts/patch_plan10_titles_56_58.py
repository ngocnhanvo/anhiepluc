#!/usr/bin/env python3
"""Update only PLAN-10 runtime DevExpress column captions. SQL aliases stay unchanged."""
import base64, codecs, json, os, pathlib, re, subprocess, tempfile, time, urllib.error, urllib.request

REMOTE = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc"
API = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_apis/git/repositories/AnHiepLuc"
TARGET = "eman_ver3/View/Print/MD_00_BaoCaoKeHoach/BaoCaoTHDoanhThuTheoDDH_KH.aspx.cs"
BRANCH = "ai/plan10-rename-headings-56-58-20261120"
EXPECTED_MASTER = "239a26adf5fbcd847f7f56a066f4b85cc231edda"
MARKER = "// PLAN-10: displayed headings now match their source systems (56 / 58)."

def git(*args, cwd=None, env=None):
    p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True)
    if p.returncode: raise RuntimeError("GIT_FAILED_" + args[0])
    return p.stdout.decode("utf-8", "replace").strip()

def decode(raw):
    if raw.startswith(codecs.BOM_UTF8): enc="utf-8-sig"
    elif raw.startswith(codecs.BOM_UTF16_LE): enc="utf-16"
    else: enc="utf-8"
    return raw.decode(enc), enc

def patch(src):
    if MARKER in src:
        print("PATCH_STATUS=ALREADY_PRESENT")
        return src, False
    src = src.replace("\r\n", "\n")
    for label, frag in (
        ("ACTIVE_REPORT_TEMPLATE", "[KH] Báo Cáo Tổng Hợp Doanh Thu Theo ĐĐH.repx"),
        ("SOURCE_SYSTEM_56", "and substring(sp.ma_sanpham, 0, 3) = '56'"),
        ("SOURCE_SYSTEM_58", "and substring(sp.ma_sanpham, 0, 3) = '58'"),
        ("OUTPUT_ALIAS_C64", "as c64"),
        ("OUTPUT_ALIAS_C81CH", "as c81CH"),
    ):
        if frag not in src:raise RuntimeError("SOURCE_CONTRACT_MISSING_" + label)
    if "and substring(sp.ma_sanpham, 0, 3) = '64'" in src or "and substring(sp.ma_sanpham, 0, 3) = '81'" in src:
        raise RuntimeError("PREVIOUS_DATA_CHANGE_MISSING")
    lines=src.splitlines(keepends=True)
    idx=[i for i,line in enumerate(lines) if "var tbl" in line and "ReportViewer1.Report.DataSource" in line]
    if len(idx)!=1:raise RuntimeError("TARGET_REPORT_DATASOURCE_ASSIGNMENT_DRIFT")
    i=idx[0]
    if not any("viewReport" in x for x in lines[max(0,i-10):i]):
        raise RuntimeError("EXPECTED_VIEWREPORT_METHOD_NOT_FOUND")
    indent=re.match(r'^([ \t]*)',lines[i]).group(1)
    body=[
        indent + MARKER,
        indent + 'if (ReportViewer1.Report != null)',
        indent + '{',
        indent + '    foreach (DevExpress.XtraReports.UI.XRTableCell header in',
        indent + '        ReportViewer1.Report.AllControls<DevExpress.XtraReports.UI.XRTableCell>())',
        indent + '    {',
        indent + '        string title = (header.Text ?? string.Empty).Trim();',
        indent + '        if (title == "64")',
        indent + '            header.Text = "56";',
        indent + '        else if (title == "81 (CH)")',
        indent + '            header.Text = "58";',
        indent + '    }',
        indent + '}',
    ]
    after="".join(lines[:i])+"\n".join(body)+"\n"+"".join(lines[i:])
    if src.count("as c64")!=after.count("as c64") or src.count("as c81CH")!=after.count("as c81CH"):
        raise RuntimeError("DATA_ALIAS_CHANGED")
    if src.count("select sum((cdh.sl_dathang")!=after.count("select sum((cdh.sl_dathang"):
        raise RuntimeError("QUERY_MODIFIED")
    if len(after.splitlines())-len(src.splitlines()) != len(body): raise RuntimeError("UNEXPECTED_NEW_LINES")
    if after.count(MARKER)!=1 or after.count('header.Text = "56"')!=1 or after.count('header.Text = "58"')!=1:
        raise RuntimeError("CAPTION_MAPPING_NOT_UNIQUE")
    print("STATIC_CONTRACT=PASS; C64_HEADER=56; C81CH_HEADER=58")
    print("SQL_AND_OUTPUT_ALIASES=UNCHANGED; SHARED_PRINTER_AND_REPX=UNCHANGED")
    return after, True

def api(pat,path,method="GET",body=None):
    headers={"Authorization":"Basic "+base64.b64encode((":"+pat).encode()).decode(),"Accept":"application/json"}
    data=None if body is None else json.dumps(body).encode()
    if data is not None:headers["Content-Type"]="application/json"
    req=urllib.request.Request(API+path,method=method,headers=headers,data=data)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError("AZURE_API_HTTP_"+str(e.code)) from None

def head(pat):
    v=api(pat,"/refs?filter=heads/master&api-version=7.1")["value"]
    return next((z["objectId"] for z in v if z["name"]=="refs/heads/master"),None)

def main():
    mode=os.getenv("REPORT_TITLE_MODE","preview")
    if mode not in ("preview","apply"):raise RuntimeError("INVALID_MODE")
    pat=os.getenv("AZURE_DEVOPS_PAT","")
    if not pat:raise RuntimeError("MISSING_AZURE_PAT")
    env=os.environ.copy()
    env["AZURE_GIT_HEADER"]="AUTHORIZATION: Basic "+base64.b64encode((":"+pat).encode()).decode()
    with tempfile.TemporaryDirectory(prefix="anhl-title-plan10-") as td:
        root=pathlib.Path(td)/"src"
        git("--config-env=http.extraheader=AZURE_GIT_HEADER","clone","--quiet","--depth=1","--branch=master",REMOTE,str(root),env=env)
        sha=git("rev-parse","HEAD",cwd=root)
        print("MASTER_BEFORE="+sha)
        if sha!=EXPECTED_MASTER:raise RuntimeError("AZURE_MASTER_SHA_DRIFT")
        f=root/TARGET
        original=f.read_bytes()
        before,enc=decode(original)
        after,changed=patch(before)
        if not changed:return
        eol="\r\n" if b"\r\n" in original else "\n"
        f.write_bytes(after.replace("\r\n","\n").replace("\n",eol).encode(enc))
        if set(git("diff","--name-only",cwd=root).splitlines())!={TARGET}:
            raise RuntimeError("UNEXPECTED_FILE_SCOPE")
        git("-c","core.whitespace=cr-at-eol","diff","--check",cwd=root)
        stat=git("diff","--numstat",cwd=root)
        print("DIFF_NUMSTAT="+stat.replace(TARGET,"REPORT_CSHARP"))
        added,removed,_=stat.split("\t",2)
        if int(added)!=13 or int(removed)!=0:raise RuntimeError("UNEXPECTED_PATCH_SIZE")
        if mode=="preview":
            print("RESULT=PREVIEW_OK_NO_AZURE_WRITE")
            return
        git("-c","user.name=AnHiepLuc Reporting Automation",
            "-c","user.email=ngocnhanvo@users.noreply.github.com",
            "commit","-am","fix(PLAN-10): show system 56 and 58 in revenue report headers",cwd=root)
        commit=git("rev-parse","HEAD",cwd=root)
        print("AZURE_PATCH_COMMIT="+commit)
        git("--config-env=http.extraheader=AZURE_GIT_HEADER","push","origin","HEAD:refs/heads/"+BRANCH,cwd=root,env=env)
        print("AZURE_BRANCH_PUSH=PASS")
        if head(pat)!=sha:raise RuntimeError("MASTER_DRIFT_AFTER_PUSH")
        pr=api(pat,"/pullRequests?api-version=7.1","POST",{
            "sourceRefName":"refs/heads/"+BRANCH,
            "targetRefName":"refs/heads/master",
            "title":"PLAN-10: đổi tiêu đề cột 64 → 56 và 81 (CH) → 58",
            "description":"Chỉ thay text hiển thị trong XtraReport khi trang báo cáo PLAN-10 nạp; giữ nguyên SQL, alias c64/c81CH, tổng cộng và mọi báo cáo khác. Không phụ thuộc mẫu [KH-Cancel] trong repo."
        })
        no=pr["pullRequestId"]
        print("AZURE_PR_ID="+str(no))
        print("AZURE_PR_URL=https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc/pullrequest/"+str(no))
        for _ in range(12):
            pr=api(pat,"/pullRequests/"+str(no)+"?api-version=7.1")
            if pr.get("mergeStatus")=="succeeded":break
            if pr.get("mergeStatus") in ("conflicts","rejectedByPolicy","failure"):
                raise RuntimeError("AZURE_MERGE_BLOCKED_"+str(pr["mergeStatus"]))
            time.sleep(3)
        if pr.get("mergeStatus")!="succeeded":raise RuntimeError("PR_NOT_READY_LEAVE_OPEN")
        if head(pat)!=sha:raise RuntimeError("MASTER_DRIFT_BEFORE_MERGE")
        result=api(pat,"/pullRequests/"+str(no)+"?api-version=7.1","PATCH",{
            "status":"completed",
            "lastMergeSourceCommit":{"commitId":commit},
            "completionOptions":{"mergeStrategy":"noFastForward","deleteSourceBranch":False,"bypassPolicy":False}
        })
        print("COMPLETION_REQUEST="+str(result.get("status")))
        for _ in range(12):
            pr=api(pat,"/pullRequests/"+str(no)+"?api-version=7.1")
            curr=head(pat)
            if pr.get("status")=="completed" and curr and curr!=sha:
                print("MASTER_AFTER="+curr)
                print("AZURE_MERGE_VERIFIED=PASS")
                return
            time.sleep(4)
        raise RuntimeError("AZURE_MERGE_NOT_VERIFIED")
if __name__=="__main__":main()
