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

# 输出格式

严格返回一个 JSON 对象：

```json
{
  "matches": [
    {
      "requirement": "必须与 Rubric 中的 requirement 完全一致",
      "status": "强匹配 | 直接匹配 | 相关匹配 | 弱匹配 | 未匹配",
      "confidence": 0.82,
      "contribution": 8.5,
      "reason": "给招聘同事看的简短原因，说明匹配或缺口依据",
      "evidence_indexes": [0, 2]
    }
  ]
}
```

# 规则

1. 必须为 Rubric 中每一个 requirement 返回一条 match，不要新增 Rubric 外的要求。
2. `requirement` 必须逐字等于 Rubric 中的 requirement，方便下游校验。
3. `contribution` 不得超过该 requirement 的 `max_score`。
4. 只有引用了 `EVIDENCE_JSON` 中的证据 index，才能给出强匹配或直接匹配。
5. 如果简历没有明确覆盖，使用 `未匹配`，`confidence` 和 `contribution` 设为 0。
6. 相关经验只能给 `相关匹配` 或 `弱匹配`，不要把语义相近但没有直接证据的内容判为强匹配。
7. 不要编造证据；`evidence_indexes` 只能引用输入中存在的 index。
