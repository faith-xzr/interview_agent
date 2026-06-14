# 动态 Rubric 简历匹配

你会收到本次 JD 的动态评分 Rubric、候选人结构化档案，以及已经校验过来源的简历证据片段。请逐条判断候选人是否覆盖每个 requirement。

# JDProfile

```json
{{JD_PROFILE_JSON}}
```

# 岗位名称上下文

`JDProfile.job_title` 是本次待匹配岗位名称。判断候选人覆盖情况时，要用岗位名称理解经验是否贴近该岗位，但最终匹配结论必须落到 Rubric 中的逐条 requirement 和可引用证据上。

# 动态评分 Rubric

```json
{{RUBRIC_JSON}}
```

# 候选人结构化档案

```json
{{CANDIDATE_PROFILE_JSON}}
```

# 可引用证据

```json
{{EVIDENCE_JSON}}
```

# 判断标准

请参考简历审计式评价，而不是只做关键词匹配：

1. **强匹配**：必须有直接证据证明候选人在相关项目/经历中实际做过该 requirement，并能看出个人职责边界、技术实现、业务场景，最好包含业务价值或量化结果。
2. **直接匹配**：简历在技能、项目、经历、教育或证书中明确覆盖 requirement，但项目深度、个人贡献或结果指标不完整。
3. **相关匹配**：技术栈、领域或经历方向相近，但缺少直接落地证据；例如只说明接触过类似工具。
4. **弱匹配**：只写熟悉/参与/负责但没有具体项目证据，或只有零散关键词，不能证明能胜任该要求。
5. **未匹配**：没有明确证据，或证据无法支撑该 requirement。

项目类、平台类、性能优化类、Agent/RAG 类 requirement 要特别关注：

- 候选人的个人职责边界是否清楚。
- 技术实现是否连接到真实业务场景。
- 是否出现业务价值或量化结果；如果没有，最多给 `直接匹配`，不要轻易给 `强匹配`。
- 不要把技术名词堆砌当成项目深度。

# 输出格式

严格返回一个 JSON 对象：

```json
{
  "matches": [
    {
      "requirement": "必须与 Rubric 中的 requirement 完全一致",
      "status": "强匹配 | 直接匹配 | 相关匹配 | 弱匹配 | 未匹配",
      "confidence": 0.82,
      "reason": "给招聘同事看的简短原因，说明匹配或缺口依据",
      "evidence_indexes": [0, 2]
    }
  ]
}
```

# 规则

1. 必须为 Rubric 中每一个 requirement 返回一条 match，不要新增 Rubric 外的要求。
2. `requirement` 必须逐字等于 Rubric 中的 requirement，方便下游校验。
3. 不要输出分数、得分、权重或任何由模型计算的分值；后端代码会根据 `status` 和 `confidence` 计算贡献分。
4. 只有引用了 `EVIDENCE_JSON` 中的证据 index，才能给出强匹配或直接匹配。
5. 如果简历没有明确覆盖，使用 `未匹配`，`confidence` 设为 0，`evidence_indexes` 设为空数组。
6. 相关经验只能给 `相关匹配` 或 `弱匹配`，不要把语义相近但没有直接证据的内容判为强匹配。
7. 不要编造证据；`evidence_indexes` 只能引用输入中存在的 index。
