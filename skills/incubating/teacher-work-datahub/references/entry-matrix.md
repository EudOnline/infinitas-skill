# Teacher Work DataHub 入口总览

更新时间：2026-03-10

## 1. 查询类（推荐直接调用）

| 能力 | 标准入口 | 说明 |
|---|---|---|
| 教师查询 | `scripts/query/query_teacher.py` | 查某老师任教班级、学科、来源 |
| 班级查询 | `scripts/query/query_class.py` | 查某班任课教师 |
| 教学进度自然语言查询 | `scripts/query/query_progress_nl_datahub.py` | 直接返回中文答案 |
| 教学进度范围查询 | `scripts/query/query_progress_scope_datahub.py` | 返回结构化范围结果 |
| 教学进度 catalog 查询 | `scripts/query/query_progress_catalog_datahub.py` | 查教学进度记录台账 |
| source trace | `scripts/query/query_source_trace.py` | 按 domain/kind/semester/status 查来源记录 |
| active timetable source | `scripts/query/query_active_timetable_source.py` | 查某学期某类课表当前 active 记录 |
| teacher context 解析 | `scripts/query/resolve_teacher_context.py` | 老师 -> 班级/学科/年级 |

---

## 2. 解析 / 入库类

| 能力 | 标准入口 | 说明 |
|---|---|---|
| 教师配备表解析 | `scripts/parsers/parse_teacher_allocation.py` | parser 本体 |
| 教师配备表解析运行器 | `scripts/parsers/parse_teacher_allocation_runner.py` | 自动选带 `xlrd` 的 Python 环境 |
| sources catalog 更新 | `scripts/registry/update_sources_catalog.py` | 新 raw/curated 记录入总台账 |
| 旧 sources 迁移引导 | `scripts/registry/bootstrap_from_existing_sources.py` | 从既有课表/配备表迁入 datahub |
| 旧 teaching-progress 迁移引导 | `scripts/registry/bootstrap_teaching_progress_sources.py` | 从旧 progress 台账迁入 datahub |

---

## 3. 索引 / 视图重建类

| 能力 | 标准入口 | 说明 |
|---|---|---|
| active source 视图 | `scripts/registry/rebuild_active_sources.py` | 重建 active_sources |
| teacher index | `scripts/registry/rebuild_teacher_index.py` | 重建 teacher_index |
| class index | `scripts/registry/rebuild_class_index.py` | 重建 class_index |
| source lineage | `scripts/registry/rebuild_source_lineage.py` | 重建 lineage 视图 |

---

## 4. 上下文 / override 类

| 能力 | 标准入口 | 说明 |
|---|---|---|
| semester context 设置 | `scripts/query/set_semester_context_datahub.py` | 设置当前城市/学年/学期/学段 |
| user override 设置 | `scripts/query/set_user_override.py` | 设置老师级 override |

---

## 5. 报告 / 输出类

| 能力 | 标准入口 | 说明 |
|---|---|---|
| 教学进度摘要 | `scripts/reports/render_progress_summary_datahub.py` | 输出到 datahub outputs |
| 教学进度复核清单 | `scripts/reports/generate_review_checklist_datahub.py` | 输出到 datahub outputs |

---

## 5.1 回归 / 自检类

| 能力 | 标准入口 | 说明 |
|---|---|---|
| Feishu adapter 集成回归 | `skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py` | 当前已达 12/12 全通过 |
| datahub 总自检 runner | `skills/teacher-work-datahub/scripts/query/selfcheck_all.py` | 一次运行 teacher_context / active_sources / teaching_progress / source_trace_lineage / receipt_outputs / query_source_trace / query_progress_scope |
| datahub 正式健康检查入口 | `skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py` | 输出人类可读摘要 + JSON/TXT 报告；extended 模式可选附带 Feishu adapter 集成检查 |

---

## 6. 兼容层（wrapper）

以下入口保留给旧 skill / 旧调用方式使用，但新逻辑不建议再写进去：

### 教学进度（已并入 teacher-work-datahub）
- `skills/teacher-work-datahub/scripts/progress/query_progress_nl.py`
- `skills/teacher-work-datahub/scripts/progress/query_progress_scope.py`
- `skills/teacher-work-datahub/scripts/progress/query_progress_catalog.py`
- `skills/teacher-work-datahub/scripts/progress/set_progress_context.py`
- `skills/teacher-work-datahub/scripts/progress/answer_progress_query.py`
- `skills/teacher-work-datahub/scripts/progress/render_progress_summary.py`
- `skills/teacher-work-datahub/scripts/progress/generate_review_checklist.py`
- `skills/teacher-work-datahub/scripts/progress/ingest_progress_record.py`

### 教师配备表解析（已并入 teacher-work-datahub）
- `skills/teacher-work-datahub/scripts/parsers/parse_teacher_allocation.py`
- `skills/teacher-work-datahub/scripts/parsers/parse_teacher_allocation_runner.py`

### Feishu adapter（已迁入 teacher-work-datahub）
- `skills/teacher-work-datahub/scripts/adapters/feishu/source_trace.py`
- `skills/teacher-work-datahub/scripts/adapters/feishu/query_active_timetable_source.py`

---

## 7. 使用建议

### 推荐顺序
1. 新开发 / 新调用：优先直接用 datahub 标准入口
2. 旧流程兼容：走 wrapper，但不要再往 wrapper 里堆核心逻辑
3. 真相读取：优先 `catalog/ + curated/ + indexes/`
4. 输出读取：优先 `outputs/`

### 不推荐
- 不推荐继续把旧 `data/schedules/...` / `data/teaching-progress/...` 当唯一标准入口
- 不推荐在旧 skill 中继续复制一份 datahub 已有逻辑
