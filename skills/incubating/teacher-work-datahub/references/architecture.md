# Architecture

## 1. 目标
teacher-work-datahub 用于把教师工作相关数据统一纳入一个可追溯、可查询、可交付的数据系统。

## 2. 数据分层
### raw
原始文件层，只进不改，用于追溯与重新解析。

### curated
加工层，保存结构化 JSON、共享索引、差异结果、lineage。

### outputs
输出层，保存图片、PDF、报告、发送回执；不是数据真相。

## 3. 统一主链路
ingest -> catalog -> parse -> curated -> active arbitration -> rebuild indexes -> query/delivery

## 4. source of truth
- 原始文件真相：`raw`
- 当前业务真相：`curated + active_sources + indexes`
- 不允许下游直接以 scattered JSON 作为权威来源

## 5. active/archived 规则
- 同类型 + 同学期默认一个 active
- 新版本 active，旧版本 archived
- 若用户明确要求并行保留，则 metadata 标记 `parallel_allowed=true`

## 6. 冲突处理
出现以下冲突时必须显式提示：
- 用户默认口径 vs active 数据源
- 教师配备表 vs 课表班级集合
- 教学进度学期 vs 当前学期
- 历史结果 vs 当前 active 结果
