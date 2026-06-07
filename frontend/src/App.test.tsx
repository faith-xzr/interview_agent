import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const demoReport = {
  run_id: "run-1",
  created_at: "2026-06-03T10:00:00Z",
  jd_profile: {
    job_title: "高级 Python 后端工程师",
    responsibilities: ["负责 RAG 平台建设"],
    required_skills: ["Python", "FastAPI", "SQL"],
    nice_to_have_skills: ["React"],
    seniority: "高级",
    years_required: 5,
    industry_background: ["AI"],
    hard_requirements: []
  },
  warnings: [],
  jd_extraction_facts: [
    {
      fact_type: "required_skill",
      value: "Python",
      evidence: "高级 Python 后端工程师，5年以上经验，负责 FastAPI、RAG、SQL、React 平台建设。",
      section: "jd",
      line_start: 1,
      line_end: 1,
      confidence: 0.9,
      extractor: "jd_profile_projection"
    },
    {
      fact_type: "responsibility",
      value: "负责 RAG 平台建设",
      evidence: "负责 RAG 平台建设",
      section: "jd",
      line_start: 2,
      line_end: 2,
      confidence: 0.86,
      extractor: "jd_profile_projection"
    }
  ],
  candidates: [
    {
      candidate_id: "candidate-1",
      source_name: "resume-1.txt",
      profile: {
        name: "王五",
        contacts: { phone: "13812345678" },
        education: ["某理工大学计算机科学与技术本科。"],
        work_experiences: ["头部互联网平台后端开发实习生：负责 RAG 检索平台后端接口、SQL 查询和跨端联调。"],
        projects: ["RAG 检索平台"],
        skills: ["Python", "FastAPI", "SQL"],
        certifications: [],
        highlights: ["主导 RAG 平台"],
        risk_points: [],
        ambiguous_points: ["项目指标未说明"]
      },
      parse_warnings: [],
      extraction_facts: [
        {
          fact_type: "target_role",
          value: "全栈开发工程师",
          evidence: "求职意向：全栈开发工程师",
          section: "basic",
          line_start: 2,
          line_end: 2,
          confidence: 0.92,
          extractor: "llm_resume"
        },
        {
          fact_type: "education_summary",
          value: "某理工大学计算机科学与技术本科。",
          evidence: "某理工大学 计算机科学与技术 本科",
          section: "education",
          line_start: 5,
          line_end: 5,
          confidence: 0.82,
          extractor: "llm_resume"
        },
        {
          fact_type: "work_summary",
          value: "头部互联网平台后端开发实习生：负责 RAG 检索平台后端接口、SQL 查询和跨端联调。",
          evidence: "头部互联网平台｜后端开发实习生；负责 RAG 检索平台后端接口、SQL 查询和跨端联调。",
          section: "experience",
          line_start: 8,
          line_end: 9,
          confidence: 0.9,
          extractor: "llm_resume"
        },
        {
          fact_type: "skill",
          value: "Python",
          evidence: "专业技能：Python | FastAPI | SQL",
          section: "skills",
          line_start: 12,
          line_end: 12,
          confidence: 0.9,
          extractor: "section_rules"
        },
        {
          fact_type: "skill",
          value: "FastAPI",
          evidence: "专业技能：Python | FastAPI | SQL",
          section: "skills",
          line_start: 12,
          line_end: 12,
          confidence: 0.9,
          extractor: "section_rules"
        },
        {
          fact_type: "skill",
          value: "SQL",
          evidence: "专业技能：Python | FastAPI | SQL",
          section: "skills",
          line_start: 12,
          line_end: 12,
          confidence: 0.9,
          extractor: "section_rules"
        },
        {
          fact_type: "project",
          value: "RAG 检索平台",
          evidence: "项目：RAG 检索平台，使用 FastAPI、SQL 和 React",
          section: "projects",
          line_start: 8,
          line_end: 8,
          confidence: 0.84,
          extractor: "section_rules"
        }
      ],
      match_report: {
        total_score: 88,
        decision: "推荐推进",
        dimension_scores: {
          "核心技能与工具": 27,
          "岗位职责匹配": 18,
          "年限与级别": 13,
          "项目证据深度": 16,
          "行业/业务背景": 8,
          "教育/证书/硬条件": 6,
          "风险扣分": -3
        },
        score_breakdown: {
          skill_score: 27,
          experience_score: 13,
          project_score: 34,
          industry_score: 8,
          education_score: 6,
          risk_deduction: 3
        },
        match_reasons: ["核心技能匹配：Python, FastAPI, SQL"],
        gap_reasons: ["建议验证项目指标"],
        evidence_snippets: [{ source: "片段 1", text: "RAG 检索平台 FastAPI SQL" }],
        dimension_explanations: [
          {
            dimension: "核心技能与工具",
            score: 27,
            max_score: 30,
            summary: "3/3 项有明确证据"
          },
          {
            dimension: "岗位职责匹配",
            score: 18,
            max_score: 20,
            summary: "1/1 项有明确证据"
          }
        ],
        requirement_matches: [
          {
            dimension: "核心技能与工具",
            requirement: "Python",
            requirement_type: "required_skill",
            status: "强匹配",
            max_score: 8,
            contribution: 7.4,
            confidence: 0.92,
            reason: "在项目或经历中找到直接证据",
            evidence: [
              {
                source: "项目证据",
                text: "RAG 检索平台 FastAPI SQL",
                section: "projects",
                line_start: 8,
                line_end: 8,
                fact_type: "project"
              }
            ]
          }
        ],
        interview_questions: Array.from({ length: 10 }, (_, index) => ({
          question: `面试问题 ${index + 1}`,
          focus: "考察点",
          difficulty: "中级",
          scoring_criteria: "评分标准",
          evidence: "面试题来源证据"
        })),
        followup_questions: [
          { question: "请补充项目指标。", reason: "模糊点", related_evidence: "追问来源证据 1" },
          { question: "请说明个人贡献。", reason: "模糊点", related_evidence: "追问来源证据 2" },
          { question: "请说明团队规模。", reason: "模糊点", related_evidence: "追问来源证据 3" }
        ]
      }
    },
    {
      candidate_id: "candidate-2",
      source_name: "resume-2.txt",
      profile: {
        name: "赵六",
        contacts: {},
        education: [],
        work_experiences: ["2年客服经验"],
        projects: ["客户满意度运营项目"],
        skills: ["Excel"],
        certifications: [],
        highlights: [],
        risk_points: [],
        ambiguous_points: []
      },
      parse_warnings: [],
      extraction_facts: [],
      match_report: {
        total_score: 42,
        decision: "暂不推进",
        dimension_scores: {
          "核心技能与工具": 0,
          "岗位职责匹配": 3,
          "年限与级别": 4,
          "项目证据深度": 5,
          "行业/业务背景": 0,
          "教育/证书/硬条件": 0,
          "风险扣分": -9
        },
        score_breakdown: {
          skill_score: 0,
          experience_score: 4,
          project_score: 8,
          industry_score: 0,
          education_score: 0,
          risk_deduction: 9
        },
        match_reasons: ["简历中存在少量可复用经历，但与岗位核心要求关联有限"],
        gap_reasons: ["核心技能与工具待确认：Python（简历未明确覆盖该要求）"],
        evidence_snippets: [{ source: "片段 1", text: "客服 Excel" }],
        dimension_explanations: [],
        requirement_matches: [],
        interview_questions: Array.from({ length: 10 }, (_, index) => ({
          question: `低匹配面试问题 ${index + 1}`,
          focus: "考察点",
          difficulty: "初级",
          scoring_criteria: "评分标准",
          evidence: "低匹配面试题来源证据"
        })),
        followup_questions: [
          { question: "请说明 Python 经验。", reason: "缺口", related_evidence: "低匹配追问来源证据 1" },
          { question: "请补充后端项目。", reason: "缺口", related_evidence: "低匹配追问来源证据 2" },
          { question: "请说明 SQL 使用经历。", reason: "缺口", related_evidence: "低匹配追问来源证据 3" }
        ]
      }
    }
  ]
};

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/runs")) {
        return new Response(JSON.stringify(demoReport), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(JSON.stringify(demoReport), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }) as typeof fetch;
  });

  test("renders the upload workspace instead of a landing page", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole("heading", { name: "智能简历解析与试题生成引擎" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /开始智能筛选/ })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.selectOptions(screen.getByLabelText("候选人简历"), "text");
    expect(screen.getByLabelText("JD 文本兜底")).toBeInTheDocument();
    expect(screen.getByLabelText("简历文本兜底")).toBeInTheDocument();
  });

  test("submits text input and keeps the result overview concise with separate detail views", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.selectOptions(screen.getByLabelText("候选人简历"), "text");
    await user.type(screen.getByLabelText("JD 文本兜底"), "高级 Python 后端工程师，5年以上经验。");
    await user.type(screen.getByLabelText("简历文本兜底"), "王五，7年 Python 后端经验。");
    await user.click(screen.getByRole("button", { name: /开始智能筛选/ }));

    await waitFor(() => expect(screen.getAllByText("王五").length).toBeGreaterThan(0));
    expect(screen.getAllByText("88").length).toBeGreaterThan(0);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.queryByText("必备技能")).not.toBeInTheDocument();
    expect(screen.queryByText("Python · FastAPI · SQL")).not.toBeInTheDocument();
    expect(screen.queryByText("推荐推进")).not.toBeInTheDocument();
    expect(screen.queryByText("暂不推进")).not.toBeInTheDocument();
    expect(screen.queryByText("核心技能匹配：Python, FastAPI, SQL")).not.toBeInTheDocument();
    expect(screen.queryByText("核心技能与工具待确认：Python（简历未明确覆盖该要求）")).not.toBeInTheDocument();
    expect(screen.queryByText("简历中存在少量可复用经历，但与岗位核心要求关联有限")).not.toBeInTheDocument();

    expect(screen.queryByRole("link", { name: "导出 JSON" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "总览" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "结构化提取" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "智能匹配打分" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "试题生成" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "追问模拟" })).toBeInTheDocument();

    expect(screen.getByText("候选人总览")).toBeInTheDocument();
    expect(screen.queryByText("评分拆解")).not.toBeInTheDocument();
    expect(screen.queryByText("抽取过程")).not.toBeInTheDocument();
    expect(screen.queryByText("面试问题 1")).not.toBeInTheDocument();
    expect(screen.queryByText("请补充项目指标。")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "结构化提取" }));
    expect(screen.getByText("抽取过程")).toBeInTheDocument();
    expect(screen.getByText("JD 核心要求")).toBeInTheDocument();
    expect(screen.getByText("简历抽取事实")).toBeInTheDocument();
    expect(screen.getAllByText("必备技能").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "学历背景" })).toBeInTheDocument();
    expect(screen.getByText("某理工大学计算机科学与技术本科。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "实习/工作经验" })).toBeInTheDocument();
    expect(screen.getByText("头部互联网平台后端开发实习生：负责 RAG 检索平台后端接口、SQL 查询和跨端联调。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目经验" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "专业技能" })).toBeInTheDocument();
    expect(screen.getByText("FastAPI")).toHaveClass("skill-chip");
    expect(screen.getByText("SQL")).toHaveClass("skill-chip");
    expect(screen.queryByRole("heading", { name: "基本信息" })).not.toBeInTheDocument();
    expect(screen.queryByText("target_role")).not.toBeInTheDocument();
    expect(screen.queryByText("required_skill")).not.toBeInTheDocument();
    expect(screen.queryByText("skill")).not.toBeInTheDocument();
    expect(screen.queryByText("90%")).not.toBeInTheDocument();
    expect(screen.queryByText("专业技能：Python | FastAPI | SQL")).not.toBeInTheDocument();
    expect(screen.queryByText("项目：RAG 检索平台，使用 FastAPI、SQL 和 React")).not.toBeInTheDocument();
    expect(screen.queryByText("projects · 第 8 行 · section_rules")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "智能匹配打分" }));
    expect(screen.getByText("评分拆解")).toBeInTheDocument();
    expect(screen.getAllByText("Python").length).toBeGreaterThan(0);
    expect(screen.getByText("强匹配")).toBeInTheDocument();
    expect(screen.getByText("贡献 7.4/8")).toBeInTheDocument();
    expect(screen.queryByText("项目证据 · 第 8 行")).not.toBeInTheDocument();
    expect(screen.queryByText("RAG 检索平台 FastAPI SQL")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "试题生成" }));
    expect(screen.getByText("面试问题 1")).toBeInTheDocument();
    expect(screen.queryByText("面试题来源证据")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "追问模拟" }));
    expect(screen.getByText("请补充项目指标。")).toBeInTheDocument();
    expect(screen.queryByText("追问来源证据 1")).not.toBeInTheDocument();
  });

  test("shows API errors in the workspace", async () => {
    global.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ detail: "至少需要一份有效简历内容。" }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }) as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.type(screen.getByLabelText("JD 文本兜底"), "Python 工程师");
    await user.click(screen.getByRole("button", { name: /开始智能筛选/ }));

    expect(await screen.findByText("至少需要一份有效简历内容。")).toBeInTheDocument();
  });
});
