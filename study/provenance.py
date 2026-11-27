import hashlib
import json


def panel_fingerprint(rows):
    payload = sorted(rows, key=lambda row: (str(row["code"]), row["year"]))
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()
