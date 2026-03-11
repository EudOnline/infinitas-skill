#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成“个人周课表”标准规范图片
"""

import argparse
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import sys

SCRIPT_DIR = Path(__file__).resolve().parent
UTILS_DIR = SCRIPT_DIR.parent / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from schedule_helpers import extract_schedule_map, has_subject, load_json, load_slot_time_map, schedule_has_evening_slots


ROOT = Path(__file__).resolve().parents[4]


def default_schedule_json() -> str:
    candidates = [
        ROOT / "data" / "teacher-work-datahub" / "curated" / "schedules" / "grade_schedule_latest_s2.json",
        ROOT / "data" / "schedules" / "2025-2026-S2-grade10cohort2024-grade11-complete.json",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return str(candidates[0])


def render_image(
    schedule_map,
    classes,
    title,
    subtitle,
    subject,
    week_parity,
    out_path: Path,
    slot_time: dict,
    source_kind: str,
    source_has_evening_slots: bool,
):
    days = ["一", "二", "三", "四", "五"]
    no_evening_semantics = (source_kind == "school_schedule_no_selfstudy") and (not source_has_evening_slots)

    def data_row(slot):
        label = f"第{slot}节" if slot.isdigit() else slot
        row = [label, slot_time.get(slot, "")]
        for d in days:
            if slot.startswith("晚") and no_evening_semantics:
                row.append("未提供")
                continue

            vals = []
            for cls in classes:
                v = schedule_map.get(cls, {}).get(slot, {}).get(d, "")
                if has_subject(v, subject, week_parity=week_parity):
                    vals.append(cls)
            row.append("、".join(vals) if vals else "—")
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

    W = 1680
    margin = 36
    title_h = 60
    subtitle_h = 42
    gap_h = 14
    row_h = 56
    header_h = 56
    spacer_h = 26
    foot_h = 44 if no_evening_semantics else 24
    col_ws = [120, 220, 255, 255, 255, 255, 255]

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
    ft_sub = ImageFont.truetype(font_b, 30)
    ft_cell = ImageFont.truetype(font_r, 23)
    ft_head = ImageFont.truetype(font_b, 23)
    ft_foot = ImageFont.truetype(font_r, 16)

    x = margin
    x2 = x + sumw
    y = margin

    tw = draw.textlength(title, font=ft_title)
    draw.text(((W - tw) / 2, y), title, fill=(24, 24, 24), font=ft_title)
    y += title_h

    sw = draw.textlength(subtitle, font=ft_sub)
    draw.text(((W - sw) / 2, y), subtitle, fill=(60, 60, 60), font=ft_sub)
    y += subtitle_h + gap_h

    start_y = y
    data_idx = 0

    for r in rows:
        if r["type"] == "spacer":
            draw.line([x, y + spacer_h // 2, x2, y + spacer_h // 2], fill=(224, 224, 224), width=2)
            y += spacer_h
            continue

        if r["type"] == "weekday_header":
            draw.rectangle([x, y, x2, y + header_h], fill=(238, 246, 255), outline=(175, 190, 220), width=1)
            h = header_h
            text_font = ft_head
        else:
            bg = (255, 255, 255) if data_idx % 2 == 0 else (248, 251, 255)
            draw.rectangle([x, y, x2, y + row_h], fill=bg, outline=(205, 205, 205), width=1)
            h = row_h
            text_font = ft_cell

        cx = x
        for w in col_ws:
            draw.line([cx, y, cx, y + h], fill=(212, 212, 212), width=1)
            cx += w
        draw.line([x2, y, x2, y + h], fill=(212, 212, 212), width=1)

        cx = x
        for i, val in enumerate(r["cells"]):
            txt = str(val)
            maxw = col_ws[i] - 14
            while draw.textlength(txt, font=text_font) > maxw and len(txt) > 1:
                txt = txt[:-1]
            if txt != str(val):
                txt = txt[:-1] + "…"

            tw2 = draw.textlength(txt, font=text_font)
            tx = cx + (col_ws[i] - tw2) / 2

            color = (22, 22, 22)
            if r["type"] == "weekday_header":
                color = (28, 58, 102)
            elif i >= 2 and txt == "未提供":
                color = (128, 128, 128)
            elif i >= 2 and txt != "—":
                color = (0, 110, 58)

            draw.text((tx, y + (h - 23) // 2), txt, fill=color, font=text_font)
            cx += col_ws[i]

        y += h
        if r["type"] == "data":
            data_idx += 1

    end_y = y
    draw.rectangle([x, start_y, x2, end_y], outline=(170, 170, 170), width=1)

    parity_label = {
        "single": "单周（斜杠前）",
        "double": "双周（斜杠后）",
        "all": "未指定",
    }.get(week_parity, str(week_parity))

    draw.text(
        (margin, y + 3),
        f"分段：上午 / 下午 / 晚自习   晚自习单双周：{parity_label}   生成：{datetime.now().strftime('%m-%d %H:%M')}",
        fill=(140, 140, 140),
        font=ft_foot,
    )
    if no_evening_semantics:
        draw.text(
            (margin, y + 22),
            "该源未提供晚自习数据，不表示无课",
            fill=(128, 128, 128),
            font=ft_foot,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=94)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schedule-json",
        default=default_schedule_json(),
    )
    parser.add_argument("--classes", default="2403班,2404班")
    parser.add_argument("--title", default="2025-2026第二学年高二年级")
    parser.add_argument("--subtitle", default="吕晓瑞")
    parser.add_argument("--subject", default="物理")
    parser.add_argument(
        "--week-parity",
        choices=["single", "double", "all"],
        default="all",
        help="单双周口径：single=单周(斜杠前)，double=双周(斜杠后)，all=两者都算",
    )
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
        default="data/reports/printables/个人周课表-标准规范版.jpg",
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
        args.week_parity,
        Path(args.out),
        slot_time,
        source_kind,
        source_has_evening,
    )
    print(Path(args.out))


if __name__ == "__main__":
    main()
