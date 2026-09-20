"""Cisco EoX 客户端 —— 按型号批量查生命周期（停止销售 / 停止支持）。

为什么单独一个模块：外部 HTTP + OAuth 的细节不该混进 API 层；也让"未配凭据"
这条路径可以被单独测试（**返回可读原因，而不是抛异常** —— 手工登记永远是可用路径）。

凭据走环境变量（与 LLM key 同模式，绝不落盘）：
    CISCO_API_CLIENT_ID / CISCO_API_CLIENT_SECRET
可选覆盖（自建代理或 Cisco 换域名时用）：
    CISCO_EOX_TOKEN_URL（默认 id.cisco.com）/ CISCO_EOX_API_BASE（默认 apix.cisco.com）

⚠️ 诚实标注：凭据到位前**无法实盘验证**；解析逻辑用官方文档的响应结构做单元测试
（mock session），拿到凭据当天即可实跑。
"""
from __future__ import annotations

import os

import requests

TOKEN_URL = os.environ.get("CISCO_EOX_TOKEN_URL", "https://id.cisco.com/oauth2/default/v1/token")
API_BASE = os.environ.get("CISCO_EOX_API_BASE", "https://apix.cisco.com/supporttools/eox/rest")
API_VERSION = "5"
CHUNK = 20          # EOXByProductID 每次最多 20 个 PID


def credentials_configured() -> bool:
    return bool(os.environ.get("CISCO_API_CLIENT_ID") and os.environ.get("CISCO_API_CLIENT_SECRET"))


def status() -> dict:
    """刷新可用性（API 层据此给前端可读提示）。"""
    if credentials_configured():
        return {"available": True, "reason": ""}
    return {"available": False,
            "reason": "未配置 Cisco API 凭据（环境变量 CISCO_API_CLIENT_ID / "
                      "CISCO_API_CLIENT_SECRET）—— 可先手工登记，凭据到位后点「刷新」即可自动拉取"}


def _get_token(session, timeout: int = 30) -> str:
    resp = session.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(os.environ.get("CISCO_API_CLIENT_ID", ""),
              os.environ.get("CISCO_API_CLIENT_SECRET", "")),
        timeout=timeout)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _parse_record(rec: dict) -> dict:
    """拍平一条 EoX 记录（日期在 {"value": ...} 里）。"""
    def dv(key: str) -> str:
        v = rec.get(key)
        if isinstance(v, dict):
            return str(v.get("value") or "")
        return str(v or "")

    return {
        "product_id": str(rec.get("EOLProductID") or ""),
        "description": str(rec.get("ProductIDDescription") or ""),
        "end_of_sale": dv("EndOfSaleDate"),
        "end_of_support": dv("LastDateOfSupport"),
        "announcement": dv("EOXExternalAnnouncementDate"),
        "bulletin": str(rec.get("ProductBulletinNumber") or ""),
        "bulletin_url": str(rec.get("LinkToProductBulletinURL") or ""),
    }


def lookup_product_ids(product_ids: list[str], session=None, timeout: int = 30) -> dict[str, list[dict]]:
    """按型号（PID）查 EoX。返回 {PID: [记录…]}；未公告 / 查不到 → 空列表。

    型号按 20 个一批（API 上限）；某批无记录时 Cisco 返回 404 + 空体，**不是错误**。
    """
    ids = [p.strip() for p in product_ids if p and p.strip()]
    if not ids:
        return {}
    session = session or requests.Session()
    token = _get_token(session, timeout)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    out: dict[str, list[dict]] = {p: [] for p in ids}
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        url = f"{API_BASE}/{API_VERSION}/EOXByProductID/1/{','.join(chunk)}"
        resp = session.get(url, headers=headers,
                           params={"responseencoding": "json"}, timeout=timeout)
        if resp.status_code == 404:
            continue                       # 这一批都没有 EoX 记录 —— 保持空列表
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):         # 个别版本包了一层数组
            data = data[0] if data else {}
        for rec in data.get("EOXRecord", []) or []:
            parsed = _parse_record(rec)
            # 用输入值归位（同一 PID 可能有多条迁移路径记录）
            key = str(rec.get("EOXInputValue") or parsed["product_id"] or "").strip()
            if key in out:
                out[key].append(parsed)
            elif parsed["product_id"] in out:
                out[parsed["product_id"]].append(parsed)
    return out


def refresh_models(conn, models: list[str], *, force: bool = False) -> dict:
    """查 Cisco EoX 并写库。返回 {updated, skipped_manual, not_announced, errors}。

    - **查不到 / 未公告不算错误**（大多数在役设备本来就没公告），也不写库
      —— 免得把"没公告"存成一条空记录，让"未登记"和"已确认未公告"分不清
    - 命中手工登记的行时跳过（除非 force），与 DAL 的手工保护一致
    """
    from storage import lifecycle_dal as dal

    if not credentials_configured():
        raise RuntimeError(status()["reason"])

    result = {"updated": [], "skipped_manual": [], "not_announced": [], "errors": []}
    try:
        found = lookup_product_ids(models)
    except requests.RequestException as e:
        raise RuntimeError(f"Cisco EoX 请求失败：{e}") from e

    for model in models:
        records = found.get(model) or []
        if not records:
            result["not_announced"].append(model)
            continue
        # 取最新一条公告（同一 PID 多条时，公告日期最新者为准）
        rec = sorted(records, key=lambda r: r.get("announcement") or "", reverse=True)[0]
        try:
            written = dal.upsert_model_eol(
                conn, model, description=rec["description"], end_of_sale=rec["end_of_sale"],
                end_of_support=rec["end_of_support"], announcement=rec["announcement"],
                bulletin=rec["bulletin"], bulletin_url=rec["bulletin_url"],
                source="api", force=force)
        except ValueError as e:
            result["errors"].append(f"{model}: {e}")
            continue
        (result["updated"] if written else result["skipped_manual"]).append(model)
    conn.commit()
    return result
