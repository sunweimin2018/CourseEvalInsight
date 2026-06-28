---
name: prd-sync-requirement
description: 用户要求以后所有修改都需要同步更新到需求文档（PRD）
metadata:
  type: feedback
---

每次用户提出修改需求后，在完成代码修改的同时，必须将改动整理到 `docs/design/多Excel数据动态生成数据分析报告系统-PRD需求文档（Vue3+Django、适配Claude Code开发）.md` 中对应的章节，包括版本号更新、功能描述修改、接口变更等。

**Why:** 用户希望通过PRD文档完整追踪所有需求变更和实现细节。

**How to apply:** 每次代码修改完成后，定位PRD中相关章节进行同步更新，并在版本表中新增一条版本记录。
