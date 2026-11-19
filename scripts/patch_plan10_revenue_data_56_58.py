#!/usr/bin/env python3
"""Apply the PLAN-10 data-source switch in one Azure file (no report label changes).

Visible report columns remain bound to c64 and c81CH; source systems become
56 and 58 respectively. Former system-81 pottery-specific filters are removed
so c81CH contains all system-58 sales. Production requires Azure PR policies.
"""
import base64
import codecs
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

REMOTE = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc"
API = "https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_apis/git/repositories/AnHiepLuc"
TARGET = "eman_ver3/View/Print/MD_00_BaoCaoKeHoach/BaoCaoTHDoanhThuTheoDDH_KH.aspx.cs"
BRANCH = "ai/plan10-switch-revenue-to-56-58-20261120"
EXPECTED_MASTER = "bfd12089c05c98acc94288c57462fe3a0330d248"

OLD_64 = "and substring(sp.ma_sanpham, 0, 3) = '64'"
OLD_81 = "and substring(sp.ma_sanpham, 0, 3) = '81'"
NEW_56 = "and substring(sp.ma_sanpham, 0, 3) = '56'"
NEW_58 = "and substring(sp.ma_sanpham, 0, 3) = '58'"
OLD_FILTER_F = "and sp.ma_sanpham not like N'%F%'"
OLD_FILTER_CHAU = "and sp.mota_tiengviet like N'Chậu%'"


def git(*args, cwd=None, env=None):
    p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True)
    if p.returncode:
        raise RuntimeError("GIT_FAILED_" + args[0])
    return p.stdout.decode("utf-8", "replace").strip()


def decode(raw):
    if raw.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif raw.startswith(codecs.BOM_UTF16_LE):
        encoding = "utf-16"
    else:
        encoding = "utf-8"
    return raw.decode(encoding), encoding


def patch(before):
    for label, text in (
        ("OLD_C64", OLD_64),
        ("OLD_C81CH", OLD_81),
        ("LEGACY_FILTER_F", OLD_FILTER_F),
        ("LEGACY_FILTER_CHAU", OLD_FILTER_CHAU),
        ("ALIAS_C64", ") as c64"),
        ("ALIAS_C81CH", ") as c81CH"),
    ):
        if before.count(text) != 1:
            raise RuntimeError("SOURCE_DRIFT_" + label)

    # Ensure these exact predicates belong to the intended output aliases.
    if not (before.index(OLD_64) < before.index(") as c64") <
            before.index(OLD_81) < before.index(OLD_FILTER_F) <
            before.index(OLD_FILTER_CHAU) < before.index(") as c81CH")):
        raise RuntimeError("SYSTEM_ORDER_OR_ALIAS_DRIFT")

    out = before.replace(OLD_64, NEW_56, 1).replace(OLD_81, NEW_58, 1)
    lines = out.splitlines(keepends=True)
    filtered = []
    removed = []
    for line in lines:
        if line.strip() in (OLD_FILTER_F, OLD_FILTER_CHAU):
            removed.append(line.strip())
            continue
        filtered.append(line)
    if sorted(removed) != sorted([OLD_FILTER_F, OLD_FILTER_CHAU]):
        raise RuntimeError("UNEXPECTED_LEGACY_FILTER_COUNT")
    out = "".join(filtered)

    for label in ("as c64", "as c81CH", "sum(tongcong)", "sum(c81CH)",
                  "isnull(A.c64, 0)", "isnull(A.c81CH, 0)"):
        if before.count(label) != out.count(label):
            raise RuntimeError("OUTPUT_ALIAS_CHANGED_" + label)
    if out.count(NEW_56) != 1 or out.count(NEW_58) != 1:
        raise RuntimeError("NEW_SYSTEM_NOT_UNIQUE")
    if OLD_64 in out or OLD_81 in out or OLD_FILTER_F in out or OLD_FILTER_CHAU in out:
        raise RuntimeError("LEGACY_FILTER_NOT_REMOVED")
    if before.count("select sum((cdh.sl_dathang") != out.count("select sum((cdh.sl_dathang"):
        raise RuntimeError("SUBQUERY_COUNT_CHANGED")
    if before.count("as tongcong") != out.count("as tongcong"):
        raise RuntimeError("TOTAL_FORMULA_CHANGED")
    print("PATCH_CONTRACT=PASS; SYSTEM_C64=56; SYSTEM_C81CH=58")
    print("REPORT_LABELS=UNCHANGED; DATA_ALIASES=UNCHANGED; NO_SYSTEM_AGGREGATION=PASS")
    print("OLD_C81_POTTERY_FILTERS=REMOVED; OTHER_SQL=UNCHANGED")
    return out


def api(pat, path, method="GET", body=None):
    h = {"Authorization": "Basic "+base64.b64encode((":"+pat).encode()).decode(),
         "Accept": "application/json"}
    data = None if body is None else json.dumps(body).encode()
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, method=method, headers=h, data=data)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("AZURE_API_HTTP_" + str(exc.code)) from None


def master_head(pat):
    refs = api(pat, "/refs?filter=heads/master&api-version=7.1")["value"]
    return next((r["objectId"] for r in refs if r["name"] == "refs/heads/master"), None)


def main():
    pat = os.environ.get("AZURE_DEVOPS_PAT", "")
    if not pat: raise RuntimeError("AZURE_PAT_MISSING")
    env = os.environ.copy()
    env["AZURE_GIT_HEADER"] = "AUTHORIZATION: Basic "+base64.b64encode((":"+pat).encode()).decode()
    with tempfile.TemporaryDirectory(prefix="ahl-plan10-") as td:
        root = pathlib.Path(td)/"src"
        git("--config-env=http.extraheader=AZURE_GIT_HEADER", "clone", "--depth=1",
            "--quiet", "--branch=master", REMOTE, str(root), env=env)
        sha = git("rev-parse", "HEAD", cwd=root)
        print("AZURE_MASTER_BEFORE="+sha)
        if sha != EXPECTED_MASTER:
            raise RuntimeError("AZURE_MASTER_CHANGED_REAUDIT")
        path = root/TARGET
        original = path.read_bytes()
        before, encoding = decode(original)
        after = patch(before)
        eol = "\r\n" if b"\r\n" in original else "\n"
        normalized = after.replace("\r\n", "\n").replace("\n", eol)
        path.write_bytes(normalized.encode(encoding))
        if set(git("diff", "--name-only", cwd=root).splitlines()) != {TARGET}:
            raise RuntimeError("UNEXPECTED_FILE_CHANGED")
        git("-c", "core.whitespace=cr-at-eol", "diff", "--check", cwd=root)
        stat = git("diff", "--numstat", cwd=root)
        print("DIFF_NUMSTAT="+stat.replace(TARGET,"TARGET_CSHARP"))
        if not stat.startswith("2\t4\t") and not stat.startswith("2\t4\t".replace("\\t", "\t")):
            raise RuntimeError("PATCH_SCOPE_DIFF_UNEXPECTED")
        if os.getenv("REPORT_PATCH_MODE", "preview") == "preview":
            print("RESULT=PREVIEW_OK_NO_AZURE_WRITE")
            return
        if os.getenv("REPORT_PATCH_MODE") != "apply":
            raise RuntimeError("INVALID_MODE")

        git("-c", "user.name=AnHiepLuc Reporting Automation",
            "-c", "user.email=ngocnhanvo@users.noreply.github.com",
            "commit", "-am", "fix(report): use system 56 and 58 data under existing 64/81 headings", cwd=root)
        commit = git("rev-parse", "HEAD", cwd=root)
        print("AZURE_PATCH_COMMIT="+commit)
        git("--config-env=http.extraheader=AZURE_GIT_HEADER", "push",
            "origin", "HEAD:refs/heads/"+BRANCH, cwd=root, env=env)
        print("AZURE_BRANCH_PUSH=PASS")
        if master_head(pat) != sha:
            raise RuntimeError("MASTER_DRIFT_AFTER_BRANCH_PUSH")
        pr = api(pat, "/pullRequests?api-version=7.1", "POST", {
            "sourceRefName": "refs/heads/"+BRANCH,
            "targetRefName": "refs/heads/master",
            "title": "PLAN-10: dùng dữ liệu hệ 56, 58, giữ nguyên tiêu đề cột 64 và 81 (CH)",
            "description": "Chỉ sửa SQL của BaoCaoTHDoanhThuTheoDDH_KH.aspx.cs. c64 lấy hệ 56; c81CH lấy toàn bộ hệ 58 (bỏ bộ lọc Chậu cũ). Không thay alias, tiêu đề, biểu mẫu, cấu trúc cột, tổng cộng hoặc DB."
        })
        number = pr["pullRequestId"]
        print("AZURE_PR_ID="+str(number))
        print("AZURE_PR_URL=https://dev.azure.com/vongocnhancd10cntt2/AnHiepLuc/_git/AnHiepLuc/pullrequest/"+str(number))
        for _ in range(12):
            pr = api(pat, "/pullRequests/"+str(number)+"?api-version=7.1")
            if pr.get("mergeStatus") == "succeeded":
                break
            if pr.get("mergeStatus") in ("conflicts", "rejectedByPolicy", "failure"):
                print("MERGE_STATUS="+str(pr.get("mergeStatus")))
                raise RuntimeError("AZURE_PR_BLOCKED_LEAVE_OPEN")
            time.sleep(3)
        if pr.get("mergeStatus") != "succeeded":
            print("MERGE_STATUS="+str(pr.get("mergeStatus")))
            raise RuntimeError("AZURE_PR_NOT_READY_LEAVE_OPEN")
        if master_head(pat) != sha:
            raise RuntimeError("MASTER_DRIFT_BEFORE_MERGE")
        completion = api(pat, "/pullRequests/"+str(number)+"?api-version=7.1", "PATCH", {
            "status": "completed",
            "lastMergeSourceCommit": {"commitId": commit},
            "completionOptions": {
                "mergeStrategy": "noFastForward",
                "deleteSourceBranch": False,
                "bypassPolicy": False
            }
        })
        print("COMPLETION_REQUEST_STATUS="+str(completion.get("status")))
        for _ in range(12):
            pr = api(pat, "/pullRequests/"+str(number)+"?api-version=7.1")
            now = master_head(pat)
            if pr.get("status") == "completed" and now and now != sha:
                print("AZURE_MASTER_AFTER="+now)
                print("AZURE_MERGE_VERIFIED=PASS")
                return
            time.sleep(4)
        raise RuntimeError("AZURE_MERGE_NOT_VERIFIED_CHECK_PR")


if __name__ == "__main__":
    main()
