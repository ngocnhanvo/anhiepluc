#!/usr/bin/env python3
"""Guarded fix for the existing AnHiepLuc price-version case.

Runs inside GitHub Actions. Private Azure source stays in ephemeral checkout.
preview: validates exact source and patch without writing to Azure.
apply: creates a single-file Azure branch + PR (master unchanged).
"""
import base64
import codecs
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REMOTE = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc"
API = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_apis/git/repositories/AnHiepLuc"
TARGET = "eman_ver3/Controller/JQGridModify/JQGridMD_01_PhienBangGiaJQGSModify.ashx"
BRANCH = "ai/fix-ca01-capnhatlaigsp-vcnb-20261031"
AUDITED_SHA = "5a9ed179ae95e2e5139297b5e4899a3d89e835d3"

def git(*args, cwd=None, env=None):
    p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True)
    if p.returncode:
        raise RuntimeError("GIT_OPERATION_FAILED:" + args[0])
    return p.stdout.decode("utf-8", "replace").strip()

def decode_file(path):
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF16_LE):
        encoding = "utf-16"
    elif data.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif data[:100].count(b"\x00") > 20:
        encoding = "utf-16-le"
    else:
        try:
            data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            encoding = "cp1258"
    src = data.decode(encoding)
    crlf = src.count("\r\n") > 0
    return src.replace("\r\n", "\n"), encoding, crlf

def patch(src):
    # Do not change the existing md_xuatkhonb or md_nhapkhonb logic.
    old = re.compile(
        r"(?m)^(?P<i>[ \t]*)var vcnbss = db\.md_vanchuyennoibo[ \t]*\n"
        r"[ \t]*\.Where\(s => s\.phienbangiaNC == id\);[ \t]*\n"
        r"(?P=i)if \(type == \"2\"\)[ \t]*\n"
        r"[ \t]*vcnbss = vcnbss\.Where\(s => scts\.Contains\(s\.sochungtu\)\);[ \t]*\n"
        r"(?P=i)else[ \t]*\n"
        r"[ \t]*vcnbss = vcnbss\.Where\(s => s\.ngaytao >= ngaygoihan\);"
    )
    matches = list(old.finditer(src))
    if len(matches) != 1:
        if "var vcnbss = db.md_vanchuyennoibo.AsQueryable();" in src and
                "s.banggiaNC == pbg.md_banggia_id" in src:
            return src, False
        raise RuntimeError("DRIFTED_VCNB_QUERY_BLOCK")
    m = matches[0]
    i = m.group("i")
    revised = "\n".join((
        i + "var vcnbss = db.md_vanchuyennoibo.AsQueryable();",
        i + "if (type == \"2\")",
        i + "    vcnbss = vcnbss.Where(s => scts.Contains(s.sochungtu) &&",
        i + "        s.banggiaNC == pbg.md_banggia_id);",
        i + "else",
        i + "    vcnbss = vcnbss.Where(s => s.phienbangiaNC == id &&",
        i + "        s.ngaytao >= ngaygoihan);",
    ))
    src = src[:m.start()] + revised + src[m.end():]

    assignment = re.compile(
        r"(?m)^(?P<i>[ \t]*)foreach \(var xnb in vcnbs\)[ \t]*\n"
        r"(?P=i)\{[ \t]*\n"
        r"(?P<a>[ \t]*)if \(doiPBGMoiNhat == \"1\"\)[ \t]*\n"
        r"(?P=a)[ \t]*xnb\.phienbangiaNC = pbgMoiNhat\.md_phienbangia_id;"
    )
    assigns = list(assignment.finditer(src))
    if len(assigns) != 1:
        raise RuntimeError("DRIFTED_VCNB_ASSIGNMENT_BLOCK")
    am = assigns[0]
    a = am.group("a")
    src = (src[:am.end()] +
           "\n" + a + "else if (type == \"2\")" +
           "\n" + a + "    xnb.phienbangiaNC = pbg.md_phienbangia_id;" +
           src[am.end():])
    return src, True

def verify(before, after, changed):
    assert after.count("var vcnbss = db.md_vanchuyennoibo.AsQueryable();") == 1
    assert after.count("s.banggiaNC == pbg.md_banggia_id") == 1
    assert "s.phienbangiaNC == id &&" in after
    assert "xnb.phienbangiaNC = pbg.md_phienbangia_id;" in after
    assert "md_vanchuyennoibo_cdvc" in after
    assert "md_vanchuyennoibo_dalayton" in after
    assert before.count("var xnbss = db.md_xuatkhonb.AsQueryable();") == after.count(
        "var xnbss = db.md_xuatkhonb.AsQueryable();") == 1
    assert before.count("db.md_nhapkhonb") == after.count("db.md_nhapkhonb")
    assert before.count("db.SaveChanges();") == after.count("db.SaveChanges();")
    assert before.count("transaction.Commit();") == after.count("transaction.Commit();")
    assert before.count("transaction.Rollback();") == after.count("transaction.Rollback();")
    if changed:
        diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(), n=0))
        additions = [x for x in diff if x.startswith("+") and not x.startswith("+++")]
        deletions = [x for x in diff if x.startswith("-") and not x.startswith("---")]
        if len(additions) != 10 or len(deletions) != 6:
            raise RuntimeError("UNEXPECTED_PATCH_SCOPE")
    print("STATIC_CONTRACT=PASS; TABLE=md_vanchuyennoibo; OTHER_MODULES=UNCHANGED")

def api(path, pat, method="GET", body=None):
    auth = "Basic " + base64.b64encode((":" + pat).encode()).decode()
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization":auth, "Accept":"application/json"}
    if data is not None: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, headers=headers, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError("AZURE_API_HTTP_" + str(e.code)) from None

def main():
    mode = os.environ.get("PRICE_FIX_MODE", "preview")
    if mode not in ("preview", "apply"):
        raise RuntimeError("INVALID_MODE")
    pat = os.environ.get("AZURE_DEVOPS_PAT", "")
    if not pat: raise RuntimeError("MISSING_AZURE_PAT")
    env = os.environ.copy()
    env["AZURE_GIT_HEADER"] = "AUTHORIZATION: Basic " + base64.b64encode((":" + pat).encode()).decode()
    with tempfile.TemporaryDirectory(prefix="anhl-price-fix-") as d:
        root = pathlib.Path(d)/"source"
        git("--config-env=http.extraheader=AZURE_GIT_HEADER", "clone", "--quiet", "--depth=1", "--branch=master", REMOTE, str(root), env=env)
        base = git("rev-parse", "HEAD", cwd=root)
        if git("branch", "--show-current", cwd=root) != "master":
            raise RuntimeError("NOT_MASTER")
        print("AZURE_MASTER_BEFORE=" + base)
        if base != AUDITED_SHA:
            raise RuntimeError("MASTER_SHA_DRIFT_STOP_AND_REAUDIT")
        f = root/TARGET
        before, encoding, crlf = decode_file(f)
        after, changed = patch(before)
        verify(before, after, changed)
        if not changed:
            print("RESULT=ALREADY_PATCHED")
            return
        f.write_bytes(after.replace("\n", "\r\n" if crlf else "\n").encode(encoding))
        actual = set(git("diff", "--name-only", cwd=root).splitlines())
        if actual != {TARGET}: raise RuntimeError("UNEXPECTED_FILE_CHANGE")
        if subprocess.run(["git","diff","--check"],cwd=root,capture_output=True).returncode:
            raise RuntimeError("WHITESPACE_CHECK_FAILED")
        print("PATCH_SCOPE=PASS; FILES=1; LINES_CHANGED=16; DIFF_CHECK=PASS")
        if mode == "preview":
            print("RESULT=PREVIEW_PASS; AZURE_MASTER_UNCHANGED=YES")
            return
        remote = git("--config-env=http.extraheader=AZURE_GIT_HEADER", "ls-remote", "--heads", "origin", BRANCH,cwd=root,env=env)
        if remote: raise RuntimeError("FEATURE_BRANCH_ALREADY_EXISTS")
        git("checkout","-b",BRANCH,cwd=root)
        git("config","user.name","AnHiepLuc Automation",cwd=root)
        git("config","user.email","37570235+ngocnhanvo@users.noreply.github.com",cwd=root)
        git("add","--",TARGET,cwd=root)
        if set(git("diff","--cached","--name-only",cwd=root).splitlines()) != {TARGET}:
            raise RuntimeError("UNEXPECTED_STAGED_PATH")
        git("commit","-m","fix(pricing): support assigning version to selected internal transfer slips",cwd=root)
        source_sha=git("rev-parse","HEAD",cwd=root)
        git("--config-env=http.extraheader=AZURE_GIT_HEADER","push","origin","HEAD:refs/heads/"+BRANCH,cwd=root,env=env)
        print("AZURE_BRANCH_PUSH=PASS; SOURCE_SHA="+source_sha)
        pr=api("/pullrequests?api-version=7.1",pat,"POST",{
            "sourceRefName":"refs/heads/"+BRANCH,
            "targetRefName":"refs/heads/master",
            "title":"Fix: Apply selected labor price version to internal-transfer slips",
            "description":"Scope: one Azure WebForms handler (CA_01_CapNhatLaiGSP). Type=2 selects specified md_vanchuyennoibo slips with matching banggiaNC, including blank phienbangiaNC. Other modes retain previous filter; selected price version is assigned before detail price refresh. No SQL writes by this automation. Static contract and diff checks PASS."
        })
        print("AZURE_PR_ID="+str(pr.get("pullRequestId")))
        print("RESULT=PR_CREATED; MASTER_UNCHANGED=YES")
if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("RESULT=FAILED; REASON="+str(exc))
        sys.exit(1)
