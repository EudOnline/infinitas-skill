# Teacher Work DataHub 阶段性维护总结（2026-03-10）

## 1. 阶段结论
teacher-work-datahub 已从“迁移中的统一层”进入“可维护、可回归、可自检”的稳定阶段。

当前已形成：
- 统一入口
- compatibility wrapper
- 主流程回归
- 小自检体系
- 正式健康检查入口
- 分层文档体系

---

## 2. 三条主线当前状态

### 2.1 teaching-progress
已完成：
- query 入口转到 datahub
- context 转到 datahub
- report / checklist 输出转到 datahub
- 旧入口薄壳化

### 2.2 teacher-allocation
已完成：
- parser 入口薄壳化
- parser runner 补齐
- 自动选择带 `xlrd` 的 Python 环境
- 文档同步到 datahub-first 口径

### 2.3 personal timetable
已完成：
- source trace 改为 datahub 薄壳
- active timetable source 查询改到 datahub
- 主流程优先走 teacher_index / active source
- 默认 teacher_allocation / schedule 路径开始 datahub-first
- 文档 / spec / 测试已逐步同步

---

## 3. 主流程与稳定基线

### 3.1 Feishu adapter 集成回归
- 入口：`skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py`
- 当前结果：**12/12 全通过**

### 3.2 健康检查基线
- `skills/teacher-work-datahub/scripts/query/selfcheck_all.py` → **7/7 全通过**
- `skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core` → `healthy`
- `skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode extended` → `healthy`

### 3.3 健康状态分级
- `healthy`：selfcheck_all 通过；若启用 Feishu adapter 集成检查，则其也通过
- `degraded`：selfcheck_all 通过，但 Feishu adapter 集成检查失败
- `unhealthy`：selfcheck_all 失败

---

## 4. 已建立的质量体系

### 4.1 正式健康检查入口
- `skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py`

支持：
- `--mode core`
- `--mode extended`
- 兼容 `--with-p6`

输出：
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.json`
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.txt`

### 4.2 datahub 小自检集合
- `selfcheck_teacher_context.py`
- `selfcheck_active_sources.py`
- `selfcheck_teaching_progress.py`
- `selfcheck_source_trace_lineage.py`
- `selfcheck_receipt_outputs.py`
- `selfcheck_query_source_trace.py`
- `selfcheck_query_progress_scope.py`

### 4.3 总自检入口
- `skills/teacher-work-datahub/scripts/query/selfcheck_all.py`

---

## 5. 这一阶段的关键修复点

### 5.1 teacher context
核心脚本：
- `scripts/query/resolve_teacher_context.py`

关键修复：
- current sheet 收敛
- hint-based 消歧
- 多候选且无 hint 的歧义拦截
- tolerance / disambiguation 文案对齐

### 5.2 parser runtime
核心脚本：
- `scripts/parsers/parse_teacher_allocation_runner.py`

关键修复：
- 自动选择支持 `xlrd` 的 Python 环境
- 避免 parser 因默认解释器缺依赖而不可用

### 5.3 query / trace / receipt consistency
关键修复：
- source trace 与 lineage 自检打通
- receipt / outputs 一致性检查补齐
- query_progress_scope / query_source_trace 已补 targeted checks

---

## 6. 当前文档分工

### 6.1 README.md
定位：
- quick start
- 最短入口说明

### 6.2 references/healthcheck.md
定位：
- 完整健康检查说明
- 失败后的排障顺序

### 6.3 references/migration-status.md
定位：
- 迁移里程碑
- 当前稳定基线

### 6.4 references/entry-matrix.md
定位：
- 命令矩阵 / 入口总览

---

## 7. 当前维护原则
- 新逻辑优先写入 datahub，旧 skill 只保留 wrapper 职责。
- 优先保证 `catalog + curated + active_sources + indexes` 作为真相层。
- 日常检查先跑 `healthcheck_datahub.py --mode core`。
- 若改动 Feishu adapter 或发送集成层，再跑 `healthcheck_datahub.py --mode extended`。
- 若新增自检，建议顺序为：单独跑通 → 并入 `selfcheck_all.py` → 更新 healthcheck 文档。

---

## 8. 后续建议
### 8.1 优先级较高
1. 进一步统一 outputs / receipts / trace 字段命名
2. 继续收口残余文档 / spec 中的旧路径描述
3. 若后续检查项继续增长，可按 `core / extended` 分组扩展自检

### 8.2 不建议的做法
- 不要在旧 skill 中继续堆核心业务逻辑
- 不要让 scattered JSON 重新成为默认真相来源
- 不要形成“旧实现一套、datahub 实现一套”的双轨长期维护

---

## 9. 阶段里程碑一句话总结
**Teacher Work DataHub 已完成从“统一化改造”到“可维护稳定基线”的跨越。**
