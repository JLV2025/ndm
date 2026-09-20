"""采集后自动审计（去抖）。

为什么要去抖：采集是**逐台**进行的（前端 worker 队列 / CLI 逐台调单设备端点），
没有服务端"批次"概念。每台采集成功后重置一个延迟定时器，批次静默 delay 秒后
跑一轮全网审计 —— 一批只跑一轮，而且跑的时候数据是完整的（而不是边采边审）。

失败隔离（最重要的一条）：整段包 try/except —— 审计出任何问题都不能影响采集。
开关：config/settings.yaml → ``audit: {run_after_collect: true, post_collect_delay: 60}``。
"""
from __future__ import annotations

import threading

DEFAULT_DELAY = 60.0

_timer: threading.Timer | None = None
_lock = threading.Lock()


def _settings() -> dict:
    from utils.settings_loader import load_settings
    return (load_settings() or {}).get("audit") or {}


def schedule_post_collect_audit(delay: float | None = None) -> bool:
    """采集成功后调用：重置延迟定时器。返回是否真的安排了（开关关闭 / 设置读不到时 False）。"""
    try:
        cfg = _settings()
    except Exception as e:                       # 设置读不到不能拖累采集
        print(f"[审计] 读取设置失败，跳过采集后自动审计：{e}")
        return False
    if cfg.get("run_after_collect", True) is False:
        return False
    if delay is None:
        try:
            delay = float(cfg.get("post_collect_delay", DEFAULT_DELAY))
        except (TypeError, ValueError):
            delay = DEFAULT_DELAY

    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()                      # 上一台的定时器作废 —— 批次内只留最后一个
        _timer = threading.Timer(max(0.0, delay), _run)
        _timer.daemon = True                     # 服务退出时不阻塞
        _timer.start()
    return True


def _run() -> None:
    global _timer
    with _lock:
        _timer = None
    try:
        from storage.database import get_connection
        from analyzers.compliance import loader, runner

        std = loader.load_standard(use_cache=False)
        res = runner.run_full_audit(get_connection(), std, trigger="post_collect")
        print(f"[审计] 采集后自动审计完成：{res['device_count']} 台，"
              f"{res['finding_count']} 条建议，已批准例外 {res['exempt_count']} 条"
              f"（{res['duration_ms']} ms）")
    except Exception as e:                       # noqa: BLE001 —— 任何异常都不上升
        print(f"[审计] 采集后自动审计失败（不影响采集）：{e}")
