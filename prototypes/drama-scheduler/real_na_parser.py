# -*- coding: utf-8 -*-
"""真实 NA 表解析器（支持 日期×时段 结构，绕过 openpyxl 样式兼容问题）。
提取成员可用性矩阵：V / NA / 部分出席标记。输出结构化 JSON 供验证与 API 复用。
"""
import io
import re
import zipfile
from xml.etree import ElementTree as ET

NSM = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

def parse_real_na_bytes(data: bytes):
    """从上传字节流解析真实 NA 表（等价于 parse_real_na）"""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return _parse(archive)


def parse_real_na(path):
    """从本地路径解析真实 NA 表"""
    with zipfile.ZipFile(path) as archive:
        return _parse(archive)


def _parse(z):
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{{{NSM}}}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NSM}}}t")))

    def col_idx(ref):
        letters = re.match(r"[A-Z]+", ref).group()
        n = 0
        for ch in letters:
            n = n * 26 + (ord(ch) - 64)
        return n - 1

    def read_sheet(fname):
        root = ET.fromstring(z.read(fname))
        grid = {}
        for r in root.findall(f".//{{{NSM}}}sheetData/{{{NSM}}}row"):
            rn = int(r.get("r"))
            cells = {}
            for c in r.findall(f"{{{NSM}}}c"):
                ref = c.get("r")
                t = c.get("t")
                v = c.find(f"{{{NSM}}}v")
                is_ = c.find(f"{{{NSM}}}is")
                if is_ is not None:
                    val = "".join(tt.text or "" for tt in is_.iter(f"{{{NSM}}}t"))
                elif v is not None:
                    val = v.text
                    if t == "s":
                        val = shared[int(val)] if int(val) < len(shared) else None
                else:
                    val = None
                if val is not None:
                    cells[col_idx(ref)] = str(val)
            if cells:
                grid[rn] = cells
        # 合并单元格：把左上角值填充到整个区域
        mc = root.find(f"{{{NSM}}}mergeCells")
        if mc is not None:
            for m in mc.findall(f"{{{NSM}}}mergeCell"):
                ref = m.get("ref")
                m1, m2 = ref.split(":")
                r1, c1 = int(re.search(r"(\d+)$", m1).group(1)), col_idx(m1)
                r2, c2 = int(re.search(r"(\d+)$", m2).group(1)), col_idx(m2)
                val = grid.get(r1, {}).get(c1)
                for rr in range(r1, r2 + 1):
                    for cc in range(c1, c2 + 1):
                        if rr in grid:
                            grid[rr].setdefault(cc, val)
        return grid

    grid = read_sheet("xl/worksheets/sheet1.xml")

    # 每次排期读取第一个带 Date / Session 标题的表块。
    blocks = []
    for rn in sorted(grid):
        row = grid[rn]
        if row.get(0) == "Date":
            # 找下方最近的 Session 行
            for srn in sorted(grid):
                if srn > rn and grid[srn].get(0) == "Session":
                    blocks.append((rn, srn))
                    break

    if not blocks:
        raise ValueError("未找到 Date / Session 表头")
    dr, sr = blocks[0]
    end = blocks[1][0] if len(blocks) > 1 else max(grid) + 1
    dates, sessions = grid[dr], grid[sr]
    slots = [{"col": col, "date": dates[col], "session": sessions[col]}
             for col in sorted(dates.keys() & sessions.keys())
             if col > 0 and dates[col] and sessions[col]]
    if not slots:
        raise ValueError("Date / Session 表头下没有完整时段")

    # 成员：读取当前表块的名称列和可用性值。
    structure_names = {"z", "NA：无法出席", "1X00后V：部分时间段出席", "WEEK", "Events"}
    members = []
    for rn in sorted(grid):
        row = grid[rn]
        name = row.get(0)
        if not sr < rn < end or not name or name in structure_names:
            continue
        if name.startswith("WEEK") or re.fullmatch(r"\d{1,2}月", name):
            continue
        has_data = any(row.get(slot["col"], "") for slot in slots)
        if not has_data:
            continue
        members.append({"row": rn, "name": name})

    if not members:
        raise ValueError("未找到有可用性数据的成员")

    # 成员可用性：对每个成员取该时段列的单元格值
    avail = {}
    partial = {}
    for m in members:
        row = grid.get(m["row"], {})
        vals = {}
        for s in slots:
            vals[s["col"]] = row.get(s["col"])
        avail[m["name"]] = vals
        # 统计部分出席
        for v in vals.values():
            if v and v.strip().upper() not in ("V", "NA", "") and "未知" not in v:
                partial.setdefault(m["name"], []).append(v)

    return {
        "slots": slots,
        "members": [{"name": m["name"]} for m in members],
        "avail": avail,
        "partial": partial,
    }
