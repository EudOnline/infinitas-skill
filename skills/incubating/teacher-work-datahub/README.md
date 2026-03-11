# Teacher Work DataHub Quick Start

> 发布定位：这是一个 **workspace-scoped teacher-work datahub** 技能，适合 private / incubating 发布；它不是零配置的通用公共技能。

## Fresh Agent Quick Path
如果你是在一个新环境里第一次接手这个 skill，先不要假设真实业务数据已经存在。

### 推荐最短路径（reviewer-safe）
1. 安装依赖：
   ```bash
   pip install -r skills/teacher-work-datahub/requirements.txt
   ```
2. 进入 fixture 模式：
   ```bash
   export TEACHER_WORK_DATAHUB_FIXTURE=minimal-datahub
   ```
3. 加载最小 synthetic fixtures：
   ```bash
   python3 skills/teacher-work-datahub/scripts/tests/load_minimal_fixture.py --workspace-root /tmp/twd-reviewer-demo
   ```
4. 运行统一自检：
   ```bash
   python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py --workspace-root /tmp/twd-reviewer-demo
   ```
5. 运行健康检查：
   ```bash
   python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core --workspace-root /tmp/twd-reviewer-demo
   ```

### 注意
- 不要先假设真实 `data/teacher-work-datahub` 已经可用
- 不要先假设 Feishu / OCR 已经配置完成
- 想验证安装与最小可用性时，优先走 fixture 路径
- 生产数据链路应在 fixture 验证通过后再接入

## 快速判断系统是否健康
先跑（core 模式）：

```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py
```

或显式写法：

```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core
```

如果要顺带检查 Feishu adapter 集成层，用 extended 模式：

```bash
python3 skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode extended
```

看总报告：
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.json`
- `data/teacher-work-datahub/outputs/healthchecks/healthcheck-datahub.txt`

底层自检入口仍可单独运行：
- `python3 skills/teacher-work-datahub/scripts/query/selfcheck_all.py`

---

## 涉及 Feishu adapter 集成时
可单独再跑 adapter 集成回归：

```bash
python3 skills/teacher-work-datahub/scripts/adapters/feishu/test_timetable_pipeline_p6.py
```

看报告：
- `data/reports/teacher-semester-flow/p6/p6-report.json`
- `data/reports/teacher-semester-flow/p6/p6-report.txt`

当前基线：
- Feishu adapter 集成回归 = **12/12 全通过**

---

## 单项检查入口
- teacher context：
  ```bash
  python3 skills/teacher-work-datahub/scripts/query/selfcheck_teacher_context.py
  ```
- active sources：
  ```bash
  python3 skills/teacher-work-datahub/scripts/query/selfcheck_active_sources.py
  ```
- teaching progress：
  ```bash
  python3 skills/teacher-work-datahub/scripts/query/selfcheck_teaching_progress.py
  ```
- source trace / lineage：
  ```bash
  python3 skills/teacher-work-datahub/scripts/query/selfcheck_source_trace_lineage.py
  ```
- receipt / outputs：
  ```bash
  python3 skills/teacher-work-datahub/scripts/query/selfcheck_receipt_outputs.py
  ```

---

## 看更完整说明
- 健康检查说明（完整排障文档）：`skills/teacher-work-datahub/references/healthcheck.md`
- 迁移现状（里程碑 / 当前基线）：`skills/teacher-work-datahub/references/migration-status.md`
- 入口总览（命令矩阵）：`skills/teacher-work-datahub/references/entry-matrix.md`
- 运行依赖与环境预期：`skills/teacher-work-datahub/references/runtime-deps.md`
- 发布前检查单：`skills/teacher-work-datahub/references/release-checklist.md`
- sample/fixtures 方案：`skills/teacher-work-datahub/references/sample-fixtures-plan.md`
- reviewer demo 实跑记录：`skills/teacher-work-datahub/references/reviewer-demo-run.md`
- 提交说明 / review 文案：`skills/teacher-work-datahub/references/submission-notes.md`
- 完整依赖清单：`skills/teacher-work-datahub/requirements.txt`
