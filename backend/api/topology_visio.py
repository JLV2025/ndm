"""Visio .vsdx 拓扑图导出
POST /api/topology/export/visio — 接收拓扑 JSON, 返回 .vsdx 文件 (ZIP 包)

基于 Visio 2013+ VSDX 格式（OpenXML ZIP + 部件 XML）
参考: Microsoft Visio 2012 XML Schema"""

from fastapi import APIRouter, HTTPException, Response
from datetime import datetime
from xml.sax.saxutils import escape as _esc
import io, zipfile

router = APIRouter()

NS = 'http://schemas.microsoft.com/office/visio/2012/main'
REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
APP_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'
VT_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'
CP_NS = 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
DC_NS = 'http://purl.org/dc/elements/1.1/'
DCT_NS = 'http://purl.org/dc/terms/'
DCTYPE_NS = 'http://purl.org/dc/dcmitype/'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'

TYPE_COLORS = {
    "switch": "#3B82F6", "router": "#F59E0B", "firewall": "#EF4444",
    "wireless": "#8B5CF6", "sdwan": "#10B981", "server": "#06B6D4",
    "unknown": "#94A3B8",
}
TIER_LABELS = {"wan": "WAN", "core": "Core", "access": "Access"}

NODE_W = 2.0   # 英寸
NODE_H = 0.75
H_GAP = 0.6
V_GAP = 6.0
START_X = 1.0
START_Y = 1.0
LABEL_H = 0.4


def _shape_cell(name: str, value: str, formula: str = "") -> str:
    """<Cell N="name" V="value"/>"""
    f = f' F="{_esc(formula)}"' if formula else ""
    return f'<Cell N="{name}" V="{_esc(value)}"{f}/>'


def _shape_xml(sid: int, name: str, label: str, sub: str,
               x: float, y: float, w: float, h: float,
               fill: str, stroke: str) -> str:
    """生成设备矩形 Shape（Type=Shape, 全属性内联）"""
    lines = [
        f'<Shape ID="{sid}" Type="Shape" LineStyle="0" FillStyle="0" TextStyle="0">',
        _shape_cell("PinX", str(round(x + w / 2, 4))),
        _shape_cell("PinY", str(round(y + h / 2, 4))),
        _shape_cell("Width", str(round(w, 4))),
        _shape_cell("Height", str(round(h, 4))),
        _shape_cell("LocPinX", str(round(w / 2, 4))),
        _shape_cell("LocPinY", str(round(h / 2, 4))),
        _shape_cell("Angle", "0"),
        # Fill
        '<Section N="Fill" IX="0">',
        _shape_cell("FillForegnd", fill),
        _shape_cell("FillPattern", "1"),
        _shape_cell("FillForegndTrans", "0"),
        '</Section>',
        # Line
        '<Section N="Line" IX="0">',
        _shape_cell("LinePattern", "1"),
        _shape_cell("LineWeight", "0.01"),
        _shape_cell("LineColor", stroke),
        '</Section>',
        # Character
        '<Section N="Character" IX="0">',
        '<Row IX="0">',
        _shape_cell("Font", "0"),
        _shape_cell("Size", "0.15"),
        _shape_cell("Color", "#000000"),
        '</Row>',
        '</Section>',
        # Paragraph (居中)
        '<Section N="Paragraph" IX="0">',
        '<Row IX="0">',
        _shape_cell("HorzAlign", "1"),
        '</Row>',
        '</Section>',
        # Geometry — 相对坐标 (0..1 范围)
        '<Section N="Geometry" IX="0">',
        _shape_cell("NoFill", "0"),
        _shape_cell("NoLine", "0"),
        '<Row T="RelMoveTo" IX="1">',
        _shape_cell("X", "0"),
        _shape_cell("Y", "0"),
        '</Row>',
        '<Row T="RelLineTo" IX="2">',
        _shape_cell("X", "1"),
        _shape_cell("Y", "0"),
        '</Row>',
        '<Row T="RelLineTo" IX="3">',
        _shape_cell("X", "1"),
        _shape_cell("Y", "1"),
        '</Row>',
        '<Row T="RelLineTo" IX="4">',
        _shape_cell("X", "0"),
        _shape_cell("Y", "1"),
        '</Row>',
        '<Row T="RelLineTo" IX="5">',
        _shape_cell("X", "0"),
        _shape_cell("Y", "0"),
        '</Row>',
        '</Section>',
        # TextBlock
        '<Section N="TextBlock">',
        _shape_cell("LeftMargin", "0.05"),
        _shape_cell("RightMargin", "0.05"),
        '</Section>',
        # Text content
        '<Text>',
        f'<cp IX="0"/><pp IX="0"/><tp IX="0">{_esc(label)}{"&#10;" + _esc(sub) if sub else ""}</tp>',
        '</Text>',
        '</Shape>',
    ]
    return "\n".join(lines)


def _conn_line_xml(sid: int, src_x: float, src_y: float,
                   dst_x: float, dst_y: float, color: str) -> str:
    """生成连接线 (1-D shape)"""
    return "\n".join([
        f'<Shape ID="{sid}" Type="Shape" LineStyle="0">',
        _shape_cell("PinX", str(round((src_x + dst_x) / 2, 4))),
        _shape_cell("PinY", str(round((src_y + dst_y) / 2, 4))),
        _shape_cell("BeginX", str(round(src_x, 4))),
        _shape_cell("BeginY", str(round(src_y, 4))),
        _shape_cell("EndX", str(round(dst_x, 4))),
        _shape_cell("EndY", str(round(dst_y, 4))),
        '<Section N="Line" IX="0">',
        _shape_cell("LinePattern", "1"),
        _shape_cell("LineWeight", "0.01"),
        _shape_cell("LineColor", color),
        _shape_cell("EndArrow", "5"),
        '</Section>',
        '<Section N="Geometry" IX="0">',
        _shape_cell("NoFill", "1"),
        _shape_cell("NoLine", "0"),
        '<Row T="MoveTo" IX="1">',
        _shape_cell("X", str(round(src_x, 4))),
        _shape_cell("Y", str(round(src_y, 4))),
        '</Row>',
        '<Row T="LineTo" IX="2">',
        _shape_cell("X", str(round(dst_x, 4))),
        _shape_cell("Y", str(round(dst_y, 4))),
        '</Row>',
        '</Section>',
        '</Shape>',
    ])


def _build_styles_xml() -> str:
    """文档级样式表 — 最小集（参照 bpmn-to-visio 已验证结构）"""
    cells = [
        ("LineWeight","0.01"),
        ("LineColor","#333333"),
        ("FillForegnd","#FFFFFF"),
        ("CharFont","0"),
        ("TxtHeight","0.1111"),
    ]
    return (
        '<StyleSheets>'
        '<StyleSheet ID="0" NameU="Normal" Name="Normal">'
        + "\n".join(_shape_cell(n, v) for n, v in cells) +
        '</StyleSheet>'
        '</StyleSheets>'
    )


@router.post("/topology/export/visio")
async def export_visio(data: dict):
    """拓扑数据 → Visio .vsdx"""
    try:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        if not nodes:
            raise HTTPException(status_code=400, detail="No topology nodes")

        # ── 按 tier 分组 + 布局 ──
        tiers: dict[str, list[dict]] = {}
        for n in nodes:
            t = n.get("tier", "unknown")
            tiers.setdefault(t, []).append(n)

        max_count = max((len(tiers.get(t, [])) for t in TIER_LABELS), default=1)
        _page_w = max(START_X * 2 + max_count * (NODE_W + H_GAP), 8.5)

        shape_map: dict[str, tuple[str, float, float]] = {}  # node_id → (shape_id, cx, cy)
        sid = 1
        current_y = START_Y
        shapes_parts: list[str] = []
        conn_parts: list[str] = []

        for tier_key in ["wan", "core", "access", "unknown"]:
            tier_nodes = tiers.get(tier_key, [])
            if not tier_nodes:
                continue

            # 层标签
            shapes_parts.append(_shape_xml(
                sid, f"Tier_{tier_key}",
                TIER_LABELS.get(tier_key, tier_key.upper()), "",
                0.3, current_y, 1.0, NODE_H,
                "#1e293b", "#334155",
            ))
            sid += 1

            # 设备 — 居中
            tier_w = len(tier_nodes) * (NODE_W + H_GAP) - H_GAP
            cursor_x = max(START_X, (_page_w - tier_w) / 2)
            for node in tier_nodes:
                node_id = str(node.get("id", ""))
                if not node_id:
                    continue
                nid = str(sid)
                sid += 1

                dtype = str(node.get("type", "unknown"))
                color = TYPE_COLORS.get(dtype, TYPE_COLORS["unknown"])
                node_label = str(node.get("label", node_id))
                platform = str(node.get("platform", ""))

                sx = cursor_x
                sy = current_y + LABEL_H
                cx = sx + NODE_W / 2  # 形状中心 X
                cy = sy + NODE_H / 2  # 形状中心 Y
                shape_map[node_id] = (nid, cx, cy)

                shapes_parts.append(_shape_xml(
                    int(nid), node_id, node_label, platform,
                    sx, sy, NODE_W, NODE_H,
                    f"{color}30", color,
                ))
                cursor_x += NODE_W + H_GAP

            current_y += LABEL_H + NODE_H + V_GAP

        page_h = max(current_y + 1, 8.27)

        # ── 边（连接线） ──
        for edge in edges:
            src_key = str(edge.get("source", ""))
            dst_key = str(edge.get("target", ""))
            src = shape_map.get(src_key)
            dst = shape_map.get(dst_key)
            if not src or not dst:
                continue

            _, sx_cx, sx_cy = src
            _, dx_cx, dx_cy = dst

            # 判断连线的设备类型决定颜色
            # 找到对应的节点，取上层设备的颜色
            src_node = next((n for n in nodes if str(n.get("id", "")) == src_key), None)
            if src_node:
                ec = TYPE_COLORS.get(str(src_node.get("type", "unknown")), "#94A3B8")
            else:
                ec = "#94A3B8"

            conn_parts.append(_conn_line_xml(sid, sx_cx, sx_cy, dx_cx, dx_cy, ec))
            sid += 1

        # ══════════════════════════════════════════════════════
        # 构建 ZIP 包
        # ══════════════════════════════════════════════════════
        location = str(data.get("location", "export"))
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        page_w = max(8.5, _page_w)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

            # 1. [Content_Types].xml
            zf.writestr("[Content_Types].xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<Types xmlns="{CT_NS}">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>'
                '<Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>'
                '<Override PartName="/visio/pages/page1.xml" ContentType="application/vnd.ms-visio.page+xml"/>'
                '<Override PartName="/visio/windows.xml" ContentType="application/vnd.ms-visio.windows+xml"/>'
                '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
                '</Types>'
            ))

            # 2. _rels/.rels
            zf.writestr("_rels/.rels", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<Relationships xmlns="{REL_NS}">'
                '<Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
                '</Relationships>'
            ))

            # 3. visio/document.xml
            zf.writestr("visio/document.xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<VisioDocument xmlns="{NS}" xmlns:r="{REL_NS}">'
                '<DocumentProperties><Creator>NDM Topology Exporter</Creator></DocumentProperties>'
                '<DocumentSettings/>'
                '<Colors/>'
                '<FaceNames>'
                '<FaceName ID="0" Name="Calibri" UnicodeRanges="-1 -1 0 0" CharSets="536871423 0" Panos="2 15 5 2 2 2 4 3 2 4"/>'
                '</FaceNames>'
                + _build_styles_xml() +
                '</VisioDocument>'
            ))

            # 4. visio/_rels/document.xml.rels
            zf.writestr("visio/_rels/document.xml.rels", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<Relationships xmlns="{REL_NS}">'
                '<Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.microsoft.com/visio/2010/relationships/windows" Target="windows.xml"/>'
                '</Relationships>'
            ))

            # 5. visio/pages/pages.xml
            pages_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<Pages xmlns="{NS}" xmlns:r="{REL_NS}" xml:space="preserve">'
                f'<Page ID="0" NameU="Page-1" Name="Topology">'
                '<PageSheet LineStyle="0" FillStyle="0" TextStyle="0">'
                + _shape_cell("PageWidth", str(round(page_w, 4)))
                + _shape_cell("PageHeight", str(round(page_h, 4)))
                + _shape_cell("DrawingScale", "1")
                + _shape_cell("PageScale", "1")
                + '</PageSheet>'
                + '<Rel r:id="rId1"/>'
                + '</Page>'
                + '</Pages>'
            )
            zf.writestr("visio/pages/pages.xml", pages_xml)

            # 6. visio/pages/_rels/pages.xml.rels
            zf.writestr("visio/pages/_rels/pages.xml.rels", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<Relationships xmlns="{REL_NS}">'
                '<Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page1.xml"/>'
                '</Relationships>'
            ))

            # 7. visio/pages/page1.xml — 核心内容
            page_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<PageContents xmlns="{NS}" xmlns:r="{REL_NS}" xml:space="preserve">'
                '<Shapes>'
                + "\n".join(shapes_parts)
                + "\n".join(conn_parts)
                + '</Shapes>'
                + '</PageContents>'
            )
            zf.writestr("visio/pages/page1.xml", page_xml)

            # 8. visio/windows.xml
            zf.writestr("visio/windows.xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<Windows xmlns="{NS}">'
                '<Window ID="0" WindowType="Drawing" WindowState="1073741824"'
                ' WindowLeft="0" WindowTop="0" WindowWidth="1024" WindowHeight="768">'
                '<StencilGroup/>'
                '<StencilGroupPos/>'
                '<ShowRulers>1</ShowRulers>'
                '<ShowGrid>1</ShowGrid>'
                '<ShowPageBreaks>0</ShowPageBreaks>'
                '<ShowGuides>1</ShowGuides>'
                '<ShowConnectionPoints>1</ShowConnectionPoints>'
                '<GlueSettings>9</GlueSettings>'
                '<SnapSettings>65847</SnapSettings>'
                '<SnapExtensions>34</SnapExtensions>'
                '<DynamicGridEnabled>1</DynamicGridEnabled>'
                '<TabSplitterPos>0.5</TabSplitterPos>'
                '</Window>'
                '</Windows>'
            ))

            # 9. docProps/app.xml
            zf.writestr("docProps/app.xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<Properties xmlns="{APP_NS}" xmlns:vt="{VT_NS}">'
                '<Application>NDM Topology Exporter</Application>'
                '</Properties>'
            ))

        zip_bytes = buf.getvalue()
        buf.close()

        filename = f"topology-{location}-{datetime.now().strftime('%Y%m%d')}.vsdx"

        return Response(
            content=zip_bytes,
            media_type="application/vnd.ms-visio.drawing",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visio export failed: {str(e)}")
