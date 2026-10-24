#!/usr/bin/env python3
"""Port the exact public Anco1 37-column export case implementation into a private Azure clone.

Only paths explicitly listed below can change. Read-only preview by default.
Never print Azure source, diff, SQL, credentials, or remote Git errors to public Actions logs.
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

ORG = "vongocnhancd10cntt2"
PROJECT = "AnHiepLuc"
AZURE_REPO = "AnHiepLuc"
BASE_URL = "https://dev.azure.com/{}/{}/_git/{}".format(ORG, PROJECT, AZURE_REPO)
SOURCE_SHA = "e7d753c0d1e2c102ddb2315fb14cbfc8bc16e81e"
REF_BASE = "https://raw.githubusercontent.com/ngocnhanvo/anco1/{}/".format(SOURCE_SHA)
BRANCH = "ai/export-hh-37-column-20261024"
ST_JS = "eman_ver3/js/Module_script/MD_00_DSHangHoa_SOANTHAO.js"
HH_JS = "eman_ver3/js/Module_script/MD_00_DSHangHoa.js"
ST_HANDLER = "eman_ver3/Controller/JQGridModify/JQGridMD_00_DSHangHoa_SOANTHAOModify.ashx"
HH_HANDLER = "eman_ver3/Controller/JQGridModify/JQGridMD_00_DSHangHoaModify.ashx"
VG_JS = "eman_ver3/js/Module_script/MD_00_DSHangHoaVG.js"
VG_HANDLER = "eman_ver3/Controller/JQGridModify/JQGridMD_00_DSHangHoaVGModify.ashx"

def git(args, cwd=None, env=None):
    p = subprocess.run(["git"] + args, cwd=cwd, env=env, capture_output=True)
    if p.returncode:
        raise RuntimeError("Git operation failed (stderr suppressed)")
    return p.stdout.decode("utf-8", "replace").strip()

def reference(path):
    url = REF_BASE + path
    with urllib.request.urlopen(url, timeout=45) as reply:
        return reply.read().decode("utf-8-sig")

def read_target(path):
    raw = path.read_bytes()
    if raw.startswith(codecs.BOM_UTF16_LE):
        encoding = "utf-16"
    elif raw.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif raw[:512].count(b"\x00") > 20:
        encoding = "utf-16-le"
    else:
        try:
            raw.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            encoding = "cp1258"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        raise RuntimeError("Unrecognized source encoding: " + path.name)
    newline = "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"
    return text.replace("\r\n", "\n"), encoding, newline, raw

def write_target(path, content, encoding, newline):
    content = content.replace("\r\n", "\n").replace("\n", newline)
    path.write_bytes(content.encode(encoding))

def extract_js_block(content, case):
    pattern = r"(?ms)^[ \t]*//start " + re.escape(case) + r"[ \t]*\r?\n.*?^[ \t]*//end " + re.escape(case) + r"[ \t]*"
    matches = list(re.finditer(pattern, content))
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one Anco1 JS block for " + case)
    return matches[0].group(0).strip("\r\n")

def add_st_js(target, ref):
    case = "CA01ExportHHVG_MD00DSHangHoaSOANTHAO"
    block = extract_js_block(ref, case)
    if case in target:
        matches = list(re.finditer(r"(?ms)^[ \t]*//start " + re.escape(case) + r"[ \t]*\n.*?^[ \t]*//end " + re.escape(case) + r"[ \t]*", target))
        if len(matches) != 1:
            raise RuntimeError("Existing draft case lacks expected section delimiters")
        return target[:matches[0].start()] + block + target[matches[0].end():]
    anchor = "//end CA01ImportHHVG_MD00DSHangHoaSOANTHAO"
    if anchor in target:
        pos = target.index(anchor) + len(anchor)
    else:
        pos = target.find("\n") + 1
    return target[:pos] + "\n\n" + block + "\n" + target[pos:]

def add_general_js(target, reference_vg):
    block = extract_js_block(reference_vg, "CA_01_ExportHHVG")
    substitutions = {
        "CA_01_ExportHHVG": "CA_01_ExportHH",
        "MD_00_DSHangHoaVG": "MD_00_DSHangHoa",
        "JQGridMD_00_DSHangHoaVGModify.ashx": "JQGridMD_00_DSHangHoaModify.ashx",
        "dlg_ExportHHVG_VG": "dlg_ExportHH_AnHiepLuc",
        "btn-export-hhvg": "btn-export-hh",
        "btn-close-export-hhvg": "btn-close-export-hh",
        "Số hàng hóa DHD theo bộ lọc": "Số hàng hóa theo bộ lọc",
    }
    for a, b in substitutions.items():
        block = block.replace(a, b)
    case = "CA_01_ExportHH"
    matches = list(re.finditer(r"(?ms)^[ \t]*//start " + case + r"[ \t]*\n.*?^[ \t]*//end " + case + r"[ \t]*", target))
    if len(matches) != 1:
        raise RuntimeError("Existing general case markers not unique")
    return target[:matches[0].start()] + block + target[matches[0].end():]

def export_methods(full):
    begin = full.find("    private List<string> GetExportProductIds(")
    end = full.find("    public bool IsReusable", begin)
    if begin == -1 or end == -1 or begin >= end:
        raise RuntimeError("Reference backend export region not found")
    return full[begin:end].rstrip() + "\n"

def add_using(text):
    if "using System.Collections.Generic;" in text:
        return text
    pattern = r"(?m)^using System\.IO;[ \t]*$"
    if len(re.findall(pattern, text)) != 1:
        raise RuntimeError("Could not insert System.Collections.Generic")
    return re.sub(pattern, "using System.IO;\nusing System.Collections.Generic;", text, count=1)

def insert_methods(text, methods):
    anchor = text.rfind("    public bool IsReusable")
    if anchor < 0:
        raise RuntimeError("IsReusable anchor not found")
    return text[:anchor] + "\n" + methods + "\n" + text[anchor:]

def add_st_handler(target, ref):
    case = "CA01ExportHHVG_MD00DSHangHoaSOANTHAO"
    if "private List<string> GetExportProductIds(" not in target:
        target = insert_methods(target, export_methods(ref))
    elif "ExportExcelHHVGSOANTHAO(" not in target:
        raise RuntimeError("Conflicting partial draft export in target")
    if 'case "' + case + '"' not in target:
        anchor = '            case "CA01ImportHHVG_MD00DSHangHoaSOANTHAO":'
        if anchor in target:
            before = target.index(anchor)
        else:
            before = target.index("            default:")
        target = target[:before] + '            case "' + case + '":\n                this.ExportExcelHHVGSOANTHAO(context);\n                break;\n' + target[before:]
    target = add_using(target)
    return target

def general_methods(ref):
    methods = export_methods(ref)
    method_names = {
        "GetExportProductIds": "GetGeneralExportProductIds",
        "GetExportDhdIds": "GetGeneralExportIds",
        "GetExportSnapshot": "GetGeneralExportSnapshot",
        "DhdExportHeaders": "GeneralExportHeaders",
        "DhdExportWidths": "GeneralExportWidths",
        "DhdExportSql": "GeneralExportSql",
        "LoadDhdExportRows": "LoadGeneralExportRows",
        "BuildDhdExportWorkbook": "BuildGeneralExportWorkbook",
        "ExportExcelHHVGDHD": "ExportExcelHH37",
        "MD_00_DSHangHoaVG": "MD_00_DSHangHoa",
        "CA_01_ExportHHVG": "CA_01_ExportHH"
    }
    for old, new in method_names.items():
        methods = methods.replace(old, new)
    eligibility = re.compile(r"(?s)    private List<string> GetGeneralExportIds\(List<string> ids\).*?(?=    private static string GetGeneralExportSnapshot)")
    replacement = ("    // General product list: preserve all module- and role-authorized IDs, not only DHD.\n"
                   "    private List<string> GetGeneralExportIds(List<string> ids)\n"
                   "    {\n"
                   "        return ids;\n"
                   "    }\n\n")
    methods, count = eligibility.subn(lambda _:replacement, methods, count=1)
    if count != 1:
        raise RuntimeError("Cannot adapt general eligibility")
    restricted_sql = re.compile(
        r"WHERE sp\.vattu = 0\s+AND \(sp\.sanpham = 1 OR sp\.ban_thanhpham = 1\)\s+"
        r"AND sp\.trangthai = N'DHD'\s+AND sp\.md_sanpham_id IN")
    methods, count = restricted_sql.subn("WHERE sp.md_sanpham_id IN", methods, count=1)
    if count != 1:
        raise RuntimeError("Cannot adapt general SQL status conditions")
    methods = methods.replace("Không có hàng hóa Đã hiệu lực nào khớp bộ lọc.",
                              "Không có hàng hóa nào khớp bộ lọc.")
    return methods

def add_general_handler(target, ref):
    # Keep legacy export helpers untouched for rollback; only re-route the active case.
    if "GetGeneralExportProductIds(" not in target:
        target = insert_methods(target, general_methods(ref))
    pattern = r'(?s)(case "CA_01_ExportHH":[ \t]*\n[ \t]*this\.)CA_01_ExportHH\(context\);'
    target, count = re.subn(pattern, r"\g<1>ExportExcelHH37(context);", target, count=1)
    if count == 0 and "this.ExportExcelHH37(context);" not in target:
        raise RuntimeError("Existing general dispatch is not recognizable")
    target = add_using(target)
    return target

def static_tests(root):
    js = [ST_JS, HH_JS]
    for name in js:
        text, _, _, _ = read_target(root/name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8") as tmp:
            tmp.write(text)
            tmp.flush()
            proc = subprocess.run(["node", "--check", tmp.name], capture_output=True)
        if proc.returncode:
            raise RuntimeError("JavaScript parse failed: " + name)
    st = read_target(root/ST_HANDLER)[0]
    hh = read_target(root/HH_HANDLER)[0]
    js_st = read_target(root/ST_JS)[0]
    js_hh = read_target(root/HH_JS)[0]
    requirements = [
        (st.count('case "CA01ExportHHVG_MD00DSHangHoaSOANTHAO"')==1, "ST route"),
        (st.count("private List<string> GetExportProductIds(")==1, "ST scoped export filter"),
        (st.count("DraftExportSql") >= 2, "ST SQL"),
        (st.count("/*EXPORT_FILTER_IDS*/")>=1, "ST parameterized query"),
        (hh.count('case "CA_01_ExportHH"')==1, "HH route"),
        (hh.count("private List<string> GetGeneralExportProductIds(")==1, "HH scoped export filter"),
        ("GetGeneralExportIds" in hh, "HH eligible rows"),
        ("GeneralExportSql" in hh and "/*EXPORT_FILTER_IDS*/" in hh, "HH parameterized query"),
        ("ExportExcelHH37(context)" in hh, "HH dispatch"),
        ("function CA01ExportHHVG_MD00DSHangHoaSOANTHAO(" in js_st, "ST UI"),
        ("function CA_01_ExportHH(" in js_hh and "snapshot: snapshot" in js_hh, "HH UI"),
        ("modify_code(" not in extract_js_block(js_hh, "CA_01_ExportHH"), "No obsolete session export"),
    ]
    for value, label in requirements:
        if not value:
            raise RuntimeError("Static check failed: " + label)
    print("STATIC_TESTS=PASS; JS=2; SERVER_ROUTING=2; DOWNLOAD=POST; NO_SOURCE_EXPOSED=YES")

def main():
    mode = os.environ.get("PORT_MODE", "preview")
    if mode not in ("preview", "apply"):
        raise RuntimeError("Invalid port mode")
    pat = os.environ.get("AZURE_DEVOPS_PAT")
    if not pat:
        raise RuntimeError("Missing Azure DevOps PAT")
    env = os.environ.copy()
    env["AZURE_GIT_HEADER"] = "AUTHORIZATION: Basic " + base64.b64encode((":"+pat).encode()).decode()
    with tempfile.TemporaryDirectory(prefix="anhiepluc-port-") as temp:
        root = pathlib.Path(temp)/"azure"
        git(["--config-env=http.extraheader=AZURE_GIT_HEADER",
             "clone", "--quiet", "--depth=1", BASE_URL, str(root)], env=env)
        parent = git(["rev-parse", "HEAD"], cwd=root)
        default_branch = git(["branch", "--show-current"], cwd=root)
        if default_branch != "master":
            raise RuntimeError("Expected Azure master (branch protection)")
        refs = {
            ST_JS: reference(ST_JS),
            VG_JS: reference(VG_JS),
            ST_HANDLER: reference(ST_HANDLER),
            VG_HANDLER: reference(VG_HANDLER)
        }
        operations = [
            (ST_JS, add_st_js, refs[ST_JS]),
            (HH_JS, add_general_js, refs[VG_JS]),
            (ST_HANDLER, add_st_handler, refs[ST_HANDLER]),
            (HH_HANDLER, add_general_handler, refs[VG_HANDLER]),
        ]
        touched=[]
        for name, fn, ref in operations:
            path=root/name
            if not path.is_file():
                raise RuntimeError("Missing Azure target path: " + name)
            content, encoding, newline, original = read_target(path)
            updated = fn(content, ref)
            if updated != content:
                write_target(path, updated, encoding, newline)
                touched.append(name)
            # Even pre-existing source gets tested.
        static_tests(root)
        changes = git(["diff", "--name-only"], cwd=root).splitlines()
        if sorted(changes) != sorted(touched):
            raise RuntimeError("Unexpected changed path set; abort")
        print("AZURE_PARENT_SHA="+parent)
        print("AZURE_BASE_BRANCH="+default_branch)
        print("CHANGED_FILES="+str(len(changes)))
        for item in changes:
            print("CHANGED_PATH="+item)
        if mode == "preview":
            print("PORT_RESULT=PREVIEW_PASS; AZURE_UNCHANGED=YES")
            return
        if not changes:
            print("PORT_RESULT=ALREADY_CURRENT; AZURE_UNCHANGED=YES")
            return
        git(["checkout","-b",BRANCH],cwd=root)
        git(["config","user.name","AnHiepLuc Automation"],cwd=root)
        git(["config","user.email","37570235+ngocnhanvo@users.noreply.github.com"],cwd=root)
        git(["add","--"] + changes,cwd=root)
        git(["commit","-m","feat(products): align 37-column Excel exports with Anco1"],cwd=root)
        commit = git(["rev-parse","HEAD"],cwd=root)
        git(["--config-env=http.extraheader=AZURE_GIT_HEADER",
             "push","origin","HEAD:refs/heads/"+BRANCH],cwd=root,env=env)
        api = "https://dev.azure.com/{}/{}/_apis/git/repositories/{}/pullrequests?api-version=7.1".format(
            ORG, PROJECT, AZURE_REPO)
        payload = json.dumps({
            "sourceRefName":"refs/heads/"+BRANCH,
            "targetRefName":"refs/heads/"+default_branch,
            "title":"Port Excel 37-column exports: SOANTHAO and MD_00_DSHangHoa",
            "description":"Mirror verified Anco1 UI preview/download and NPOI 37-column workbook. "
                          "SOANTHAO retains SOANTHAO eligibility; general product list retains "
                          "module and role authorized rows. No changes to Anco1 or GitHub application sources. "
                          "Static JavaScript and handler contract checks passed. Runtime SQL and workbook "
                          "download on AnHiepLuc must be verified before production merge."
        }).encode()
        req = urllib.request.Request(api, data=payload, method="POST", headers={
            "Authorization": "Basic " + base64.b64encode((":"+pat).encode()).decode(),
            "Content-Type":"application/json",
            "Accept":"application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                pr = json.load(resp)
        except Exception:
            print("AZURE_PUSH=PASS; AZURE_PR=NOT_CONFIRMED; REVIEW_BRANCH="+BRANCH)
            print("AZURE_COMMIT="+commit)
            raise RuntimeError("Azure PR creation failed after successful push; no production merge occurred")
        print("AZURE_PUSH=PASS; AZURE_COMMIT="+commit)
        print("AZURE_PR_ID="+str(pr.get("pullRequestId","unknown")))
        print("PORT_RESULT=PR_OPEN; MASTER_NOT_MODIFIED=YES")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print("PORT_RESULT=FAILED; ERROR="+str(ex))
        sys.exit(1)
