#!/usr/bin/env python3
"""Read-only, parameterized SQL table explorer for AnHiepLuc."""
import base64
import datetime
import decimal
import json
import os
import re
import secrets
import subprocess
import sys
import zlib

import pymssql
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


def public_comment(message):
    issue = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))["issue"]
    subprocess.run(["gh", "issue", "comment", str(issue["number"]), "--repo", os.environ["GITHUB_REPOSITORY"], "--body", message], check=True)


def encrypt(payload, encoded_key):
    public_key = serialization.load_pem_public_key(base64.b64decode(encoded_key, validate=True))
    aes_key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    compressed = zlib.compress(json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"), 9)
    encrypted_key = public_key.encrypt(aes_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    ciphertext = AESGCM(aes_key).encrypt(nonce, compressed, None)
    return base64.b64encode(encrypted_key + nonce + ciphertext).decode("ascii")


def run():
    issue = json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8"))["issue"]
    payload = json.loads(issue["body"])
    if payload.get("operation") == "price_chain":
        doc = payload.get("document")
        if not isinstance(doc, str) or not re.fullmatch(r"NTP/[0-9]{5}/[0-9]{2}", doc):
            raise ValueError("INVALID_DOCUMENT")
        host = os.environ["DB_SERVER"].removeprefix("tcp:")
        port = 1433
        if "," in host:
            a, b = host.rsplit(",", 1)
            if b.isdigit(): host, port = a, int(b)
        con = pymssql.connect(server=host, port=port, user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_DATABASE"], login_timeout=20, timeout=30, charset="UTF-8", autocommit=False, as_dict=True)
        try:
            with con.cursor() as cur:
                cur.execute("SELECT TOP (2) * FROM dbo.md_vanchuyennoibo WHERE sochungtu=%s", (doc,))
                receipts = cur.fetchall()
                prices = []
                versions = []
                if receipts and receipts[0].get("banggiaNC"):
                    bg = receipts[0]["banggiaNC"]
                    cur.execute("SELECT TOP (5) * FROM dbo.md_banggia WHERE md_banggia_id=%s", (bg,))
                    prices = cur.fetchall()
                    cur.execute("SELECT TOP (50) * FROM dbo.md_phienbangia WHERE md_banggia_id=%s ORDER BY ngay_hieuluc DESC", (bg,))
                    versions = cur.fetchall()
                result={"database":os.environ["DB_DATABASE"],"receipt":receipts,"price_list":prices,"versions":versions}
            con.rollback()
        finally:
            con.close()
        ciphertext=encrypt(result,payload["public_key_b64"])
        public_comment("SQL_PRICE_CHAIN=PASS; DOCUMENT_COUNT="+str(len(receipts))+"; PRICE_LIST_COUNT="+str(len(prices))+"; VERSION_COUNT="+str(len(versions))+"\nQUERY_RESULT_ENC_V1:"+ciphertext)
        print("SQL_PRICE_CHAIN=PASS; READ_ONLY=YES")
        return
    if payload.get("operation") == "catalog":
        pattern = payload.get("pattern", "kho")
        if not isinstance(pattern, str) or not re.fullmatch(r"[A-Za-z_]{1,40}", pattern):
            raise ValueError("INVALID_CATALOG_PATTERN")
        host = os.environ["DB_SERVER"]
        if host.lower().startswith("tcp:"):
            host = host[4:]
        port = 1433
        if "," in host:
            a, b = host.rsplit(",", 1)
            if b.isdigit():
                host, port = a, int(b)
        conn = pymssql.connect(server=host, port=port, user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_DATABASE"], login_timeout=20, timeout=30, charset="UTF-8", autocommit=False, as_dict=True)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DB_NAME() AS dbname")
                dbname = cur.fetchone()["dbname"]
                cur.execute("SELECT TOP (100) s.name AS schema_name, t.name AS table_name FROM sys.tables t INNER JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE t.name LIKE %s ORDER BY t.name", ("%" + pattern + "%",))
                tables = cur.fetchall()
                cur.execute("SELECT HAS_DBACCESS(DB_NAME()) AS has_db_access")
                dbaccess = cur.fetchone()["has_db_access"]
            conn.rollback()
        finally:
            conn.close()
        report = {"dbname": dbname, "pattern": pattern, "matching_tables": tables, "has_db_access": dbaccess}
        encrypted = encrypt(report, payload["public_key_b64"])
        public_comment("SQL_CATALOG=PASS; MATCHING_TABLES=" + str(len(tables)) + "\nQUERY_RESULT_ENC_V1:" + encrypted)
        print("SQL_CATALOG=PASS; READ_ONLY=YES")
        return
    if set(payload) - {"table", "schema", "where", "max_rows", "public_key_b64"}:
        raise ValueError("INVALID_REQUEST_FIELDS")
    table = payload["table"]
    schema = payload.get("schema", "dbo")
    where = payload.get("where", {})
    limit = payload.get("max_rows", 5)
    if not isinstance(table, str) or not IDENT.fullmatch(table):
        raise ValueError("INVALID_TABLE")
    if not isinstance(schema, str) or not IDENT.fullmatch(schema):
        raise ValueError("INVALID_SCHEMA")
    if not isinstance(where, dict) or len(where) > 8 or not where:
        raise ValueError("INVALID_FILTER")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("INVALID_LIMIT")
    for key, value in where.items():
        if not isinstance(key, str) or not IDENT.fullmatch(key):
            raise ValueError("INVALID_COLUMN")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError("INVALID_FILTER_VALUE")
    public_key_b64 = payload["public_key_b64"]

    host = os.environ["DB_SERVER"]
    if host.lower().startswith("tcp:"):
        host = host[4:]
    port = 1433
    if "," in host:
        a, b = host.rsplit(",", 1)
        if b.isdigit():
            host, port = a, int(b)
    db = pymssql.connect(server=host, port=port, user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_DATABASE"], login_timeout=20, timeout=30, charset="UTF-8", autocommit=False, as_dict=True)
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION", (schema, table))
            columns = [r["COLUMN_NAME"] for r in cursor.fetchall()]
            if not columns:
                raise ValueError("TABLE_NOT_FOUND_OR_NO_PERMISSION")
            actual = {c.casefold(): c for c in columns}
            if any(k.casefold() not in actual for k in where):
                raise ValueError("FILTER_COLUMN_NOT_FOUND")
            filters = []
            values = []
            for key, value in where.items():
                name = actual[key.casefold()]
                if value is None:
                    filters.append("[" + name + "] IS NULL")
                else:
                    filters.append("[" + name + "]=%s")
                    values.append(value)
            expr = " AND ".join(filters)
            target = "[" + schema + "].[" + table + "]"
            cursor.execute("SELECT COUNT_BIG(*) AS n FROM " + target + " WHERE " + expr, tuple(values))
            count = cursor.fetchone()["n"]
            cursor.execute("SELECT TOP (" + str(limit) + ") * FROM " + target + " WHERE " + expr, tuple(values))
            rows = cursor.fetchall()
            result = {"database": os.environ["DB_DATABASE"], "schema": schema, "table": table, "filter": where, "total": count, "columns": columns, "rows": rows}
        db.rollback()
    finally:
        db.close()
    ciphertext = encrypt(result, public_key_b64)
    public_comment("SQL_READONLY=PASS; MATCH_COUNT=" + str(count) + "; ROWS_ENCRYPTED=" + str(len(rows)) + "\nQUERY_RESULT_ENC_V1:" + ciphertext)
    print("SQL_READONLY=PASS; MATCH_COUNT=" + str(count) + "; READ_ONLY=YES")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        error = str(e) if isinstance(e, ValueError) else type(e).__name__
        print("SQL_READONLY=FAIL; REASON=" + error)
        try:
            public_comment("SQL_READONLY=FAIL; REASON=" + error)
        except Exception:
            pass
        sys.exit(1)
