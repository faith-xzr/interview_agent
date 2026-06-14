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

# 简历评价参考标准

生成 Rubric 时借鉴简历审计视角来分配维度和权重，但不要脱离 JD facts 编造要求：

1. **项目技术深度**：优先识别能证明真实落地能力的项目要求，包括复杂问题、架构设计、关键技术取舍、个人职责边界、业务价值或量化结果。项目类 requirement 应尽量体现“技术实现 + 业务场景 + 结果量化”的判断标准。
2. **技能匹配度**：核心技能、工具、框架、模型、平台能力应优先覆盖必备项；只作为加分项出现的技能权重应低于必备项。
3. **经验与门槛**：年限、级别、学历、证书、行业背景等硬条件应独立成项，`priority` 使用 `hard_gate` 或 `must_have`，避免被项目亮点完全抵消。
4. **内容证据完整性**：如果 JD 强调交付、优化、治理、负责范围，应生成能验证项目职责、业务闭环、指标结果的 requirement。
5. **表达与可信度**：对只堆技术名词但缺少场景、职责、结果的简历，应在 matching 阶段保守判断，所以 Rubric 要能区分“会用某技术”和“用该技术解决过真实问题”。

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
8. 如果 JD 包含项目落地、平台建设、性能优化、业务推进、Agent/RAG 等复杂场景，Rubric 应体现项目深度和业务价值，而不只是列技能关键词。
