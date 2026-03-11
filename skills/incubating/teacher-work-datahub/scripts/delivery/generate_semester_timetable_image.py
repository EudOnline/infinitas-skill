#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成“个人学期课表（单双周同图）”标准规范图片

展示规则（单元格仅一行数据）：
1) 单双周一致：仅显示班级（不加“单/双”），不着色。
2) 仅单周有课：显示“单xxx”，单周色背景。
3) 仅双周有课：显示“双xxx”，双周色背景。
4) 单双周都上但不同：显示“单xxx/双yyy”，左右双色背景。
5) 单双周都无课：显示“—”。
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from schedule_helpers import extract_schedule_map, has_subject, load_json, load_slot_time_map, schedule_has_evening_slots


def fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    txt = str(text)
    if draw.textlength(txt, font=font) <= max_w:
        return txt
    while len(txt) > 1 and draw.textlength(txt + "…", font=font) > max_w:
        txt = txt[:-1]
    return txt + "…"


def render_image(
    schedule_map,
    classes,
    title,
    subtitle,
    subject,
    out_path: Path,
    slot_time: dict,
    source_kind: str,
    source_has_evening_slots: bool,
):
    days = ["一", "二", "三", "四", "五"]
    no_evening_semantics = (source_kind == "school_schedule_no_selfstudy") and (not source_has_evening_slots)

    def data_row(slot):
        label = f"第{slot}节" if slot.isdigit() else slot
        row = [label, slot_time[slot]]
        for d in days:
            single_vals = []
            double_vals = []
            for cls in classes:
                v = schedule_map.get(cls, {}).get(slot, {}).get(d, "")
                if has_subject(v, subject, "single"):
                    single_vals.append(cls)
                if has_subject(v, subject, "double"):
                    double_vals.append(cls)
            if slot.startswith("晚") and no_evening_semantics:
                row.append({
                    "single": "未提供",
                    "double": "未提供",
                    "display_mode": "unknown_evening",
                })
            else:
                row.append({
                    "single": "、".join(single_vals) if single_vals else "—",
                    "double": "、".join(double_vals) if double_vals else "—",
                    "display_mode": "normal",
                })
        return {"type": "data", "cells": row}

    rows = [
        {"type": "weekday_header", "cells": ["节次", "时间", "星期一", "星期二", "星期三", "星期四", "星期五"]}
    ]
    for s in ["1", "2", "3", "4"]:
        rows.append(data_row(s))
    rows.append({"type": "spacer"})
    for s in ["5", "6", "7"]:
        rows.append(data_row(s))
    rows.append({"type": "spacer"})
    for s in ["晚1", "晚2", "晚3", "晚4"]:
        rows.append(data_row(s))

    # 布局
    W = 1780
    margin = 34
    title_h = 62
    subtitle_h = 42
    gap_h = 12
    header_h = 58
    row_h = 58
    spacer_h = 24
    foot_h = 136 if no_evening_semantics else 108

    col_ws = [124, 228, 272, 272, 272, 272, 272]
    sumw = sum(col_ws)
    if sumw > W - 2 * margin:
        scale = (W - 2 * margin) / sumw
        col_ws = [int(w * scale) for w in col_ws]
        sumw = sum(col_ws)

    table_h = 0
    for r in rows:
        if r["type"] == "spacer":
            table_h += spacer_h
        elif r["type"] == "weekday_header":
            table_h += header_h
        else:
            table_h += row_h

    H = margin + title_h + subtitle_h + gap_h + table_h + foot_h + margin

    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    font_b = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    font_r = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if not Path(font_r).exists():
        font_r = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"

    ft_title = ImageFont.truetype(font_b, 40)
    ft_sub = ImageFont.truetype(font_b, 28)
    ft_head = ImageFont.truetype(font_b, 23)
    ft_cell = ImageFont.truetype(font_r, 20)
    ft_foot = ImageFont.truetype(font_r, 16)

    # 颜色
    color_header_bg = (238, 246, 255)
    color_header_text = (28, 58, 102)
    color_grid = (208, 208, 208)
    color_single_bg = (226, 241, 255)  # 单周：浅蓝
    color_double_bg = (255, 239, 219)  # 双周：浅橙
    color_single_text = (26, 86, 146)
    color_double_text = (146, 90, 21)
    color_unknown_evening_bg = (247, 247, 247)
    color_unknown_evening_border = (193, 193, 193)
    color_unknown_evening_text = (120, 120, 120)

    x = margin
    x2 = x + sumw
    y = margin

    tw = draw.textlength(title, font=ft_title)
    draw.text(((W - tw) / 2, y), title, fill=(24, 24, 24), font=ft_title)
    y += title_h

    sub = f"{subtitle}｜{subject}学期课表（单双周同图）"
    sw = draw.textlength(sub, font=ft_sub)
    draw.text(((W - sw) / 2, y), sub, fill=(58, 58, 58), font=ft_sub)
    y += subtitle_h + gap_h

    start_y = y
    data_idx = 0

    for r in rows:
        if r["type"] == "spacer":
            draw.line([x, y + spacer_h // 2, x2, y + spacer_h // 2], fill=(224, 224, 224), width=2)
            y += spacer_h
            continue

        if r["type"] == "weekday_header":
            h = header_h
            draw.rectangle([x, y, x2, y + h], fill=color_header_bg, outline=(175, 190, 220), width=1)
        else:
            h = row_h
            base_bg = (255, 255, 255) if data_idx % 2 == 0 else (249, 251, 254)
            draw.rectangle([x, y, x2, y + h], fill=base_bg, outline=(205, 205, 205), width=1)

        # 列竖线
        cx = x
        for w in col_ws:
            draw.line([cx, y, cx, y + h], fill=color_grid, width=1)
            cx += w
        draw.line([x2, y, x2, y + h], fill=color_grid, width=1)

        # 内容
        cx = x
        for i, val in enumerate(r["cells"]):
            cw = col_ws[i]
            if r["type"] == "weekday_header":
                txt = fit_text(draw, str(val), ft_head, cw - 14)
                tw2 = draw.textlength(txt, font=ft_head)
                tx = cx + (cw - tw2) / 2
                draw.text((tx, y + (h - 23) // 2), txt, fill=color_header_text, font=ft_head)
            elif i < 2:
                txt = fit_text(draw, str(val), ft_cell, cw - 14)
                tw2 = draw.textlength(txt, font=ft_cell)
                tx = cx + (cw - tw2) / 2
                draw.text((tx, y + (h - 21) // 2), txt, fill=(30, 30, 30), font=ft_cell)
            else:
                cell = val
                single_txt = cell["single"]
                double_txt = cell["double"]
                display_mode = cell.get("display_mode", "normal")

                # 先清空单元格内部
                draw.rectangle([cx + 1, y + 1, cx + cw - 1, y + h - 1], fill=(255, 255, 255))

                if display_mode == "unknown_evening":
                    draw.rectangle(
                        [cx + 1, y + 1, cx + cw - 1, y + h - 1],
                        fill=color_unknown_evening_bg,
                        outline=color_unknown_evening_border,
                        width=1,
                    )
                    display = "未提供"
                    txt_color = color_unknown_evening_text
                else:
                    single_has = single_txt != "—"
                    double_has = double_txt != "—"
                    same = single_has and double_has and single_txt == double_txt

                    if not single_has and not double_has:
                        display = "—"
                        txt_color = (130, 130, 130)
                    elif same:
                        # 单双周一致：仅显示班级，不加单/双，不着色
                        display = single_txt
                        txt_color = (35, 35, 35)
                    elif single_has and not double_has:
                        # 双周无课：只显示单周
                        draw.rectangle([cx + 1, y + 1, cx + cw - 1, y + h - 1], fill=color_single_bg)
                        display = f"单{single_txt}"
                        txt_color = color_single_text
                    elif double_has and not single_has:
                        # 单周无课：只显示双周
                        draw.rectangle([cx + 1, y + 1, cx + cw - 1, y + h - 1], fill=color_double_bg)
                        display = f"双{double_txt}"
                        txt_color = color_double_text
                    else:
                        # 单双周都上但不同：一行显示，左右双色背景
                        midx = cx + cw // 2
                        draw.rectangle([cx + 1, y + 1, midx, y + h - 1], fill=color_single_bg)
                        draw.rectangle([midx, y + 1, cx + cw - 1, y + h - 1], fill=color_double_bg)
                        draw.line([midx, y + 1, midx, y + h - 1], fill=(232, 232, 232), width=1)
                        display = f"单{single_txt}/双{double_txt}"
                        txt_color = (55, 55, 55)

                txt = fit_text(draw, display, ft_cell, cw - 10)
                tw2 = draw.textlength(txt, font=ft_cell)
                tx = cx + (cw - tw2) / 2
                draw.text((tx, y + (h - 21) // 2), txt, fill=txt_color, font=ft_cell)

            cx += cw

        y += h
        if r["type"] == "data":
            data_idx += 1

    end_y = y
    draw.rectangle([x, start_y, x2, end_y], outline=(170, 170, 170), width=1)

    # 图例 + 说明
    ly = y + 10
    lx = margin

    # 单周图例
    draw.rectangle([lx, ly, lx + 30, ly + 18], fill=color_single_bg, outline=(196, 216, 235), width=1)
    draw.text((lx + 38, ly - 1), "单周（斜杠前）", fill=color_single_text, font=ft_foot)

    # 双周图例
    lx2 = lx + 260
    draw.rectangle([lx2, ly, lx2 + 30, ly + 18], fill=color_double_bg, outline=(236, 216, 196), width=1)
    draw.text((lx2 + 38, ly - 1), "双周（斜杠后）", fill=color_double_text, font=ft_foot)

    # 单双周不同图例（双色）
    lx3 = lx + 520
    draw.rectangle([lx3, ly, lx3 + 15, ly + 18], fill=color_single_bg, outline=(196, 216, 235), width=1)
    draw.rectangle([lx3 + 15, ly, lx3 + 30, ly + 18], fill=color_double_bg, outline=(236, 216, 196), width=1)
    draw.text((lx3 + 38, ly - 1), "同节单双周不同", fill=(95, 95, 95), font=ft_foot)

    if no_evening_semantics:
        lx4 = lx + 810
        draw.rectangle([lx4, ly, lx4 + 30, ly + 18], fill=color_unknown_evening_bg, outline=color_unknown_evening_border, width=1)
        draw.text((lx4 + 38, ly - 1), "晚自习未提供", fill=color_unknown_evening_text, font=ft_foot)

    explain_line = "同周同课仅显示班级（如 2404班）；双周无课不显示“双—”；每个单元格仅一行数据。"
    if no_evening_semantics:
        explain_line += " 使用全校无自习课表时，晚1-晚4 标注“未提供”表示该源缺少晚自习数据，不表示无课。"
    draw.text(
        (margin, ly + 30),
        explain_line,
        fill=(120, 120, 120),
        font=ft_foot,
    )
    source_note = "课表源：全校无自习课表（晚自习未提供）" if no_evening_semantics else f"课表源：{source_kind}"
    draw.text(
        (margin, ly + 52),
        f"分段：上午 / 下午 / 晚自习   {source_note}   生成：{datetime.now().strftime('%m-%d %H:%M')}",
        fill=(140, 140, 140),
        font=ft_foot,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=95)


def main():
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[4]
    default_candidates = [
        root / "data" / "teacher-work-datahub" / "curated" / "schedules" / "grade_schedule_latest_s2.json",
        root / "data" / "schedules" / "2025-2026-S2-grade10cohort2024-grade11-complete.json",
    ]
    default_schedule_json = str(next((p for p in default_candidates if p.exists()), default_candidates[0]))
    parser.add_argument(
        "--schedule-json",
        default=default_schedule_json,
    )
    parser.add_argument("--classes", default="2403班,2404班")
    parser.add_argument("--title", default="2025-2026第二学年高二年级")
    parser.add_argument("--subtitle", default="吕晓瑞")
    parser.add_argument("--subject", default="物理")
    parser.add_argument(
        "--semester-schedule-json",
        default="config/semester_schedule.json",
        help="官方作息配置",
    )
    parser.add_argument(
        "--source-kind",
        default="",
        help="课表源类型，如 grade_schedule_with_selfstudy / school_schedule_no_selfstudy",
    )
    parser.add_argument(
        "--source-has-evening-slots",
        default="auto",
        help="课表源是否提供晚自习节次：true|false|auto",
    )
    parser.add_argument(
        "--out",
        default="data/reports/printables/个人学期课表-单双周-标准规范版.jpg",
    )
    args = parser.parse_args()

    classes = [x.strip() for x in args.classes.split(",") if x.strip()]
    schedule_data = load_json(Path(args.schedule_json))
    schedule_map = extract_schedule_map(schedule_data, classes)
    slot_time = load_slot_time_map(Path(args.semester_schedule_json))

    source_kind = args.source_kind or schedule_data.get("schedule_kind") or schedule_data.get("source", {}).get("kind", "")
    flag = (args.source_has_evening_slots or "auto").strip().lower()
    if flag == "true":
        source_has_evening = True
    elif flag == "false":
        source_has_evening = False
    else:
        source_has_evening = schedule_has_evening_slots(schedule_data)

    render_image(
        schedule_map,
        classes,
        args.title,
        args.subtitle,
        args.subject,
        Path(args.out),
        slot_time,
        source_kind,
        source_has_evening,
    )
    print(Path(args.out))


if __name__ == "__main__":
    main()
