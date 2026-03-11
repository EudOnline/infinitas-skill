#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 Feishu OpenAPI 发送图片或文件
"""

import argparse
import json
from pathlib import Path
import requests

OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
UPLOAD_IMAGE_URL = "https://open.feishu.cn/open-apis/im/v1/images"
UPLOAD_FILE_URL = "https://open.feishu.cn/open-apis/im/v1/files"
SEND_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


def load_app():
    cfg = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
    acc = cfg["channels"]["feishu"]["accounts"]["default"]
    return acc["appId"], acc["appSecret"]


def token(app_id, app_secret):
    r = requests.post(TOKEN_URL, json={"app_id": app_id, "app_secret": app_secret}, timeout=20)
    r.raise_for_status()
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(d)
    return d["tenant_access_token"]


def upload_image(tk: str, file_path: Path) -> str:
    with file_path.open("rb") as f:
        r = requests.post(
            UPLOAD_IMAGE_URL,
            headers={"Authorization": f"Bearer {tk}"},
            data={"image_type": "message"},
            files={"image": (file_path.name, f, "image/jpeg")},
            timeout=30,
        )
    r.raise_for_status()
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(d)
    return d["data"]["image_key"]


def upload_file(tk: str, file_path: Path) -> str:
    with file_path.open("rb") as f:
        r = requests.post(
            UPLOAD_FILE_URL,
            headers={"Authorization": f"Bearer {tk}"},
            data={"file_type": "stream", "file_name": file_path.name},
            files={"file": (file_path.name, f)},
            timeout=30,
        )
    r.raise_for_status()
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(d)
    return d["data"]["file_key"]


def send_image(tk: str, receive_id: str, receive_id_type: str, image_key: str):
    payload = {
        "receive_id": receive_id,
        "msg_type": "image",
        "content": json.dumps({"image_key": image_key}, ensure_ascii=False),
    }
    r = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json; charset=utf-8"},
        params={"receive_id_type": receive_id_type},
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(d)
    return d


def send_file(tk: str, receive_id: str, receive_id_type: str, file_key: str, file_name: str):
    payload = {
        "receive_id": receive_id,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key, "file_name": file_name}, ensure_ascii=False),
    }
    r = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json; charset=utf-8"},
        params={"receive_id_type": receive_id_type},
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(d)
    return d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--receive-id", required=True)
    parser.add_argument("--receive-id-type", default="open_id")
    parser.add_argument("--as-image", action="store_true")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    app_id, app_secret = load_app()
    tk = token(app_id, app_secret)

    if args.as_image:
        image_key = upload_image(tk, file_path)
        resp = send_image(tk, args.receive_id, args.receive_id_type, image_key)
    else:
        file_key = upload_file(tk, file_path)
        resp = send_file(tk, args.receive_id, args.receive_id_type, file_key, file_path.name)

    print(json.dumps(resp, ensure_ascii=False))


if __name__ == "__main__":
    main()
