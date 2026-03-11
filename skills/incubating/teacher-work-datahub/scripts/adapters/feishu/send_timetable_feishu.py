#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一封装：发送课表到飞书，并稳定返回 JSON。

返回结构固定为：
{
  "success": bool,
  "method": "feishu_openapi",
  "message_id": str,
  "error": {"type": str, "message": str, "details": dict} | null,
  "file": str,
  "receive_id": str,
  "as_image": bool
}
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests

OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
UPLOAD_IMAGE_URL = "https://open.feishu.cn/open-apis/im/v1/images"
UPLOAD_FILE_URL = "https://open.feishu.cn/open-apis/im/v1/files"
SEND_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
METHOD_NAME = "feishu_openapi"


class SendError(Exception):
    def __init__(self, err_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.err_type = err_type
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.err_type,
            "message": self.message,
            "details": self.details,
        }


def normalize_file_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.absolute()


def build_result(
    *,
    success: bool,
    file_path: Path,
    receive_id: str,
    as_image: bool,
    message_id: str = "",
    error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": success,
        "method": METHOD_NAME,
        "message_id": message_id or "",
        "error": error,
        "file": str(file_path),
        "receive_id": receive_id,
        "as_image": bool(as_image),
    }


def load_app_credentials() -> tuple[str, str]:
    if not OPENCLAW_CONFIG.exists():
        raise SendError(
            "config_error",
            f"未找到 OpenClaw 配置文件：{OPENCLAW_CONFIG}",
            {"config": str(OPENCLAW_CONFIG)},
        )

    try:
        config = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
        account = config["channels"]["feishu"]["accounts"]["default"]
        app_id = account["appId"]
        app_secret = account["appSecret"]
    except Exception as exc:  # pragma: no cover - 防守式解析
        raise SendError(
            "config_error",
            "OpenClaw Feishu 配置解析失败",
            {"config": str(OPENCLAW_CONFIG), "exception": str(exc)},
        ) from exc

    if not app_id or not app_secret:
        raise SendError(
            "config_error",
            "OpenClaw Feishu 配置缺少 appId 或 appSecret",
            {"config": str(OPENCLAW_CONFIG)},
        )
    return app_id, app_secret


def parse_json_response(response: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def feishu_request(action: str, method: str, url: str, **kwargs) -> Dict[str, Any]:
    try:
        response = requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        raise SendError(
            "network_error",
            f"{action}请求失败：{exc}",
            {"action": action, "url": url},
        ) from exc

    body = parse_json_response(response)
    if response.status_code >= 400:
        raise SendError(
            "feishu_api_error",
            f"{action}失败：HTTP {response.status_code}",
            {
                "action": action,
                "http_status": response.status_code,
                "body": body if body is not None else response.text[:1000],
            },
        )
    if body is None:
        raise SendError(
            "invalid_response",
            f"{action}失败：响应不是合法 JSON",
            {
                "action": action,
                "http_status": response.status_code,
                "body_text": response.text[:1000],
            },
        )
    if body.get("code") != 0:
        raise SendError(
            "feishu_api_error",
            f"{action}失败：code={body.get('code')} msg={body.get('msg', '')}",
            {
                "action": action,
                "http_status": response.status_code,
                "body": body,
            },
        )
    return body


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    body = feishu_request(
        "获取 tenant_access_token",
        "POST",
        TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=20,
    )
    token = body.get("tenant_access_token", "")
    if not token:
        raise SendError(
            "invalid_response",
            "获取 tenant_access_token 失败：响应缺少 tenant_access_token",
            {"body": body},
        )
    return token


def upload_image(token: str, file_path: Path) -> str:
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    with file_path.open("rb") as file_obj:
        body = feishu_request(
            "上传图片",
            "POST",
            UPLOAD_IMAGE_URL,
            headers={"Authorization": f"Bearer {token}"},
            data={"image_type": "message"},
            files={"image": (file_path.name, file_obj, mime_type)},
            timeout=30,
        )
    image_key = body.get("data", {}).get("image_key", "")
    if not image_key:
        raise SendError(
            "invalid_response",
            "上传图片失败：响应缺少 image_key",
            {"body": body},
        )
    return image_key


def upload_file(token: str, file_path: Path) -> str:
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    with file_path.open("rb") as file_obj:
        body = feishu_request(
            "上传文件",
            "POST",
            UPLOAD_FILE_URL,
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": "stream", "file_name": file_path.name},
            files={"file": (file_path.name, file_obj, mime_type)},
            timeout=30,
        )
    file_key = body.get("data", {}).get("file_key", "")
    if not file_key:
        raise SendError(
            "invalid_response",
            "上传文件失败：响应缺少 file_key",
            {"body": body},
        )
    return file_key


def send_image(token: str, receive_id: str, receive_id_type: str, image_key: str) -> str:
    payload = {
        "receive_id": receive_id,
        "msg_type": "image",
        "content": json.dumps({"image_key": image_key}, ensure_ascii=False),
    }
    body = feishu_request(
        "发送图片消息",
        "POST",
        SEND_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        params={"receive_id_type": receive_id_type},
        json=payload,
        timeout=20,
    )
    message_id = body.get("data", {}).get("message_id", "")
    if not message_id:
        raise SendError(
            "invalid_response",
            "发送图片消息失败：响应缺少 message_id",
            {"body": body},
        )
    return message_id


def send_file(token: str, receive_id: str, receive_id_type: str, file_key: str, file_name: str) -> str:
    payload = {
        "receive_id": receive_id,
        "msg_type": "file",
        "content": json.dumps({"file_key": file_key, "file_name": file_name}, ensure_ascii=False),
    }
    body = feishu_request(
        "发送文件消息",
        "POST",
        SEND_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        params={"receive_id_type": receive_id_type},
        json=payload,
        timeout=20,
    )
    message_id = body.get("data", {}).get("message_id", "")
    if not message_id:
        raise SendError(
            "invalid_response",
            "发送文件消息失败：响应缺少 message_id",
            {"body": body},
        )
    return message_id


def send_timetable_file(
    file_path: str | Path,
    receive_id: str,
    receive_id_type: str = "open_id",
    as_image: bool = False,
) -> Dict[str, Any]:
    normalized_file = normalize_file_path(str(file_path))
    try:
        if not normalized_file.exists():
            raise SendError(
                "file_not_found",
                f"待发送文件不存在：{normalized_file}",
                {"file": str(normalized_file)},
            )
        if not normalized_file.is_file():
            raise SendError(
                "invalid_file",
                f"待发送路径不是文件：{normalized_file}",
                {"file": str(normalized_file)},
            )
        if not receive_id:
            raise SendError(
                "invalid_argument",
                "receive_id 不能为空",
                {"receive_id": receive_id, "receive_id_type": receive_id_type},
            )

        app_id, app_secret = load_app_credentials()
        tenant_token = get_tenant_access_token(app_id, app_secret)

        if as_image:
            media_key = upload_image(tenant_token, normalized_file)
            message_id = send_image(tenant_token, receive_id, receive_id_type, media_key)
        else:
            media_key = upload_file(tenant_token, normalized_file)
            message_id = send_file(tenant_token, receive_id, receive_id_type, media_key, normalized_file.name)

        return build_result(
            success=True,
            file_path=normalized_file,
            receive_id=receive_id,
            as_image=as_image,
            message_id=message_id,
            error=None,
        )
    except SendError as exc:
        return build_result(
            success=False,
            file_path=normalized_file,
            receive_id=receive_id,
            as_image=as_image,
            message_id="",
            error=exc.to_dict(),
        )
    except Exception as exc:  # pragma: no cover - 兜底
        return build_result(
            success=False,
            file_path=normalized_file,
            receive_id=receive_id,
            as_image=as_image,
            message_id="",
            error={
                "type": "unexpected_error",
                "message": str(exc),
                "details": {"exception_class": exc.__class__.__name__},
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--receive-id", required=True)
    parser.add_argument("--receive-id-type", default="open_id")
    parser.add_argument("--as-image", action="store_true")
    args = parser.parse_args()

    result = send_timetable_file(
        file_path=args.file,
        receive_id=args.receive_id,
        receive_id_type=args.receive_id_type,
        as_image=args.as_image,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
