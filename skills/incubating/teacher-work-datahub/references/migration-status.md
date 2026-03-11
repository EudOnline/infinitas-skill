# Teacher Work DataHub 迁移状态

更新时间：2026-03-10

## 目标
将教师配备、个人课表、教学进度三条能力线逐步收口到 `teacher-work-datahub`：
- 旧 skill 保留为兼容入口
- 新查询、索引、台账、追溯逐步统一到 datahub
- 默认读路径逐步改为 datahub-first，旧路径仅做 fallback

---

## 一、已完成的 datahub-first / datahub-backed 入口

### A. 教学进度（teaching-progress）
已完成并入 datahub：

- `skills/teacher-work-datahub/scripts/progress/query_progress_nl.py`
- `skills/teacher-work-datahub/scripts/progress/query_progress_scope.py`
- `skills/teacher-work-datahub/scripts/progress/query_progress_catalog.py`
- `skills/teacher-work-datahub/scripts/progress/set_progress_context.py`
- `skills/teacher-work-datahub/scripts/progress/answer_progress_query.py`
- `skills/teacher-work-datahub/scripts/progress/render_progress_summary.py`
- `skills/teacher-work-datahub/scripts/progress/generate_review_checklist.py`
- `skills/teacher-work-datahub/scripts/progress/ingest_progress_record.py`
- `skills/teacher-work-datahub/scripts/progress/run_progress_ocr_tables.py`
- `skills/teacher-work-datahub/scripts/progress/parse_progress_ocr_tables.py`
- `skills/teacher-work-datahub/scripts/progress/parse_progress_markdown_table.py`
- `skills/teacher-work-datahub/scripts/progress/progress_query_utils.py`

对应 datahub-backed 查询/报告入口：
- `scripts/query/query_progress_nl_datahub.py`
- `scripts/query/query_progress_scope_datahub.py`
- `scripts/query/query_progress_catalog_datahub.py`
- `scripts/query/set_semester_context_datahub.py`
- `scripts/query/answer_progress_query_datahub.py`
- `scripts/reports/render_progress_summary_datahub.py`
- `scripts/reports/generate_review_checklist_datahub.py`

- 教学进度职责已收口到 datahub，本地可继续维持单技能结构

### B. 教师配备（teacher-allocation）
已完成：
- `skills/teacher-work-datahub/scripts/parsers/parse_teacher_allocation.py`
  - datahub parser 本体
- `skills/teacher-work-datahub/scripts/parsers/parse_teacher_allocation_runner.py`
  - 自动选择带 `xlrd` 的 Python 运行环境
- 旧 parser skill 的职责已收口到 datahub，本地可继续删除独立 skill 目录

### C. 个人课表 / 交付（delivery core + Feishu adapter）
已完成：
- `skills/teacher-work-datahub/scripts/adapters/feishu/source_trace.py`
  - 作为 Feishu adapter 兼容入口，转调 datahub query
- `skills/teacher-work-datahub/scripts/adapters/feishu/query_active_timetable_source.py`
  - 作为 Feishu adapter 兼容入口，转调 datahub active source query
- `skills/teacher-work-datahub/scripts/delivery/build_teacher_semester_timetable.py`
  - datahub core 主流程已内包
  - 默认 teacher_allocation 输入优先读 datahub curated
  - teacher context / active source 已优先走 datahub
  - 已补 teacher_index 当前 sheet 收敛、hint 消歧、无 hint 歧义拦截
  - datahub core 不内置飞书发送；发送由 adapter 层处理
- `skills/teacher-work-datahub/scripts/delivery/generate_timetable_image.py`
  - 周课表出图已内包到 datahub
- `skills/teacher-work-datahub/scripts/delivery/generate_semester_timetable_image.py`
  - 学期课表出图已内包到 datahub
- `skills/teacher-work-datahub/scripts/delivery/delivery_receipt.py`
  - 标准交付回执已内包到 datahub
- `skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py`
  - 当前作为 Feishu adapter 集成回归入口
  - 当前回归结果：**12/12 全通过**
- `skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py`
  - 已提供正式健康检查入口
  - 支持健康状态分级：`healthy / degraded / unhealthy`
  - 支持 `core / extended` 两种检查模式

---

## 二、当前标准入口（推荐）

### 查询类
- 教学进度自然语言：`skills/teacher-work-datahub/scripts/query/query_progress_nl_datahub.py`
- 教学进度 scope：`skills/teacher-work-datahub/scripts/query/query_progress_scope_datahub.py`
- 教学进度 catalog：`skills/teacher-work-datahub/scripts/query/query_progress_catalog_datahub.py`
- 教师查询：`skills/teacher-work-datahub/scripts/query/query_teacher.py`
- 班级查询：`skills/teacher-work-datahub/scripts/query/query_class.py`
- source trace：`skills/teacher-work-datahub/scripts/query/query_source_trace.py`
- active timetable source：`skills/teacher-work-datahub/scripts/query/query_active_timetable_source.py`

### 索引 / 上下文类
- active source 重建：`scripts/registry/rebuild_active_sources.py`
- teacher index 重建：`scripts/registry/rebuild_teacher_index.py`
- class index 重建：`scripts/registry/rebuild_class_index.py`
- source lineage 重建：`scripts/registry/rebuild_source_lineage.py`
- semester context 设置：`scripts/query/set_semester_context_datahub.py`
- user override 设置：`scripts/query/set_user_override.py`

### 报告 / 输出类
- 教学进度摘要：`scripts/reports/render_progress_summary_datahub.py`
- 教学进度复核清单：`scripts/reports/generate_review_checklist_datahub.py`

---

## 三、兼容层（保留，但不建议新增逻辑）

下列旧入口保留的主要目的：
- 不打断既有调用方式
- 便于渐进迁移
- 作为 datahub 的 compatibility wrapper

原则：
- 新逻辑优先写到 datahub
- 旧 skill 脚本尽量只做参数透传与最小兼容
- 不再往旧实现里继续堆核心业务逻辑

---

## 四、默认读路径策略

### 当前策略
- **优先读 datahub curated / indexes / outputs**
- 若 datahub 对应产物尚未铺满，再 fallback 到旧路径

### 典型场景
- teacher_allocation：优先 datahub curated latest
- timetable image generators：优先 datahub 默认课表路径
- timetable source trace：优先 datahub catalog/indexes
- teaching-progress query：优先 datahub catalog/context/outputs

---

## 五、仍处于过渡期的点

1. `active_sources.json` 存在键名过渡：
   - 兼容 `by_semester`
   - 兼容 `semesters`

2. 部分文档 / spec / 示例命令仍引用旧路径：
   - `data/schedules/...`
   - `data/teaching-progress/...`
   这些需要逐步改成 datahub-first 描述

3. 部分测试脚本仍直接引用旧文件：
   - 后续宜改成通过 datahub 索引解析实际输入

---

## 六、当前健康基线（2026-03-10）
本节只保留当前稳定基线；完整运行说明与排障顺序请看 `references/healthcheck.md`。

- 正式健康检查入口：`skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py`
- 当前 `selfcheck_all.py`：**7/7 全通过**
- 当前 Feishu adapter 集成回归：**12/12 全通过**
- 当前健康状态分级：
  - `healthy`：selfcheck_all 通过；若启用 adapter 集成检查，则其也通过
  - `degraded`：selfcheck_all 通过，但 adapter 集成检查失败
  - `unhealthy`：selfcheck_all 失败

## 七、后续建议

### 下一阶段优先事项
1. 进一步统一 outputs / receipts / trace 字段命名
2. 继续收口残余文档 / spec 中的旧路径描述
3. 视稳定度逐步弱化旧目录的“标准入口”地位
4. 若后续检查项继续增长，可考虑按“core / extended”分组执行

### 不建议的做法
- 不要在旧 skill 中继续增加大量新业务逻辑
- 不要形成“旧实现一套、datahub 实现一套”的双轨长期维护
- 不要在未补 trace / lineage / active index 的情况下直接跳过 datahub 台账
