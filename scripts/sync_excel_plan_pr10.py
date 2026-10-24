#!/usr/bin/env python3
"""Safely update existing Azure PR #10 planning document from GitHub Actions.

GitHub repo only holds the action; source-of-truth documentation is on Azure.
No Azure master writes, no source code modifications, no secrets in logs.
"""
import base64
import json
import os
import pathlib
import re
import subprocess
import tempfile
import urllib.error
import urllib.request

ORGANIZATION = "vongocnhancd10cntt2"
PROJECT = "AnHiepLuc"
REPO = "AnHiepLuc"
PR_ID = 10
BRANCH = "ai/plan-excel-template-41-columns-20261025"
OLD_PATH = "docs/MD_00_DSHangHoaVG_Excel_41_Column_Alignment_PLAN.md"
NEW_PATH = "docs/MD_00_DSHangHoaVG_Excel_37_Column_Alignment_PLAN.md"
SOURCE_PATH = "plans/AnHiepLuc_Product_Export_41_Column_Alignment_PLAN.md"
BASE = f"https://dev.azure.com/{ORGANIZATION}/{PROJECT}/_apis/git/repositories/{REPO}"
REMOTE = f"https://dev.azure.com/{ORGANIZATION}/{PROJECT}/_git/{REPO}"
TITLE = "Documentation only: AnHiepLuc 37-column XLS export and production workshop/team mapping"

def run(args, *, cwd=None, env=None):
    proc = subprocess.run(["git"] + args, cwd=cwd, env=env, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("GIT_FAILED (sensitive details suppressed)")
    return proc.stdout.decode("utf-8","replace").strip()

def azure_call(endpoint, auth, method="GET", data=None):
    payload=None if data is None else json.dumps(data).encode("utf-8")
    req=urllib.request.Request(BASE+endpoint, data=payload, method=method,
      headers={"Authorization": auth, "Accept":"application/json",
               **({"Content-Type":"application/json"} if payload is not None else {})})
    try:
        with urllib.request.urlopen(req,timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError("AZURE_API_HTTP_"+str(error.code)) from None

def validate_plan(text):
    lines=text.splitlines()
    rows=[m.group(1) for line in lines if (m:=re.match(r"^\| ([A-Z]{1,2}) \|",line))]
    if len(rows)!=37 or rows[0]!="A" or rows[-1]!="AK":
        raise RuntimeError("PLAN_COLUMNS_NOT_37")
    for col in ("AH | Xưởng SX","AI | Tổ SX","AJ | Thuế","AK | Bán TP"):
        if not any(col in x for x in lines): raise RuntimeError("PLAN_TAIL_MAPPING_WRONG")
    if not all(term in text for term in ("md_phanxuong.ten_phanxuong",
        "md_phanxuong_to.ten_to", "sp.md_phanxuong_id","sp.md_to_id",
        "LOẠI BỎ", "37 cột")):
        raise RuntimeError("PLAN_MISSING_OWNER_DECISIONS")
    for name in ("vd","vn","vl","ghichu_vachngan","Mã thô"):
        if any(re.search(r"^\| [A-Z]{1,2} \| "+re.escape(name)+r" \|",x) for x in lines):
            raise RuntimeError("REMOVED_COLUMN_STILL_IN_TABLE")
    print("VALIDATE_37_COLUMN_PLAN=PASS")
    print("WORKSHOP_SOURCE=md_phanxuong; TEAM_SOURCE=md_phanxuong_to")

def main():
    pat=os.environ.get("AZURE_DEVOPS_PAT")
    if not pat: raise RuntimeError("MISSING_AZURE_DEVOPS_PAT")
    env=os.environ.copy()
    auth="Basic "+base64.b64encode((":"+pat).encode("utf-8")).decode("ascii")
    env["AZURE_AUTH_HEADER"]="AUTHORIZATION: "+auth
    source=pathlib.Path(SOURCE_PATH)
    if not source.is_file(): raise RuntimeError("SOURCE_PLAN_NOT_FOUND")
    updated=source.read_text("utf-8")
    validate_plan(updated)

    pr=azure_call(f"/pullrequests/{PR_ID}?api-version=7.1",auth)
    if pr.get("status")!="active":
        raise RuntimeError("PR_NOT_ACTIVE: "+str(pr.get("status")))
    if (pr.get("sourceRefName")!="refs/heads/"+BRANCH
        or pr.get("targetRefName")!="refs/heads/master"):
        raise RuntimeError("PR_SCOPE_MISMATCH")

    with tempfile.TemporaryDirectory() as directory:
        root=pathlib.Path(directory)/"azure"
        run(["--config-env=http.extraheader=AZURE_AUTH_HEADER","clone",
             "--quiet","--depth=1","--branch",BRANCH,REMOTE,str(root)],env=env)
        old=root/OLD_PATH
        new=root/NEW_PATH
        if not old.is_file() and not new.is_file():
            raise RuntimeError("PLANNING_FILE_MISSING_ON_AZURE_BRANCH")
        if old.is_file() and new.exists():
            raise RuntimeError("BOTH_OLD_AND_NEW_EXIST: require review")
        if old.exists():
            new.parent.mkdir(parents=True,exist_ok=True)
            old.rename(new)
        new.write_text(updated,encoding="utf-8")
        changed=run(["status","--porcelain"],cwd=root).splitlines()
        paths=run(["ls-files","--others","--modified","--deleted","--exclude-standard"],cwd=root).splitlines()
        if any(p not in (OLD_PATH,NEW_PATH) for p in paths):
            raise RuntimeError("UNEXPECTED_CHANGE_DETECTED")
        if changed:
            run(["config","user.name","AnHiepLuc Automation"],cwd=root)
            run(["config","user.email","37570235+ngocnhanvo@users.noreply.github.com"],cwd=root)
            run(["add","--",OLD_PATH,NEW_PATH],cwd=root)
            staged=run(["diff","--cached","--name-only"],cwd=root).splitlines()
            if sorted(staged)!=sorted([OLD_PATH,NEW_PATH]):
                raise RuntimeError("STAGED_FILES_MISMATCH")
            run(["commit","-m","docs: remove hidden XLS fields; use workshop/team source tables"],cwd=root)
            commit=run(["rev-parse","HEAD"],cwd=root)
            run(["--config-env=http.extraheader=AZURE_AUTH_HEADER","push","origin",
                 "HEAD:refs/heads/"+BRANCH],cwd=root,env=env)
            print("AZURE_PLAN_COMMIT="+commit)
        else:
            print("AZURE_PLAN_ALREADY_UPDATED=YES")

    refreshed=azure_call(f"/pullrequests/{PR_ID}?api-version=7.1",auth)
    if refreshed.get("status")!="active":
        raise RuntimeError("PR_STATUS_CHANGED_DURING_UPDATE")
    result=azure_call(f"/pullrequests/{PR_ID}?api-version=7.1",auth,"PATCH",{
      "title":TITLE,
      "description":"Documentation-only plan updated for 37 visible/physical XLS columns. "
                    "Remove vd/vn/vl/ghichu_vachngan and Ma tho. "
                    "Workshop from md_phanxuong, team from md_phanxuong_to; "
                    "key mappings verified before implementation. No application-code changes."
    })
    print("AZURE_PR_ID="+str(result.get("pullRequestId")))
    print("AZURE_PR_STATUS="+str(result.get("status")))
    print("PR_UPDATE=PASS; AZURE_MASTER_NOT_MODIFIED=YES")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("PLAN_SYNC=FAILED; REASON="+str(exc))
        raise SystemExit(1)
