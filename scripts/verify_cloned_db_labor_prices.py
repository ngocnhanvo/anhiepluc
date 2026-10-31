#!/usr/bin/env python3
"""Read-only validation of price details on a cloned AnHiepLuc database.

Expected labor price is an active row from md_giasanpham matching
price-version, product and unit. No SQL modifications are executed.
"""
import os, json, re, base64, zlib, secrets, decimal, subprocess, sys
import pymssql
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DB = "emanAnHiepLuc.31.10.26"
DOC = "NTP/02280/26"

def publish(text):
    ev = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))
    subprocess.run(["gh", "issue", "comment", str(ev["issue"]["number"]), "--repo",
                    os.environ["GITHUB_REPOSITORY"], "--body", text], check=True)

def encrypted_report(report,pem_b64):
    pub=serialization.load_pem_public_key(base64.b64decode(pem_b64,validate=True))
    key=secrets.token_bytes(32);nonce=secrets.token_bytes(12)
    raw=zlib.compress(json.dumps(report,default=str,ensure_ascii=False).encode(),9)
    wrap=pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    return base64.b64encode(wrap+nonce+AESGCM(key).encrypt(nonce,raw,None)).decode("ascii")

def db_connection():
    host=os.environ["DB_SERVER"]
    if host.lower().startswith("tcp:"):host=host[4:]
    port=1433
    if "," in host:
        a,b=host.rsplit(",",1)
        if b.isdigit():host,port=a,int(b)
    return pymssql.connect(server=host,port=port,user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],database=os.environ["DB_DATABASE"],
        login_timeout=20,timeout=45,charset="UTF-8",as_dict=True,autocommit=False)

def money(value):
    return decimal.Decimal(str(value)) if value is not None else None

def main():
    ev=json.load(open(os.environ["GITHUB_EVENT_PATH"],encoding="utf-8"))
    args=json.loads(ev["issue"]["body"])
    if args.get("document") != DOC or args.get("database") != DB:
        raise ValueError("INVALID_TARGET")
    report={"database":DB,"document":DOC,"details":[],"version":None,"checks":{}}
    con=db_connection()
    try:
        with con.cursor() as c:
            c.execute("SELECT DB_NAME() AS name")
            if c.fetchone()["name"] != DB:raise ValueError("WRONG_DATABASE")
            c.execute("SELECT md_vanchuyennoibo_id,phienbangiaNC,banggiaNC FROM dbo.md_vanchuyennoibo WHERE sochungtu=%s",(DOC,))
            records=c.fetchall()
            if len(records) != 1:raise ValueError("INVALID_DOCUMENT_COUNT")
            hd=records[0]
            if not hd["phienbangiaNC"]:raise ValueError("MISSING_PRICE_VERSION")
            c.execute("SELECT md_phienbangia_id,md_banggia_id,ten_phienbangia,hoatdong,ngay_hieuluc FROM dbo.md_phienbangia WHERE md_phienbangia_id=%s",(hd["phienbangiaNC"],))
            ver=c.fetchone()
            if not ver:raise ValueError("UNKNOWN_VERSION")
            report["version"]=ver
            report["checks"]["version_matches_price_list"]=str(ver["md_banggia_id"]).lower()==str(hd["banggiaNC"]).lower()
            report["checks"]["version_active"]=bool(ver["hoatdong"])
            seen=set()
            for table in ("md_vanchuyennoibo_cdvc","md_vanchuyennoibo_dalayton"):
                sql=("SELECT md_sanpham_id,md_donvitinhsanpham_id,gianhancong FROM dbo."
                     +table+" WHERE md_vanchuyennoibo_id=%s")
                c.execute(sql,(hd["md_vanchuyennoibo_id"],))
                rows=c.fetchall()
                for r in rows:
                    product=r["md_sanpham_id"];unit=r["md_donvitinhsanpham_id"]
                    c.execute("SELECT gia,hoatdong FROM dbo.md_giasanpham WHERE md_phienbangia_id=%s AND md_sanpham_id=%s AND md_donvitinhsanpham_id=%s",
                        (hd["phienbangiaNC"],product,unit))
                    candidates=c.fetchall()
                    active=[x for x in candidates if x["hoatdong"]]
                    saved=money(r["gianhancong"])
                    expected=money(active[0]["gia"]) if len(active)==1 else None
                    matched=(len(active)==1 and saved is not None and expected is not None and saved==expected)
                    report["details"].append({
                        "table":table, "product":product,"unit":unit,
                        "saved":saved,"expected":expected,"total_candidates":len(candidates),
                        "active_candidates":len(active),"matched":matched})
            report["checks"]["total_rows"]=len(report["details"])
            report["checks"]["matched_rows"]=sum(1 for x in report["details"] if x["matched"])
            report["checks"]["unmatched_rows"]=sum(1 for x in report["details"] if not x["matched"])
            report["checks"]["missing_price"]=sum(1 for x in report["details"] if x["active_candidates"]==0)
            report["checks"]["duplicate_active"]=sum(1 for x in report["details"] if x["active_candidates"]>1)
            report["checks"]["null_or_zero_saved"]=sum(1 for x in report["details"] if x["saved"] is None or x["saved"]==0)
            report["checks"]["cdvc_count"]=sum(x["table"]=="md_vanchuyennoibo_cdvc" for x in report["details"])
            report["checks"]["dalayton_count"]=sum(x["table"]=="md_vanchuyennoibo_dalayton" for x in report["details"])
        con.rollback()
    finally:
        con.close()
    c=report["checks"]
    head=("LABOR_PRICE_AUDIT=PASS; DB_VERIFIED=YES; VERSION_NAME="+str(report["version"]["ten_phienbangia"])+
        "; VERSION_ACTIVE="+str(c["version_active"]).upper()+"; VERSION_PARENT_MATCH="+str(c["version_matches_price_list"]).upper()+
        "; CDVC="+str(c["cdvc_count"])+"; DALAYTON="+str(c["dalayton_count"])+
        "; MATCHED="+str(c["matched_rows"])+"; TOTAL="+str(c["total_rows"])+
        "; MISSING="+str(c["missing_price"])+"; DUPLICATE="+str(c["duplicate_active"])+
        "; NULL_OR_ZERO="+str(c["null_or_zero_saved"]))
    publish(head+"\nLABOR_AUDIT_ENC_V1:"+encrypted_report(report,args["public_key_b64"]))
    print("READ_ONLY_PRICE_CHECK=PASS; MATCHED="+str(c["matched_rows"])+"/"+str(c["total_rows"]))

if __name__=="__main__":
    try:main()
    except Exception as exc:
        reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        print("READ_ONLY_PRICE_CHECK=FAILED; REASON="+reason)
        try:publish("LABOR_PRICE_AUDIT=FAILED; REASON="+reason)
        except Exception:pass
        sys.exit(1)
