#!/usr/bin/env python3
"""Merge a specific verified Azure pricing-fix PR, without bypassing branch policy."""
import base64
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

BASE = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_apis/git/repositories/AnHiepLuc"
REMOTE = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc"
EXPECTED_MASTER = "5a9ed179ae95e2e5139297b5e4899a3d89e835d3"
SOURCE_BRANCH = "refs/heads/ai/fix-ca01-capnhatlaigsp-vcnb-20261031"
TARGET = "eman_ver3/Controller/JQGridModify/JQGridMD_01_PhienBangGiaJQGSModify.ashx"
PAT = os.environ.get("AZURE_DEVOPS_PAT","")
if not PAT: raise RuntimeError("MISSING_AZURE_PAT")
HEADERS={"Authorization":"Basic "+base64.b64encode((":"+PAT).encode()).decode(),"Accept":"application/json"}

def api(path,method="GET",body=None):
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers=HEADERS.copy()
    if payload is not None: headers["Content-Type"]="application/json"
    request=urllib.request.Request(BASE+path,data=payload,headers=headers,method=method)
    try:
        with urllib.request.urlopen(request,timeout=40) as resp: return json.load(resp)
    except urllib.error.HTTPError as err:
        raise RuntimeError("AZURE_API_HTTP_"+str(err.code)) from None

def master():
    x=api("/refs?filter=heads/master&api-version=7.1").get("value",[])
    return next((a.get("objectId") for a in x if a.get("name")=="refs/heads/master"),None)

def verify_master():
    env=os.environ.copy()
    env["AZURE_GIT_HEADER"]=HEADERS["Authorization"]
    with tempfile.TemporaryDirectory(prefix="anhl-verify-") as d:
        dest=pathlib.Path(d)/"azure"
        cmd=["git","--config-env=http.extraheader=AZURE_GIT_HEADER","clone","--quiet","--depth=1","--branch","master",REMOTE,str(dest)]
        p=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode:raise RuntimeError("VERIFY_CLONE_FAILED")
        b=(dest/TARGET).read_bytes()
        for enc in ("utf-8-sig","utf-16","cp1258"):
            try:code=b.decode(enc);break
            except UnicodeError:continue
        else:raise RuntimeError("VERIFY_DECODE_FAILED")
        if (code.count("var vcnbss = db.md_vanchuyennoibo.AsQueryable();")!=1 or
                "s.banggiaNC == pbg.md_banggia_id" not in code or
                "else if (type == \"2\")\n" not in code.replace("\r\n","\n")):
            raise RuntimeError("POST_MERGE_SOURCE_MISMATCH")
        print("POST_MERGE_STATIC=PASS; TARGET_FILE="+TARGET)

def run():
    event=json.load(open(os.environ["GITHUB_EVENT_PATH"],encoding="utf-8"))
    body=json.loads(event["issue"]["body"])
    pr_id=body.get("pr_id")
    expected_source=body.get("source_sha")
    if not isinstance(pr_id,int) or pr_id<1:raise RuntimeError("INVALID_PR_ID")
    if not isinstance(expected_source,str) or len(expected_source)!=40 or any(c not in "0123456789abcdef" for c in expected_source):
        raise RuntimeError("INVALID_SOURCE_SHA")
    url="/pullrequests/"+str(pr_id)+"?api-version=7.1"
    pr=api(url)
    sha=master()
    if pr.get("sourceRefName")!=SOURCE_BRANCH or pr.get("targetRefName")!="refs/heads/master":
        raise RuntimeError("PR_BRANCH_MISMATCH")
    if (pr.get("lastMergeSourceCommit") or {}).get("commitId")!=expected_source:
        raise RuntimeError("SOURCE_SHA_MISMATCH")
    if pr.get("status")=="completed":
        print("PR_ALREADY_COMPLETED=YES; AZURE_MASTER="+str(sha))
        verify_master()
        return
    if pr.get("status")!="active" or pr.get("isDraft"):
        raise RuntimeError("PR_NOT_ACTIVE_OR_DRAFT")
    if sha!=EXPECTED_MASTER:raise RuntimeError("MASTER_SHA_DRIFT_NO_MERGE")
    for _ in range(16):
        if pr.get("mergeStatus")=="succeeded":break
        if pr.get("mergeStatus") in ("conflicts","failure","rejectedByPolicy"):
            raise RuntimeError("PR_MERGE_POLICY_OR_CONFLICT_BLOCKED")
        time.sleep(3)
        pr=api(url)
    if pr.get("mergeStatus")!="succeeded":raise RuntimeError("PR_MERGE_NOT_READY")
    print("GUARDED_MERGE_READY=YES; PR="+str(pr_id)+"; SOURCE="+expected_source+"; BASE="+sha)
    api(url,"PATCH",{
        "status":"completed",
        "lastMergeSourceCommit":{"commitId":expected_source},
        "completionOptions":{"mergeStrategy":"noFastForward","deleteSourceBranch":False,"bypassPolicy":False}
    })
    for _ in range(20):
        current=api(url)
        after=master()
        if current.get("status")=="completed" and after and after!=EXPECTED_MASTER:
            print("AZURE_PR_MERGE=PASS; AZURE_MASTER_AFTER="+after)
            verify_master()
            return
        if current.get("mergeStatus") in ("conflicts","failure","rejectedByPolicy"):
            raise RuntimeError("MERGE_REJECTED_BY_POLICY_OR_CONFLICT")
        time.sleep(3)
    raise RuntimeError("MERGE_RESULT_NOT_CONFIRMED")

if __name__=="__main__":
    try:run()
    except Exception as err:
        print("RESULT=FAILED; REASON="+str(err))
        sys.exit(1)
