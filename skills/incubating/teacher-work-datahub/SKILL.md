---
name: teacher-work-datahub
description: 统一管理教师配备表、课表、教学进度表等教师工作数据。用于原始文件归档、结构化解析、active/archived 版本管理、教师/班级索引构建、个人课表生成、教学进度查询与数据追溯。适用于用户上传教师配备表、课表、教学进度表，或询问“某老师教哪几个班”“某班任课老师是谁”“本学期课表/考试范围”等场景。
---

# Teacher Work DataHub

## 发布定位（当前）
本技能适合作为 **workspace-scoped / private / incubating** 技能发布。

- 它优先面向教师工作数据目录与既有数据资产，而不是“零配置公共工具”
- `core`：应尽量只依赖 `teacher-work-datahub` 自身脚本与数据结构
- `extended`：允许存在可选集成检查（例如与 Feishu adapter 联调）
- 若外部适配层不存在，`extended` 检查应 **skip 而不是 fail**
- 除飞书适配外，教师数据、课表生成、交付回执、自检等自建能力应尽量内包在本技能内
- 若作为 registry 候选提交，建议明确标注：**not a zero-config public skill**

## 启动要求（新环境）
新环境第一次使用本技能时，**先跑 bootstrap**：

```bash
python3 skills/teacher-work-datahub/scripts/registry/bootstrap_report.py --json
```

作用：
- 检查 datahub catalog / indexes 是否齐备
- 检查 OCR key 是否已配置
- 在未配置 OCR key 时输出清晰的 `suggested_actions`
- 作为后续 smoke / selfcheck 前的入口检查

若报告提示缺 catalog 或索引，再按 `suggested_actions` 依次执行 bootstrap / rebuild。

## 何时使用
当出现以下任务时启用本技能：
- 上传教师配备表
- 上传“班主任/任课教师配备一览表”
- 上传 WPS / Excel `.xls` 合并单元格教师配备表
- 需要先反合并填充，再结构化解析教师配备关系
- 上传年级课表 / 全校课表
- 上传教学进度表 / 考试范围表
- 上传教学安排表 / 周次安排表
- 询问期中 / 期末考试范围
- 需要 OCR 识别教学进度总表后入库
- 询问某老师任教班级
- 询问某班任课老师
- 生成个人周课表 / 学期课表
- 查询当前 active 数据源
- 查询某学期教学进度或考试范围
- 需要把资料归档、结构化、长期保存并可追溯

## 核心原则
1. 原始数据与加工数据严格分层：
   - `raw/`：原始数据层，只进不改
   - `curated/`：加工数据层，结构化结果与共享索引统一在此
2. `outputs/` 不是数据真相，只是交付结果
3. 下游统一读取 `curated/` 与 `indexes/`，不直接读取 scattered 原始文件
4. 同类型 + 同学期默认仅一个 `active`
5. 严禁猜测；缺数据时明确提示
6. 所有回答与交付必须可追溯到 source record

## 统一数据流
1. 接收文件并识别类型
2. 归档到 `raw/`
3. 登记 `catalog/sources.json`
4. 执行对应 parser 输出到 `curated/`
5. 更新 active/archived 状态
6. 重建共享索引：
   - `active_sources.json`
   - `teacher_index.json`
   - `class_index.json`
   - `semester_context.json`
7. 执行查询 / 出图 / 报告 / 飞书发送

## 数据优先级
默认优先级如下：
1. 用户本次明确指定
2. `user_overrides.json`
3. 当前 active 结构化数据
4. 历史记忆
5. 不猜测

## 关键文件
- 架构说明：`references/architecture.md`
- 统一 schema：`references/schemas.md`
- 迁移方案：`references/migration-plan.md`
- 迁移现状与标准入口：`references/migration-status.md`
- 入口总览 / 命令矩阵：`references/entry-matrix.md`
- 健康检查说明：`references/healthcheck.md`
- 运行依赖与环境预期：`references/runtime-deps.md`
- 发布前检查单：`references/release-checklist.md`
- sample/fixtures 方案：`references/sample-fixtures-plan.md`
- 阶段性维护总结：`references/maintenance-summary-2026-03-10.md`

## 常见脚本入口
- 教师配备表解析：`scripts/parsers/parse_teacher_allocation.py`
- 教师配备表执行入口（自动选择可用 Python 环境）：`scripts/parsers/parse_teacher_allocation_runner.py`
- source 台账更新：`scripts/registry/update_sources_catalog.py`
- 教学进度自然语言查询：`scripts/progress/query_progress_nl.py`
- 教学进度范围查询：`scripts/progress/query_progress_scope.py`
- 教学进度 OCR 入库：`scripts/progress/ingest_progress_record.py`
- active 视图重建：`scripts/registry/rebuild_active_sources.py`
- 教师索引重建：`scripts/registry/rebuild_teacher_index.py`
- 班级索引重建：`scripts/registry/rebuild_class_index.py`
- 教师查询：`scripts/query/query_teacher.py`
- 班级查询：`scripts/query/query_class.py`
- 教师个人课表主流程：`scripts/delivery/build_teacher_semester_timetable.py`
