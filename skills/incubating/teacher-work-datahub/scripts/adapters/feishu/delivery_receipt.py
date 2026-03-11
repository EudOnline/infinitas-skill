#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thin wrapper to teacher-work-datahub delivery_receipt."""

from __future__ import annotations

import runpy
from pathlib import Path

TARGET = Path(__file__).resolve().parents[5] / "skills" / "teacher-work-datahub" / "scripts" / "delivery" / "delivery_receipt.py"

if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
