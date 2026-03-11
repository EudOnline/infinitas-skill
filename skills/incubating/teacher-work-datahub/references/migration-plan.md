# Migration Plan

## Phase 1
- 建立 `teacher-work-datahub` skill 骨架
- 建立统一数据目录：`raw/` `curated/` `outputs/` `catalog/`
- 迁移教师配备表 parser
- 建立 `sources.json`
- 建立 `active_sources.json`
- 建立 `teacher_index.json`
- 改造课表主流程优先读取统一 teacher index

## Phase 2
- 建立 `class_index.json`
- 引入 `user_overrides.json`
- 建立统一 teacher context 解析层
- 课表主流程优先级改为：explicit > override > teacher_index > fallback

## Phase 3
- 把教学进度台账并入总 `sources.json`
- 接入 teaching-progress 的结构化记录与查询
- 统一 `semester_context.json`

## Phase 4
- 合并重复发送脚本
- 拆分 `schedule_helpers.py`
- 旧 skill 逐步转为薄壳兼容入口
