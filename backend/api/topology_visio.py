"""Visio .vdx 拓扑图导出
POST /api/topology/export/visio — 接收拓扑 JSON, 返回 .vdx 文件"""

from fastapi import APIRouter, HTTPException, Response
import xml.etree.ElementTree as ET
from datetime import datetime

router = APIRouter()

# 设备颜色 (Visio 十六进制, 不带 #)
TYPE_COLORS: dict[str, str] = {
    "switch": "#3B82F6",
    "router": "#F59E0B",
    "firewall": "#EF4444",
    "wireless": "#8B5CF6",
    "sdwan": "#10B981",
    "server": "#06B6D4",
    "unknown": "#94A3B8",
}

TIER_LABELS: dict[str, str] = {
    "wan": "WAN",
    "core": "Core",
    "access": "Access",
}

# 布局常数
NODE_W = 2.0   # 英寸
NODE_H = 0.75
H_GAP = 0.6
V_GAP = 6.0    # 层间 (含标签)
START_X = 1.0
START_Y = 1.0
LABEL_H = 0.4

VISIO_NS = "http://schemas.microsoft.com/visio/2003/core"


def _make_shape(
    shape_id: str, name: str, text: str,
    x: float, y: float, w: float, h: float,
    fill_color: str, stroke_color: str,
) -> ET.Element:
    """构造一个 Visio Shape (矩形 + 文本)"""
    shape = ET.Element("Shape", {
        "ID": shape_id,
        "NameU": name,
        "Type": "Shape",
    })

    # 位置/尺寸
    xfrm = ET.SubElement(shape, "XForm")
    ET.SubElement(xfrm, "PinX", {"F": f"Inh"}).text = str(x + w / 2)
    ET.SubElement(xfrm, "PinY", {"F": f"Inh"}).text = str(y + h / 2)
    ET.SubElement(xfrm, "Width", {"F": f"Inh"}).text = str(w)
    ET.SubElement(xfrm, "Height", {"F": f"Inh"}).text = str(h)
    ET.SubElement(xfrm, "LocPinX", {"F": f"Inh"}).text = str(w / 2)
    ET.SubElement(xfrm, "LocPinY", {"F": f"Inh"}).text = str(h / 2)

    # 填充/线条
    fs = ET.SubElement(shape, "Fill")
    ET.SubElement(fs, "FillForegnd", {"F": "Inh"}).text = fill_color
    ET.SubElement(fs, "FillPattern", {"F": "Inh"}).text = "1"

    ls = ET.SubElement(shape, "Line")
    ET.SubElement(ls, "LinePattern", {"F": "Inh"}).text = "1"
    ET.SubElement(ls, "LineWeight", {"F": "Inh"}).text = "0.01"
    ET.SubElement(ls, "LineColor", {"F": "Inh"}).text = stroke_color

    # 文本
    cs = ET.SubElement(shape, "Char")
    ET.SubElement(cs, "Size", {"F": "Inh"}).text = "0.15"
    ET.SubElement(cs, "Color", {"F": "Inh"}).text = "#FFFFFF"

    tb = ET.SubElement(shape, "TextBlock")
    ET.SubElement(tb, "LeftMargin", {"F": "Inh"}).text = "0.05"
    ET.SubElement(tb, "RightMargin", {"F": "Inh"}).text = "0.05"

    te = ET.SubElement(shape, "Text")
    ET.SubElement(te, "cp", {"IX": "0"})
    ET.SubElement(te, "pp", {"IX": "0"})
    ET.SubElement(te, "tp", {"IX": "0"}).text = text

    return shape


def _make_connector(src_id: str, dst_id: str) -> ET.Element:
    """构造连接线"""
    return ET.Element("Connect", {"FromSheet": src_id, "ToSheet": dst_id})


@router.post("/topology/export/visio")
async def export_visio(data: dict):
    """
    将拓扑数据导出为 Visio .vdx 文件 (XML Drawing)

    请求体: LocationTopologyData JSON
    返回: .vdx 文件 (application/vnd.visio)
    """
    try:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        # 按 tier 分组
        tiers: dict[str, list[dict]] = {"wan": [], "core": [], "access": [], "unknown": []}
        for n in nodes:
            tier = n.get("tier", "unknown")
            tiers.setdefault(tier, []).append(n)

        # 计算位置
        shape_map: dict[str, str] = {}  # node_id → shape_id
        shape_id_counter = 1
        page_x = START_X
        current_y = START_Y

        shapes_el = ET.Element("Shapes")
        connects_el = ET.Element("Connects")

        # 每层渲染
        tier_order = ["wan", "core", "access", "unknown"]
        for tier_key in tier_order:
            tier_nodes = tiers.get(tier_key, [])
            if not tier_nodes:
                continue

            label = TIER_LABELS.get(tier_key, tier_key.upper())
            # 层级标签
            tier_shape_id = str(shape_id_counter)
            shape_id_counter += 1
            shapes_el.append(_make_shape(
                tier_shape_id, f"Tier_{tier_key}",
                label, 0.3, current_y, 1.0, NODE_H,
                "#1e293b", "#334155",
            ))

            # 设备节点
            row_w = len(tier_nodes) * (NODE_W + H_GAP) - H_GAP
            cursor_x = START_X
            for node in tier_nodes:
                nid = str(shape_id_counter)
                shape_id_counter += 1
                node_id = node["id"]
                shape_map[node_id] = nid

                device_type = node.get("type", "unknown")
                color = TYPE_COLORS.get(device_type, TYPE_COLORS["unknown"])
                text = f"{node['label']}\n{node.get('platform', '')}"

                shapes_el.append(_make_shape(
                    nid, node_id, text.strip(),
                    cursor_x, current_y + LABEL_H, NODE_W, NODE_H,
                    f"{color}30", color,
                ))
                cursor_x += NODE_W + H_GAP

            current_y += LABEL_H + NODE_H + V_GAP

        # 边
        for i, edge in enumerate(edges):
            src = shape_map.get(edge["source"])
            dst = shape_map.get(edge["target"])
            if src and dst:
                connects_el.append(_make_connector(src, dst))

        # 组装 Visio XML
        visio = ET.Element("VisioDocument", {
            "xmlns": VISIO_NS,
        })
        pages = ET.SubElement(visio, "Pages")
        page = ET.SubElement(pages, "Page", {"ID": "0", "NameU": "Topology"})
        page.append(shapes_el)
        page.append(connects_el)

        # 序列化
        xml_bytes = ET.tostring(visio, encoding="utf-8", xml_declaration=True)
        content = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml_bytes

        filename = f"topology-{data.get('location', 'export')}-{datetime.now().strftime('%Y%m%d')}.vdx"

        return Response(
            content=content,
            media_type="application/vnd.visio",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visio export failed: {str(e)}")
