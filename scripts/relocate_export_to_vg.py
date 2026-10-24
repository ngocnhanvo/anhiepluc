#!/usr/bin/env python3
"""Relocate AnHiepLuc Excel export to the correct DHD module, Azure-only.

Reference is pinned Anco1. GitHub is used only as an Actions runner.
Preview is read-only. Source content, diffs and credentials never appear in logs.
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
import urllib.error
import urllib.request

ORG = "vongocnhancd10cntt2"
PROJECT = "AnHiepLuc"
REPO = "AnHiepLuc"
REMOTE = "https://dev.azure.com/{}/{}/_git/{}".format(ORG, PROJECT, REPO)
API = "https://dev.azure.com/{}/{}/_apis/git/repositories/{}".format(ORG, PROJECT, REPO)
REF_BASE = "https://raw.githubusercontent.com/ngocnhanvo/anco1/e7d753c0d1e2c102ddb2315fb14cbfc8bc16e81e/"
PREVIOUS_MASTER = "0e4051f8bfedd9d27d885edb3e8d7ee853c9664b"
PREVIOUS_MERGE = "0990610afcc5ef6a1ff385def023f4bebecc8c6a"
FEATURE_SHA = "057678711c69f9b361fd28f5fea6a1f3fd320625"
BRANCH = "ai/relocate-excel-export-to-vg-20261024"
ROOT = "eman_ver3/"
HH_JS = ROOT+"js/Module_script/MD_00_DSHangHoa.js"
HH_HANDLER = ROOT+"Controller/JQGridModify/JQGridMD_00_DSHangHoaModify.ashx"
VG_JS = ROOT+"js/Module_script/MD_00_DSHangHoaVG.js"
VG_HANDLER = ROOT+"Controller/JQGridModify/JQGridMD_00_DSHangHoaVGModify.ashx"
ALLOWED = [HH_JS, HH_HANDLER, VG_JS, VG_HANDLER]

def git(args, cwd=None, env=None, raw=False):
    p = subprocess.run(["git"]+args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError("Git command failed (details withheld)")
    return p.stdout if raw else p.stdout.decode("utf-8","replace").strip()

def git_ok(args, cwd=None):
    return subprocess.run(["git"]+args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

def read_file(path):
    original = path.read_bytes()
    if original.startswith(codecs.BOM_UTF16_LE):
        encoding = "utf-16"
    elif original.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif original[:512].count(b"\x00") > 20:
        encoding = "utf-16-le"
    else:
        try: original.decode("utf-8"); encoding = "utf-8"
        except UnicodeDecodeError: encoding = "cp1258"
    text = original.decode(encoding).replace("\r\n","\n")
    newline = "\r\n" if original.count(b"\r\n") > original.count(b"\n")/2 else "\n"
    # UTF-16 newlines cannot be detected by byte count above.
    if encoding.startswith("utf-16"):
        newline = "\r\n" if text.count("\n") > 0 and original.count(b"\r\x00\n\x00") > 0 else "\n"
    return text, encoding, newline, original

def save(path, content, encoding, newline):
    path.write_bytes(content.replace("\r\n","\n").replace("\n",newline).encode(encoding))

def reference(path):
    with urllib.request.urlopen(REF_BASE+path,timeout=40) as resp:
        return resp.read().decode("utf-8-sig").replace("\r\n","\n")

def block(text, tag):
    pattern = r"(?ms)^[ \t]*//start "+re.escape(tag)+r"[ \t]*\n.*?^[ \t]*//end "+re.escape(tag)+r"[ \t]*"
    matches = list(re.finditer(pattern,text))
    if len(matches)!=1:
        raise RuntimeError("Expected one function block for "+tag)
    return matches[0]

def vg_js(text, ref):
    tag="CA_01_ExportHHVG"
    src=ref[block(ref,tag).start():block(ref,tag).end()]
    current=block(text,tag)
    return text[:current.start()]+src+text[current.end():]

def backend_methods(ref):
    first=ref.find("    private List<string> GetExportProductIds(")
    last=ref.find("    public bool IsReusable",first)
    if first<0 or last<first:
        raise RuntimeError("Missing Anco1 DHD export backend region")
    methods=ref[first:last].rstrip()+"\n"
    for term in ("GetExportDhdIds","DhdExportSql","BuildDhdExportWorkbook",
                 "ExportExcelHHVGDHD","CA_01_ExportHHVG",
                 "sp.trangthai = N'DHD'", "sp.vattu = 0",
                 "(sp.sanpham = 1 OR sp.ban_thanhpham = 1)"):
        if term not in methods:
            raise RuntimeError("Missing reference export contract")
    return methods

def vg_handler(text, ref):
    if "ExportExcelHHVGDHD(" in text:
        if "private List<string> GetExportProductIds(" not in text:
            raise RuntimeError("Partial DHD backend detected")
    else:
        if "private List<string> GetExportProductIds(" in text:
            raise RuntimeError("Unexpected existing export helper name")
        anchor=text.rfind("    public bool IsReusable")
        if anchor<0: raise RuntimeError("No handler insertion anchor")
        text=text[:anchor]+"\n"+backend_methods(ref)+"\n"+text[anchor:]
    case='case "CA_01_ExportHHVG":'
    if case not in text:
        anchor="            default:"
        if anchor not in text:
            raise RuntimeError("No handler dispatch anchor")
        text=text.replace(anchor, '            '+case+'\n                this.ExportExcelHHVGDHD(context);\n                break;\n'+anchor,1)
    if text.count(case)!=1 or text.count("this.ExportExcelHHVGDHD(context);")!=1:
        raise RuntimeError("Duplicate or mismatched DHD handler route")
    if "using System.Collections.Generic;" not in text:
        import_line="using System.IO;"
        if text.count(import_line)!=1:
            raise RuntimeError("Cannot add generics using")
        text=text.replace(import_line,import_line+"\nusing System.Collections.Generic;",1)
    return text

def patch(root, env):
    # Previous Azure merged PR #8 introduced the *wrong* general-module case.
    # Restore ONLY those two files to their exact pre-PR content, abort if either
    # file has been edited since PR #8. No other history or code is rewritten.
    for rev in (PREVIOUS_MASTER, PREVIOUS_MERGE):
        if not git_ok(["cat-file","-e",rev+"^{commit}"],cwd=root):
            git(["--config-env=http.extraheader=AZURE_GIT_HEADER","fetch","--quiet",
                 "--depth=1","origin",rev],cwd=root,env=env)
    for name in (HH_JS,HH_HANDLER):
        f=root/name
        if not f.is_file(): raise RuntimeError("Missing original general export path")
        original=git(["show",PREVIOUS_MASTER+":"+name],cwd=root,raw=True)
        known_merge=git(["show",PREVIOUS_MERGE+":"+name],cwd=root,raw=True)
        current=f.read_bytes()
        if current==original:
            print("GENERAL_MODULE=ALREADY_RESTORED; PATH="+name)
        elif current==known_merge:
            f.write_bytes(original)
            print("GENERAL_MODULE=RESTORED_LEGACY; PATH="+name)
        else:
            raise RuntimeError("General module changed since PR #8; safe restore aborted")
    for path, fn in ((VG_JS,vg_js),(VG_HANDLER,vg_handler)):
        f=root/path
        if not f.is_file(): raise RuntimeError("Missing DHD module source")
        text, encoding, newline, original=read_file(f)
        updated=fn(text,reference(path))
        if updated!=text: save(f,updated,encoding,newline)
    return len([x for x in ALLOWED if not git_ok(["diff","--quiet","--",x],cwd=root)])

def verify(root, env):
    for name in (HH_JS,HH_HANDLER):
        if (root/name).read_bytes()!=git(["show",PREVIOUS_MASTER+":"+name],cwd=root,raw=True):
            raise RuntimeError("General module not fully restored")
    js=read_file(root/VG_JS)[0]
    handler=read_file(root/VG_HANDLER)[0]
    general=read_file(root/HH_HANDLER)[0]
    draft=read_file(root/(ROOT+"Controller/JQGridModify/JQGridMD_00_DSHangHoa_SOANTHAOModify.ashx"))[0]
    jsblock=js[block(js,"CA_01_ExportHHVG").start():block(js,"CA_01_ExportHHVG").end()]
    with tempfile.NamedTemporaryFile(suffix=".js",mode="w",encoding="utf-8") as f:
        f.write(jsblock+"\n"); f.flush()
        result=subprocess.run(["node","--check",f.name],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if result.returncode: raise RuntimeError("DHD case JavaScript syntax failed")
    expected_ref=reference(VG_JS)
    expected_block=expected_ref[block(expected_ref,"CA_01_ExportHHVG").start():
                                block(expected_ref,"CA_01_ExportHHVG").end()]
    if jsblock!=expected_block: raise RuntimeError("DHD UI differs from confirmed Anco1 reference")
    if 'case "CA_01_ExportHHVG":' not in handler or handler.count("this.ExportExcelHHVGDHD(context);")!=1:
        raise RuntimeError("DHD case handler not routed")
    if "DhdExportSql" not in handler or "GetExportDhdIds" not in handler:
        raise RuntimeError("DHD export backend missing")
    if 'sp.trangthai = N\'DHD\'' not in handler or "sp.vattu = 0" not in handler:
        raise RuntimeError("DHD SQL eligibility missing")
    if "(sp.sanpham = 1 OR sp.ban_thanhpham = 1)" not in handler:
        raise RuntimeError("DHD product restriction missing")
    if "DhdExportHeaders" not in handler or "BuildDhdExportWorkbook" not in handler:
        raise RuntimeError("37-column workbook missing")
    if "GetGeneralExportProductIds" in general or "this.ExportExcelHH37(context)" in general:
        raise RuntimeError("Wrong general module export still present")
    if 'case "CA01ExportHHVG_MD00DSHangHoaSOANTHAO":' not in draft:
        raise RuntimeError("SOANTHAO export unexpectedly missing")
    expected_ref_handler=backend_methods(reference(VG_HANDLER))
    if expected_ref_handler not in handler:
        raise RuntimeError("DHD handler export differs from verified Anco1 source")
    changed=git(["diff","--name-only"],cwd=root).splitlines()
    if any(x not in ALLOWED for x in changed): raise RuntimeError("Changed unapproved Azure path")
    if not git_ok(["diff","--check"],cwd=root): raise RuntimeError("Git whitespace error")
    print("VERIFY=PASS; DHD_37_COLUMN=YES; GENERAL_RESTORED=YES; SOANTHAO_UNCHANGED=YES")
    print("AZURE_CHANGED_FILES="+str(len(changed)))
    for name in changed: print("AZURE_CHANGED_PATH="+name)
    return changed

def api_req(path,pat,method="GET",body=None):
    hdr={"Authorization":"Basic "+base64.b64encode((":"+pat).encode()).decode(),
         "Accept":"application/json"}
    data=None if body is None else json.dumps(body).encode()
    if data is not None: hdr["Content-Type"]="application/json"
    req=urllib.request.Request(API+path,headers=hdr,data=data,method=method)
    try:
        with urllib.request.urlopen(req,timeout=50) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError("Azure API error HTTP "+str(e.code)) from None

def main():
    mode=os.environ.get("RELOCATE_MODE","preview")
    if mode not in ("preview","apply"):
        raise RuntimeError("Invalid RELOCATE_MODE")
    pat=os.environ.get("AZURE_DEVOPS_PAT")
    if not pat: raise RuntimeError("Missing Azure DevOps PAT")
    env=os.environ.copy()
    env["AZURE_GIT_HEADER"]="AUTHORIZATION: Basic "+base64.b64encode((":"+pat).encode()).decode()
    with tempfile.TemporaryDirectory(prefix="anhiepluc-relocate-") as tmp:
        root=pathlib.Path(tmp)/"src"
        git(["--config-env=http.extraheader=AZURE_GIT_HEADER","clone",
             "--quiet","--depth=12",REMOTE,str(root)],env=env)
        base=git(["rev-parse","HEAD"],cwd=root)
        default=git(["branch","--show-current"],cwd=root)
        if default!="master": raise RuntimeError("Unexpected Azure default branch")
        print("AZURE_MASTER_BEFORE="+base)
        patch(root,env)
        changed=verify(root,env)
        if not changed:
            print("RESULT=NO_CHANGES_ALREADY_FIXED")
            return
        if mode=="preview":
            print("RESULT=PREVIEW_PASS; AZURE_UNCHANGED=YES")
            return
        # Fail safely if a same-named branch exists, rather than rewriting it.
        if git(["--config-env=http.extraheader=AZURE_GIT_HEADER","ls-remote","--heads","origin",BRANCH],cwd=root,env=env):
            raise RuntimeError("Azure work branch already exists; no force push")
        git(["checkout","-b",BRANCH],cwd=root)
        git(["config","user.name","AnHiepLuc Automation"],cwd=root)
        git(["config","user.email","37570235+ngocnhanvo@users.noreply.github.com"],cwd=root)
        git(["add","--"]+changed,cwd=root)
        git(["commit","-m","fix(products): move 37-column export to DSHangHoaVG; restore DSHangHoa"],cwd=root)
        sha=git(["rev-parse","HEAD"],cwd=root)
        git(["--config-env=http.extraheader=AZURE_GIT_HEADER","push",
             "origin","HEAD:refs/heads/"+BRANCH],cwd=root,env=env)
        print("AZURE_BRANCH_PUSH=PASS; AZURE_COMMIT="+sha)
        pr=api_req("/pullrequests?api-version=7.1",pat,"POST",{
            "sourceRefName":"refs/heads/"+BRANCH,
            "targetRefName":"refs/heads/master",
            "title":"Fix Excel export location: MD_00_DSHangHoaVG / CA_01_ExportHHVG",
            "description":"Restore MD_00_DSHangHoa CA_01_ExportHH exactly as before PR #8. "
                "Implement Anco1 DHD 37-column Excel in MD_00_DSHangHoaVG CA_01_ExportHHVG. "
                "Keep SOANTHAO untouched. Node syntax/static contract tests passed; "
                "runtime WebForms/SQL export still requires smoke testing."
        })
        print("AZURE_PR="+str(pr.get("pullRequestId")))
        print("RESULT=PR_CREATED; MASTER_NOT_CHANGED=YES")

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("RESULT=FAILED; DETAIL="+str(exc))
        sys.exit(1)
