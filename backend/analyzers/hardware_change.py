"""硬件变更检测 —— 指纹 diff 与事件（spec 第六节）。

只做确定性集合比较（"什么变了"）；不做策略（"该怎么办"）——整机级变化
只记录、只提示，历史全留，由人工备注（意图不自动化）。

判定优先级：整机更换 > 形态变化 > 成员级变化。
整机更换的判据只有两条：**平台变化 或 SN 集合零交集** —— 不看型号集合：
混型号堆叠（JL728B + JL727B）是常态，加一个不同型号的成员不能被误判为换代。
"""
import json

from utils.device_identity import member_suffixes


def compute_fingerprint(platform: str, model_str: str, serial_str: str, kind: str,
                        member_ids: str = "") -> dict:
    """硬件指纹 = (平台, 形态, 型号集合, 序列号集合, 成员数, 槽位绑定)。

    槽位绑定（{成员号: 序列号}）让"成员重编号"可检出——集合相同但槽位↔序列号
    绑定变化时报 member_reordered（成员行是槽位身份，重编号会让旧行离线、
    新行建立；没有这条事件，运维看到的是一对来路不明的行）。
    """
    models = sorted({m.strip() for m in (model_str or "").split(",") if m.strip()})
    serials = [s.strip() for s in (serial_str or "").split(",") if s.strip()]
    suffixes = member_suffixes(len(serials), member_ids)
    slots = {suffixes[i]: sn for i, sn in enumerate(serials)}
    return {"platform": platform or "", "models": models,
            "serials": sorted(set(serials)), "member_count": len(serials),
            "slots": slots, "kind": kind or ""}


def diff_fingerprints(prev: dict | None, cur: dict) -> dict | None:
    """返回变更事件 {"kind", "detail"}；无变化 / 首次采集 → None。

    情形（spec 第六节）：member_added / member_removed / member_replaced /
    member_reordered / full_replacement / form_change。
    """
    if prev is None or prev == cur:
        return None
    old, new = set(prev["serials"]), set(cur["serials"])
    if prev["platform"] != cur["platform"] or not (old & new):
        return {"kind": "full_replacement",
                "detail": json.dumps({"platform": [prev["platform"], cur["platform"]],
                                      "models": [prev["models"], cur["models"]],
                                      "serials": [sorted(old), sorted(new)]},
                                     ensure_ascii=False)}
    if prev["kind"] != cur["kind"]:
        return {"kind": "form_change",
                "detail": json.dumps({"kind": [prev["kind"], cur["kind"]],
                                      "members": [prev["member_count"], cur["member_count"]]},
                                     ensure_ascii=False)}
    if old == new:
        if prev.get("slots") != cur.get("slots"):
            return {"kind": "member_reordered",
                    "detail": json.dumps({"slots": [prev.get("slots"), cur.get("slots")]},
                                         ensure_ascii=False)}
        return None          # 集合与槽位都没变，只剩型号文本差异 —— 不算硬件变更
    if new > old:
        return {"kind": "member_added",
                "detail": json.dumps({"added": sorted(new - old)}, ensure_ascii=False)}
    if old > new:
        return {"kind": "member_removed",
                "detail": json.dumps({"removed": sorted(old - new)}, ensure_ascii=False)}
    return {"kind": "member_replaced",
            "detail": json.dumps({"out": sorted(old - new), "in": sorted(new - old)},
                                 ensure_ascii=False)}


def record_event(conn, device_id: int, event: dict, detected_at: str,
                 movements: list[dict] | None = None) -> None:
    """写变更事件；movements = [{serial, from_device}]（调拨，来自 device_members.last_device 变化）"""
    detail = event.get("detail") or ""
    if movements:
        detail = json.dumps({"diff": detail, "movements": movements}, ensure_ascii=False)
    conn.execute(
        "INSERT INTO device_change_events (device_id, detected_at, kind, detail) VALUES (?,?,?,?)",
        (device_id, detected_at, event["kind"], detail))
