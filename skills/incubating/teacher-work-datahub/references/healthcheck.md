# Teacher Work DataHub 健康检查说明

更新时间：2026-03-10

## 1. 目的
这份文档用于说明 teacher-work-datahub 当前可用的健康检查入口、推荐执行顺序、结果输出位置，以及当检查失败时的排障方向。

文档定位：
- `README.md` = quick start
- `healthcheck.md` = 完整健康检查与排障说明
- `migration-status.md` = 迁移里程碑与当前稳定基线

目标是让后续维护者可以快速回答三个问题：
1. 现在系统整体是否健康？
2. 哪一层出了问题？
3. 应该先修哪里？

---

## 2. 推荐检查顺序

### 第一层：正式健康检查入口（推荐）
优先直接运行：

```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py
```

等价于显式指定 core 模式：

```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core
```

若同时要带上 Feishu adapter 集成回归，推荐使用 extended 模式：

```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode extended
```

兼容参数 `--with-p6` 仍可使用。

适用场景：
- 改完 datahub 脚本后做快速健康检查
- 想先判断“系统大面上是否正常”
- 需要一份人类可读摘要 + 机器可读 JSON 报告

结果输出：
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.json`
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.txt`

内部会调用：
- `selfcheck_all.py`
- （可选）Feishu adapter 集成回归 `skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py`

当前覆盖：
- teacher_context
- active_sources
- teaching_progress
- source_trace_lineage
- receipt_outputs
- query_source_trace
- query_progress_scope

---

### 第二层：总自检（底层入口）
若只想跑 datahub 小自检集合，也可直接运行：

```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py
```

结果输出：
- `data/teacher-work-datahub/outputs/selfchecks/selfcheck-all.json`

---

### 第二层：Feishu adapter 集成回归
若涉及飞书发送适配、adapter 包装层、发送回执联调，继续运行：

```bash
python3 skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py
```

结果输出：
- `data/reports/teacher-semester-flow/p6/p6-report.json`
- `data/reports/teacher-semester-flow/p6/p6-report.txt`

当前状态：
- **12/12 全通过**

适用场景：
- 改动 Feishu adapter 包装层
- 改动飞书发送适配逻辑
- 改动 adapter 侧回执联调行为

---

## 3. 单项自检入口

### 3.1 teacher context
```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_teacher_context.py
```

当前检查点：
- current sheet 收敛是否正确
- 姓名容错文案是否正确

输出：
- `data/teacher-work-datahub/outputs/selfchecks/teacher-context-selfcheck.json`

当它失败时，优先排查：
- `scripts/query/resolve_teacher_context.py`
- `data/teacher-work-datahub/curated/indexes/teacher_index.json`
- teacher_index 是否为最新 active source 重建结果

---

### 3.2 active sources
```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_active_sources.py
```

当前检查点：
- S2 的 `teacher_allocation`
- S2 的 `grade_schedule_with_selfstudy`
- S2 的 `school_schedule_no_selfstudy`

输出：
- `data/teacher-work-datahub/outputs/selfchecks/active-sources-selfcheck.json`

当它失败时，优先排查：
- `data/teacher-work-datahub/curated/indexes/active_sources.json`
- `scripts/registry/rebuild_active_sources.py`
- `data/teacher-work-datahub/catalog/sources.json`

---

### 3.3 teaching progress
```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_teaching_progress.py
```

当前检查点：
- `query_progress_scope_datahub.py`
- `query_progress_nl_datahub.py`

输出：
- `data/teacher-work-datahub/outputs/selfchecks/teaching-progress-selfcheck.json`

当它失败时，优先排查：
- `scripts/query/query_progress_scope_datahub.py`
- `scripts/query/query_progress_nl_datahub.py`
- `data/teacher-work-datahub/catalog/sources.json`
- `data/teacher-work-datahub/curated/indexes/semester_context.json`
- 目标 `curated_path` 是否仍存在

---

### 3.4 source trace / lineage
```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_source_trace_lineage.py
```

当前检查点：
- source trace 是否能查到关键 active record
- lineage 是否包含关键 active record

输出：
- `data/teacher-work-datahub/outputs/selfchecks/source-trace-lineage-selfcheck.json`

当它失败时，优先排查：
- `scripts/query/query_source_trace.py`
- `scripts/registry/rebuild_source_lineage.py`
- `data/teacher-work-datahub/curated/lineage/source_lineage.json`
- `data/teacher-work-datahub/catalog/sources.json`

---

### 3.5 receipt / outputs 一致性
```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_receipt_outputs.py
```

当前检查点：
- `outputs.*` 与 `delivery_receipt.output_file_paths.*` 是否一致
- receipt 中 `source_trace.active_record_id` 是否与 selected_source trace 一致

输出：
- `data/teacher-work-datahub/outputs/selfchecks/receipt-outputs-selfcheck.json`

当它失败时，优先排查：
- `skills/teacher-work-datahub/scripts/delivery/delivery_receipt.py`
- `skills/teacher-work-datahub/scripts/delivery/build_teacher_semester_timetable.py`
- 目标 case json 的 `outputs` / `delivery_receipt` 结构

---

## 4. 失败后的推荐排障顺序

### 场景 A：总自检失败
先看：
1. `selfcheck-all.json` 中是哪一项 failed
2. 失败项的 `stdout/stderr`
3. 对应单项自检的输出 JSON

不要一上来就重跑所有大回归；先缩小到失败的那一层。

---

### 场景 B：Feishu adapter 集成失败，但 selfcheck_all 通过
通常说明：
- datahub core 仍然健康
- 但 adapter 包装层或飞书发送集成行为回归了

优先排查：
- `skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py`
- Feishu adapter 包装层
- 飞书发送适配逻辑
- adapter 侧回执联调

---

### 场景 C：active_sources 失败
通常说明：
- source arbitration 出问题
- 或 catalog / active index 未重建

优先操作：
```bash
python3 skills/teacher-work-datahub/scripts/registry/rebuild_active_sources.py
```

必要时继续检查：
- `catalog/sources.json`
- 关键 record 是否被错误标为 archived

---

### 场景 D：teacher_context 失败
通常说明：
- teacher_index 未更新
- 或当前 sheet 收敛 / hint 消歧逻辑回归

优先操作：
```bash
python3 skills/teacher-work-datahub/scripts/registry/rebuild_teacher_index.py
python3 skills/teacher-work-datahub/scripts/query/selfcheck_teacher_context.py
```

---

### 场景 E：teaching_progress 失败
优先区分：
- 是 scope 查询失败
- 还是 NL 查询失败

建议先单独跑：
```bash
python3 skills/teacher-work-datahub/scripts/query/query_progress_scope_datahub.py --grade 高二 --subject 物理 --exam midterm
python3 skills/teacher-work-datahub/scripts/query/query_progress_nl_datahub.py --text "太原市高二物理期中范围" --format text
```

---

## 5. 当前稳定基线
截至 2026-03-10，当前稳定基线为：

### Feishu adapter 集成回归
- `test_timetable_pipeline_p6.py` → **12/12 全通过**

### 小自检
- `selfcheck_teacher_context.py` → 通过
- `selfcheck_active_sources.py` → 通过
- `selfcheck_teaching_progress.py` → 通过
- `selfcheck_source_trace_lineage.py` → 通过
- `selfcheck_receipt_outputs.py` → 通过
- `selfcheck_all.py` → **5/5 全通过**

---

## 6. 使用建议

### 日常改动后
推荐最少执行：
```bash
python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py
```

### 改动 Feishu adapter 后
再补：
```bash
python3 skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py
```

### 改动 registry / active 相关逻辑后
建议顺带重建：
```bash
python3 skills/teacher-work-datahub/scripts/registry/rebuild_active_sources.py
python3 skills/teacher-work-datahub/scripts/registry/rebuild_teacher_index.py
python3 skills/teacher-work-datahub/scripts/registry/rebuild_class_index.py
python3 skills/teacher-work-datahub/scripts/registry/rebuild_source_lineage.py
```

---

## 7. 维护原则
- 先跑总自检，再定位到单项自检。
- 先确认索引与 active source 是否健康，再怀疑主流程。
- 若是 datahub-first 入口与 wrapper 行为不一致，优先修 datahub，再修 wrapper。
- 不要让旧路径重新成为默认真相；真相应保持在 `catalog + curated + active_sources + indexes`。
