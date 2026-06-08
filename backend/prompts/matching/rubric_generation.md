# JD 动态评分 Rubric 生成

你会收到已经抽取并校验过证据的 JD 结构化结果。请不要套固定模板，而是根据本次 JD 的真实要求生成一份总分 100 分的动态评分 Rubric。

# 输入

JDProfile:

```json
{{JD_PROFILE_JSON}}
```

JD facts:

```json
{{JD_FACTS_JSON}}
```

# 岗位名称上下文

`JDProfile.job_title` 是本次待匹配岗位名称。生成 Rubric 时要用它理解岗位定位和场景边界，但不要把岗位名称本身当作一条可打分 requirement；真正可打分的要求仍然必须来自 JD facts。

# 输出格式

严格返回一个 JSON 对象：

```json
{
  "rubric": [
    {
      "dimension": "面向招聘同事展示的维度名称，例如：AIGC工具生态、内容生产经验、年限与级别、行业背景、硬性门槛",
      "requirement": "从 JD facts 归纳出的单条可评分要求",
      "requirement_type": "core_skill | responsibility | project_depth | years | seniority | industry | hard_requirement | nice_to_have | other",
      "max_score": 12,
      "priority": "must_have | nice_to_have | hard_gate",
      "scoring_note": "说明为什么这条要求值得这个权重"
    }
  ]
}
```

# 规则

1. `rubric` 必须来自输入的 JD facts，不要编造 JD 没有的要求。
2. 不要固定使用六个通用维度。维度应该贴合本次 JD。
3. 一个 requirement 只表达一个可判断的要求。
4. `max_score` 总和应为 100；如果你不能精确相加，下游会归一化。
5. 明确必备、核心职责、硬性门槛、反复强调的内容应获得更高权重。
6. 加分项可以保留，但权重应低于必备项。
7. 如果多个 JD facts 语义重复，只保留信号最强的一条。
