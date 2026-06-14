import { render, screen, waitFor, within } from "@testing-library/react";
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
          scoring_criteria: "评分标准"
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
          scoring_criteria: "评分标准"
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

const startedInterviewSession = {
  session_id: "interview-1",
  run_id: "run-1",
  candidate_id: "candidate-1",
  mode: "structured",
  status: "active",
  created_at: "2026-06-03T10:10:00Z",
  updated_at: "2026-06-03T10:10:00Z",
  current_question: {
    question: "面试问题 1",
    focus: "考察点",
    scoring_criteria: "评分标准",
    source: "planned",
    question_index: 0
  },
  turns: [],
  final_report: null
};

const interviewSessionAfterTurn = {
  ...startedInterviewSession,
  updated_at: "2026-06-03T10:12:00Z",
  current_question: {
    question: "你刚才提到效果还可以，能具体说明你个人负责的环节和用什么指标验证效果吗？",
    focus: "动态追问",
    scoring_criteria: "候选人能否补充个人贡献和量化指标。",
    source: "dynamic_followup",
    question_index: 0
  },
  turns: [
    {
      turn_index: 1,
      question: startedInterviewSession.current_question,
      answer: "我做过 RAG 系统，主要用了 FastAPI，效果还可以。",
      created_at: "2026-06-03T10:12:00Z",
      diagnosis: {
        question_index: 0,
        original_question: "面试问题 1",
        candidate_answer: "我做过 RAG 系统，主要用了 FastAPI，效果还可以。",
        answer_summary: "候选人提到做过 RAG 系统，但没有展开个人职责和指标。",
        clarity_score: 42,
        depth_score: 36,
        evidence_consistency: "weak",
        issues: ["缺少个人职责", "缺少量化结果"],
        followup_needed: true,
        followup_question: "你刚才提到效果还可以，能具体说明你个人负责的环节和用什么指标验证效果吗？",
        reason: "回答缺少可验证结果。",
        expected_signal: "候选人能否补充个人贡献和量化指标。",
        source: "llm"
      }
    }
  ],
  final_report: null
};

const completedInterviewSession = {
  ...interviewSessionAfterTurn,
  status: "completed",
  updated_at: "2026-06-03T10:14:00Z",
  current_question: null,
  final_report: {
    overall_score: 53,
    clarity_score: 42,
    depth_score: 36,
    evidence_consistency: "weak",
    recommendation: "谨慎推进，补充验证关键缺口",
    strengths: ["已形成初步面试记录，可作为后续追问依据。"],
    risks: ["缺少个人职责", "缺少量化结果"],
    summary: "本次面试完成 1 轮问答。候选人平均表达清晰度 42 分，回答深度 36 分，证据一致性为 weak。",
    next_steps: ["继续要求候选人给出指标口径、基线、提升幅度和验证方式。"]
  }
};

const defaultModelProviders = {
  default_provider_id: "openai-compatible",
  providers: [
    {
      id: "dashscope",
      name: "通义千问（DashScope）",
      model: "qwen3.5-flash",
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      api_key_configured: false,
      is_default: false
    },
    {
      id: "deepseek",
      name: "DeepSeek",
      model: "deepseek-v4-flash",
      base_url: "https://api.deepseek.com/v1",
      api_key_configured: false,
      is_default: false
    },
    {
      id: "kimi",
      name: "Kimi",
      model: "kimi-latest",
      base_url: "https://api.moonshot.cn/v1",
      api_key_configured: false,
      is_default: false
    },
    {
      id: "glm",
      name: "智谱 GLM",
      model: "glm-5",
      base_url: "https://open.bigmodel.cn/api/coding/paas/v4",
      api_key_configured: false,
      is_default: false
    },
    {
      id: "openai-compatible",
      name: "OpenAI Compatible",
      model: "gpt-4o-mini",
      base_url: "https://api.openai.com/v1",
      api_key_configured: false,
      is_default: true
    }
  ]
};

const dashscopeModelProviders = {
  ...defaultModelProviders,
  default_provider_id: "dashscope",
  providers: defaultModelProviders.providers.map((provider) => ({
    ...provider,
    is_default: provider.id === "dashscope"
  }))
};

const deepseekSavedKeyProviders = {
  ...defaultModelProviders,
  providers: defaultModelProviders.providers.map((provider) => ({
    ...provider,
    api_key_configured: provider.id === "deepseek" ? true : provider.api_key_configured,
    api_key_source: provider.id === "deepseek" ? "saved" : "none"
  }))
};

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/runs") && method === "GET") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/runs") && method === "POST") {
        return new Response(JSON.stringify(demoReport), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/interviews") && method === "GET") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/settings/model-providers") && method === "GET") {
        return new Response(JSON.stringify(defaultModelProviders), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/settings/model-providers/default") && method === "PUT") {
        return new Response(JSON.stringify(dashscopeModelProviders), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/runs/run-1/interviews")) {
        return new Response(JSON.stringify(startedInterviewSession), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/interviews/interview-1/turns")) {
        return new Response(JSON.stringify(interviewSessionAfterTurn), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/interviews/interview-1/final-report")) {
        return new Response(JSON.stringify(completedInterviewSession), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/runs/run-1/answer-followup")) {
        return new Response(JSON.stringify({
          question_index: 0,
          original_question: "面试问题 1",
          candidate_answer: "我做过 RAG 系统，主要用了 FastAPI，效果还可以。",
          answer_summary: "候选人提到做过 RAG 系统，但没有展开个人职责和指标。",
          clarity_score: 42,
          depth_score: 36,
          evidence_consistency: "weak",
          issues: ["缺少个人职责", "缺少量化结果"],
          followup_needed: true,
          followup_question: "你刚才提到效果还可以，能具体说明你个人负责的环节和用什么指标验证效果吗？",
          reason: "回答缺少可验证结果。",
          expected_signal: "候选人能否补充个人贡献和量化指标。",
          source: "llm"
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/interviews/interview-1") && method === "DELETE") {
        return new Response(null, { status: 204 });
      }
      return new Response(JSON.stringify(demoReport), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }) as typeof fetch;
  });

  test("uses AI Native recruiting assistant branding in the sidebar", async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText("AI Native 招聘助手")).toBeInTheDocument());
    expect(screen.getByText("ai-native-recruiting-assistant")).toBeInTheDocument();
    expect(screen.queryByText("Powered by AI")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Interview")).not.toBeInTheDocument();
    expect(screen.queryByText("智能面试助手")).not.toBeInTheDocument();
    expect(screen.queryByText("智能招聘助手")).not.toBeInTheDocument();
  });

  test("uses an interview-guide style sidebar without knowledge base or schedule modules", async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByRole("button", { name: /简历管理/ })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /模拟面试/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /面试记录/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /设置/ })).toBeInTheDocument();
    expect(screen.queryByText("知识库")).not.toBeInTheDocument();
    expect(screen.queryByText("面试日程")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "简历管理" })).toBeInTheDocument();
    expect(screen.getByText("按岗位 JD 分组管理简历与分析结果")).toBeInTheDocument();
  });

  test("loads persisted resume groups and interview records from the backend", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/runs") && method === "GET") {
        return new Response(JSON.stringify([demoReport]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/interviews") && method === "GET") {
        return new Response(JSON.stringify([completedInterviewSession]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/settings/model-providers") && method === "GET") {
        return new Response(JSON.stringify(defaultModelProviders), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(JSON.stringify({ detail: "unexpected request" }), { status: 500 });
    }) as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => expect(screen.getAllByText("高级 Python 后端工程师").length).toBeGreaterThan(0));
    expect(screen.getAllByText("王五").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "面试记录 管理面试历史" }));
    expect(screen.getAllByText("总分 53").length).toBeGreaterThan(0);
    expect(screen.getAllByText("谨慎推进，补充验证关键缺口").length).toBeGreaterThan(0);
  });

  test("switches the default model provider through the backend settings API", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/runs") && method === "GET") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/interviews") && method === "GET") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/settings/model-providers") && method === "GET") {
        return new Response(JSON.stringify(defaultModelProviders), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/settings/model-providers/default") && method === "PUT") {
        return new Response(JSON.stringify(dashscopeModelProviders), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(JSON.stringify({ detail: "unexpected request" }), { status: 500 });
    });
    global.fetch = fetchMock as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "设置 管理模型服务" }));
    expect(await screen.findByText("OpenAI Compatible")).toBeInTheDocument();
    expect(screen.getByText("通义千问（DashScope）")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    expect(screen.queryByText("本地模型服务")).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "设为默认" })[0]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/settings/model-providers/default",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ provider_id: "dashscope" })
        })
      );
    });
    expect(screen.getAllByRole("button", { name: "当前默认" }).length).toBe(1);
  });

  test("saves a pasted provider API key from the settings page", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/runs") && method === "GET") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/interviews") && method === "GET") {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/settings/model-providers") && method === "GET") {
        return new Response(JSON.stringify(defaultModelProviders), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/settings/model-providers/deepseek/api-key") && method === "PUT") {
        return new Response(JSON.stringify(deepseekSavedKeyProviders), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(JSON.stringify({ detail: "unexpected request" }), { status: 500 });
    });
    global.fetch = fetchMock as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "设置 管理模型服务" }));
    const deepseekHeading = await screen.findByRole("heading", { name: "DeepSeek" });
    const deepseekCard = deepseekHeading.closest("article");
    expect(deepseekCard).not.toBeNull();

    await user.click(within(deepseekCard as HTMLElement).getByRole("button", { name: "粘贴 API Key" }));
    await user.type(within(deepseekCard as HTMLElement).getByLabelText("DeepSeek API Key"), "sk-direct-deepseek");
    await user.click(within(deepseekCard as HTMLElement).getByRole("button", { name: "保存 Key" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/settings/model-providers/deepseek/api-key",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ api_key: "sk-direct-deepseek" })
        })
      );
    });
    expect(await within(deepseekCard as HTMLElement).findByText("已保存到本地配置")).toBeInTheDocument();
  });

  test("renders the upload workspace instead of a landing page", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByRole("heading", { name: "简历管理" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /开始智能筛选/ })).toBeInTheDocument();
    expect(screen.getByText("上传 JD 与简历后，这里会按岗位展示候选人、分析状态和 AI 评分。")).toBeInTheDocument();
    expect(screen.queryByText(/后续面试入口/)).not.toBeInTheDocument();

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
    expect(screen.getAllByText("高级 Python 后端工程师").length).toBeGreaterThan(0);
    expect(screen.queryByText("未命名岗位")).not.toBeInTheDocument();
    expect(screen.getAllByText("88").length).toBeGreaterThan(0);
    expect(screen.getAllByText("42").length).toBeGreaterThan(0);
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
    expect(screen.getByRole("button", { name: "模拟面试 配置面试练习" })).toBeInTheDocument();

    expect(screen.getByText("候选人总览")).toBeInTheDocument();
    expect(screen.queryByText("评分拆解")).not.toBeInTheDocument();
    expect(screen.queryByText("抽取过程")).not.toBeInTheDocument();
    expect(screen.queryByText("面试问题 1")).not.toBeInTheDocument();
    expect(screen.queryByText("请补充项目指标。")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "结构化提取" }));
    expect(screen.getByText("抽取过程")).toBeInTheDocument();
    expect(screen.getByText("JD 核心要求")).toBeInTheDocument();
    expect(screen.getByText("简历中的重点")).toBeInTheDocument();
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
    expect(screen.getAllByText("评分标准").length).toBeGreaterThan(0);
    expect(screen.queryByText("中级")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "模拟面试 配置面试练习" }));
    expect(screen.getByText("面试官风格")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /亲切的 HR/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /严厉的面试主管/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始 AI 面试" })).toBeInTheDocument();
    expect(screen.queryByText("追问来源证据 1")).not.toBeInTheDocument();
  });

  test("shows skipped question generation state when backend returns no interview questions", async () => {
    const lowScoreReport = JSON.parse(JSON.stringify(demoReport));
    lowScoreReport.candidates[0].match_report.total_score = 39;
    lowScoreReport.candidates[0].match_report.interview_questions = [];
    lowScoreReport.candidates[0].match_report.followup_questions = [];
    global.fetch = vi.fn(async () => {
      return new Response(JSON.stringify(lowScoreReport), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }) as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.selectOptions(screen.getByLabelText("候选人简历"), "text");
    await user.type(screen.getByLabelText("JD 文本兜底"), "高级 Python 后端工程师，5年以上经验。");
    await user.type(screen.getByLabelText("简历文本兜底"), "王五，客服经验。");
    await user.click(screen.getByRole("button", { name: /开始智能筛选/ }));
    await screen.findByText("候选人总览");

    await user.click(screen.getByRole("button", { name: "试题生成" }));
    expect(screen.getByText("当前候选人未生成面试题，已跳过面试题展示。")).toBeInTheDocument();
    expect(screen.queryByText("面试问题 1")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "模拟面试 配置面试练习" }));
    expect(screen.getByText("当前候选人未生成面试题，建议先完成岗位匹配审核后再开始 AI 面试。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "开始 AI 面试" })).not.toBeInTheDocument();
  });

  test("keeps resume extraction highlights coherent and hides low-value facts", async () => {
    const fragmentedReport = JSON.parse(JSON.stringify(demoReport));
    fragmentedReport.candidates[0].match_report.match_reasons = [
      "AI工具应用能力：熟练运用 ChatGPT、Midjourney 与 Runway。",
      "项目经验匹配：有校园营销案例。"
    ];
    fragmentedReport.candidates[0].extraction_facts = [
      {
        fact_type: "responsibility",
        value: "负责「定制&找工厂」账号矩阵操盘，独立闭环完成从选题、脚本到分发的全流程，累计产出",
        evidence: "负责「定制&找工厂」账号矩阵操盘，独立闭环完成从选题、脚本到分发的全流程，累计产出",
        section: "experience",
        line_start: 10,
        line_end: 10,
        confidence: 0.84,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "爆款短视频15条",
        evidence: "爆款短视频15条",
        section: "experience",
        line_start: 11,
        line_end: 11,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "运用 AIGC 工作流（Midjourney + Runway）辅助视觉生产，将单条视频制作周期从3天缩短",
        evidence: "运用 AIGC 工作流（Midjourney + Runway）辅助视觉生产，将单条视频制作周期从3天缩短",
        section: "experience",
        line_start: 12,
        line_end: 12,
        confidence: 0.84,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "至4小时",
        evidence: "至4小时",
        section: "experience",
        line_start: 13,
        line_end: 13,
        confidence: 0.8,
        extractor: "llm_resume"
      },
      {
        fact_type: "metric",
        value: "40+",
        evidence: "比基础模型，视觉任务准确率最高提升百分之 40+",
        section: "experience",
        line_start: 14,
        line_end: 14,
        confidence: 0.88,
        extractor: "section_rules"
      },
      {
        fact_type: "highlight",
        value: "在深信服实习中，VLM 视觉任务准确率最高提升41.3%",
        evidence: "对比基础模型在三个视觉任务上提取准确率上升 13.45%、29.96%、41.3%",
        section: "experience",
        line_start: 15,
        line_end: 15,
        confidence: 0.9,
        extractor: "llm_resume"
      },
      {
        fact_type: "metric",
        value: "13.45%",
        evidence: "对比基础模型在三个视觉任务上提取准确率上升 13.45%、29.96%、41.3%",
        section: "experience",
        line_start: 15,
        line_end: 15,
        confidence: 0.88,
        extractor: "section_rules"
      },
      {
        fact_type: "project",
        value: "XX 品牌 AIGC 营销实战（校园创业）",
        evidence: "XX 品牌 AIGC 营销实战（校园创业）",
        section: "projects",
        line_start: 20,
        line_end: 20,
        confidence: 0.84,
        extractor: "llm_resume"
      },
      {
        fact_type: "project",
        value: "带领5人团队为校园咖啡店策划 AIGC 营销活动，利用 Midjourney 生成系列海报，节省设计",
        evidence: "带领5人团队为校园咖啡店策划 AIGC 营销活动，利用 Midjourney 生成系列海报，节省设计",
        section: "projects",
        line_start: 21,
        line_end: 21,
        confidence: 0.86,
        extractor: "llm_resume"
      },
      {
        fact_type: "metric",
        value: "5人",
        evidence: "带领5人团队为校园咖啡店策划 AIGC 营销活动",
        section: "projects",
        line_start: 21,
        line_end: 21,
        confidence: 0.86,
        extractor: "section_rules"
      },
      {
        fact_type: "project",
        value: "成本2000元",
        evidence: "成本2000元",
        section: "projects",
        line_start: 22,
        line_end: 22,
        confidence: 0.84,
        extractor: "llm_resume"
      },
      {
        fact_type: "skill",
        value: "熟练掌握小红书/抖音/TikTok平台运营；精通AIGC工作流（ChatGPT/Midjourney/Runway）；熟悉Python、Photoshop、剪映等工具",
        evidence: "熟练掌握小红书/抖音/TikTok平台运营；精通AIGC工作流（ChatGPT/Midjourney/Runway）；熟悉Python、Photoshop、剪映等工具",
        section: "skills",
        line_start: 30,
        line_end: 30,
        confidence: 0.86,
        extractor: "llm_resume"
      },
      {
        fact_type: "skill",
        value: "精通 AIGC 工作流",
        evidence: "精通 AIGC 工作流",
        section: "skills",
        line_start: 31,
        line_end: 31,
        confidence: 0.84,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "（ChatGPT/Midjourney/Runway）",
        evidence: "（ChatGPT/Midjourney/Runway）",
        section: "skills",
        line_start: 32,
        line_end: 32,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "熟悉",
        evidence: "熟悉",
        section: "skills",
        line_start: 33,
        line_end: 33,
        confidence: 0.72,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "• 跨境平台：精通 TikTok Shop",
        evidence: "• 跨境平台：精通 TikTok Shop",
        section: "skills",
        line_start: 34,
        line_end: 34,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "Amazon",
        evidence: "Amazon",
        section: "skills",
        line_start: 35,
        line_end: 35,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "Shopify 独立站运营逻辑与后台操作。",
        evidence: "Shopify 独立站运营逻辑与后台操作。",
        section: "skills",
        line_start: 36,
        line_end: 36,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "• AI 营销：熟练掌握 Midjourney V6",
        evidence: "• AI 营销：熟练掌握 Midjourney V6",
        section: "skills",
        line_start: 37,
        line_end: 37,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "Runway Gen-3",
        evidence: "Runway Gen-3",
        section: "skills",
        line_start: 38,
        line_end: 38,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "HeyGen 等 AIGC 工具进行视",
        evidence: "HeyGen 等 AIGC 工具进行视",
        section: "skills",
        line_start: 39,
        line_end: 39,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "频/图片规模化生产 [4]。",
        evidence: "频/图片规模化生产 [4]。",
        section: "skills",
        line_start: 40,
        line_end: 40,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "skill",
        value: "• 数据分析：熟练使用 Python（Pandas）",
        evidence: "• 数据分析：熟练使用 Python（Pandas）",
        section: "skills",
        line_start: 41,
        line_end: 41,
        confidence: 0.82,
        extractor: "section_rules"
      },
      {
        fact_type: "summary",
        value: "具备极强的 AI 赋能意识，善于利用新技术解决业务痛点；拥有出色的逻辑",
        evidence: "具备极强的 AI 赋能意识，善于利用新技术解决业务痛点；拥有出色的逻辑",
        section: "summary",
        line_start: 40,
        line_end: 40,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "summary",
        value: "具备极强的 AI 赋能意识，善于利用新技术解决业务痛点",
        evidence: "具备极强的 AI 赋能意识，善于利用新技术解决业务痛点",
        section: "summary",
        line_start: 40,
        line_end: 40,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "summary",
        value: "思维与快速学习能力",
        evidence: "思维与快速学习能力",
        section: "summary",
        line_start: 41,
        line_end: 41,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "summary",
        value: "拥有出色的逻辑思维与快速学习能力",
        evidence: "拥有出色的逻辑思维与快速学习能力",
        section: "summary",
        line_start: 41,
        line_end: 41,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "domain_evidence",
        value: "AI",
        evidence: "AI",
        section: "summary",
        line_start: 40,
        line_end: 40,
        confidence: 0.72,
        extractor: "section_rules"
      }
    ];
    global.fetch = vi.fn(async () => {
      return new Response(JSON.stringify(fragmentedReport), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }) as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.selectOptions(screen.getByLabelText("候选人简历"), "text");
    await user.type(screen.getByLabelText("JD 文本兜底"), "AIGC 内容运营");
    await user.type(screen.getByLabelText("简历文本兜底"), "小李，AIGC 校园营销经验。");
    await user.click(screen.getByRole("button", { name: /开始智能筛选/ }));
    await screen.findByText("候选人总览");
    await user.click(screen.getByRole("button", { name: "结构化提取" }));

    expect(screen.getByText("简历中的重点")).toBeInTheDocument();
    expect(screen.queryByText("简历抽取事实")).not.toBeInTheDocument();
    expect(screen.queryByText(/AI工具应用能力/)).not.toBeInTheDocument();
    expect(screen.queryByText("领域证据")).not.toBeInTheDocument();
    expect(screen.queryByText("AI")).not.toBeInTheDocument();
    expect(screen.getByText("负责「定制&找工厂」账号矩阵操盘，独立闭环完成从选题、脚本到分发的全流程，累计产出爆款短视频15条")).toBeInTheDocument();
    expect(screen.queryByText("爆款短视频15条")).not.toBeInTheDocument();
    expect(screen.getByText("运用 AIGC 工作流（Midjourney + Runway）辅助视觉生产，将单条视频制作周期从3天缩短至4小时")).toBeInTheDocument();
    expect(screen.queryByText("至4小时")).not.toBeInTheDocument();
    expect(screen.getByText("在深信服实习中，VLM 视觉任务准确率最高提升41.3%")).toBeInTheDocument();
    expect(screen.queryByText("40+")).not.toBeInTheDocument();
    expect(screen.queryByText("13.45%")).not.toBeInTheDocument();
    expect(screen.getByText("XX 品牌 AIGC 营销实战（校园创业）：带领5人团队为校园咖啡店策划 AIGC 营销活动，利用 Midjourney 生成系列海报，节省设计成本2000元")).toBeInTheDocument();
    expect(screen.queryByText(/节省设计5人成本/)).not.toBeInTheDocument();
    expect(screen.queryByText("成本2000元")).not.toBeInTheDocument();
    expect(screen.getByText("AIGC 工作流（ChatGPT/Midjourney/Runway）")).toHaveClass("skill-chip");
    expect(screen.queryByText("（ChatGPT/Midjourney/Runway）")).not.toBeInTheDocument();
    expect(screen.queryByText("熟悉")).not.toBeInTheDocument();
    expect(screen.getByText("跨境平台：TikTok Shop / Amazon / Shopify 独立站运营逻辑与后台操作")).toHaveClass("skill-chip");
    expect(screen.getByText("AI 营销：Midjourney V6 / Runway Gen-3 / HeyGen 等 AIGC 工具进行视频/图片规模化生产")).toHaveClass("skill-chip");
    expect(screen.getByText("数据分析：Python（Pandas）")).toHaveClass("skill-chip");
    expect(screen.queryByText("Amazon")).not.toBeInTheDocument();
    expect(screen.queryByText("频/图片规模化生产 [4]。")).not.toBeInTheDocument();
    expect(screen.getByText("具备极强的 AI 赋能意识，善于利用新技术解决业务痛点")).toBeInTheDocument();
    expect(screen.getByText("拥有出色的逻辑思维与快速学习能力")).toBeInTheDocument();
    expect(screen.queryByText("思维与快速学习能力")).not.toBeInTheDocument();
  });

  test("supplements isolated project highlights with a profile project summary", async () => {
    const reportWithIsolatedProjectHighlight = JSON.parse(JSON.stringify(demoReport));
    reportWithIsolatedProjectHighlight.candidates[0].profile.projects = [
      "工业设备智能问答与辅助诊断平台：面向工业设备巡检、报警解释、故障排查和检维修知识问答，将自然语言问题转化为可追溯的工业运维辅助诊断流程。"
    ];
    reportWithIsolatedProjectHighlight.candidates[0].extraction_facts = [
      {
        fact_type: "education_summary",
        value: "2024.09 - 至今 浙江大学 控制科学与工程 - 硕士",
        evidence: "2024.09 - 至今 浙江大学 控制科学与工程 - 硕士",
        section: "education",
        line_start: 6,
        line_end: 6,
        confidence: 0.88,
        extractor: "llm_resume"
      },
      {
        fact_type: "highlight",
        value: "已授权专利一项（大模型辅助的多模态工业设备知识图谱构建方法）",
        evidence: "已授权专利一项（大模型辅助的多模态工业设备知识图谱构建方法）",
        section: "projects",
        line_start: 45,
        line_end: 45,
        confidence: 0.9,
        extractor: "llm_resume"
      }
    ];

    global.fetch = vi.fn(async () => {
      return new Response(JSON.stringify(reportWithIsolatedProjectHighlight), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }) as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.selectOptions(screen.getByLabelText("候选人简历"), "text");
    await user.type(screen.getByLabelText("JD 文本兜底"), "工业智能运维");
    await user.type(screen.getByLabelText("简历文本兜底"), "工业设备智能问答与辅助诊断平台。");
    await user.click(screen.getByRole("button", { name: /开始智能筛选/ }));
    await screen.findByText("候选人总览");
    await user.click(screen.getByRole("button", { name: "结构化提取" }));

    expect(screen.getByText("工业设备智能问答与辅助诊断平台：面向工业设备巡检、报警解释、故障排查和检维修知识问答，将自然语言问题转化为可追溯的工业运维辅助诊断流程。")).toBeInTheDocument();
    expect(screen.getByText("已授权专利一项（大模型辅助的多模态工业设备知识图谱构建方法）")).toBeInTheDocument();
  });

  test("compacts fragmented work experience facts and hides citation leftovers", async () => {
    const fragmentedReport = JSON.parse(JSON.stringify(demoReport));
    fragmentedReport.candidates[0].extraction_facts = [
      {
        fact_type: "responsibility",
        value: "TikTok Shop 矩阵操盘：负责北美区 TikTok Shop账号从 0到1的搭建，通过AI批",
        evidence: "TikTok Shop 矩阵操盘：负责北美区 TikTok Shop账号从 0到1的搭建，通过AI批",
        section: "experience",
        line_start: 10,
        line_end: 10,
        confidence: 0.84,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "量生成营销素材，累计曝光150万",
        evidence: "量生成营销素材，累计曝光150万",
        section: "experience",
        line_start: 11,
        line_end: 11,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "AI 赋能选品与营销：引入 NLP 与情",
        evidence: "AI 赋能选品与营销：引入 NLP 与情",
        section: "experience",
        line_start: 12,
        line_end: 12,
        confidence: 0.84,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "感分析工具抓取社媒热点，结合",
        evidence: "感分析工具抓取社媒热点，结合",
        section: "experience",
        line_start: 13,
        line_end: 13,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "Midjourney 快速迭3个",
        evidence: "Midjourney 快速迭3个",
        section: "experience",
        line_start: 14,
        line_end: 14,
        confidence: 0.82,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "[4]",
        evidence: "[4]",
        section: "experience",
        line_start: 15,
        line_end: 15,
        confidence: 0.72,
        extractor: "section_rules"
      },
      {
        fact_type: "responsibility",
        value: "自动化客服体系：基于 LLM 搭建多语言智能客服 Agent，处理80%的售前咨询与售",
        evidence: "自动化客服体系：基于 LLM 搭建多语言智能客服 Agent，处理80%的售前咨询与售",
        section: "experience",
        line_start: 16,
        line_end: 16,
        confidence: 0.84,
        extractor: "llm_resume"
      },
      {
        fact_type: "responsibility",
        value: "后FAQ",
        evidence: "后FAQ",
        section: "experience",
        line_start: 17,
        line_end: 17,
        confidence: 0.82,
        extractor: "llm_resume"
      }
    ];
    global.fetch = vi.fn(async () => {
      return new Response(JSON.stringify(fragmentedReport), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }) as typeof fetch;
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.selectOptions(screen.getByLabelText("候选人简历"), "text");
    await user.type(screen.getByLabelText("JD 文本兜底"), "海外内容运营");
    await user.type(screen.getByLabelText("简历文本兜底"), "小李，TikTok Shop 运营经验。");
    await user.click(screen.getByRole("button", { name: /开始智能筛选/ }));
    await screen.findByText("候选人总览");
    await user.click(screen.getByRole("button", { name: "结构化提取" }));

    expect(screen.getByText("TikTok Shop 矩阵操盘：负责北美区 TikTok Shop账号从 0到1的搭建，通过AI批量生成营销素材，累计曝光150万")).toBeInTheDocument();
    expect(screen.getByText("AI 赋能选品与营销：引入 NLP 与情感分析工具抓取社媒热点，结合 Midjourney 快速迭3个")).toBeInTheDocument();
    expect(screen.getByText("自动化客服体系：基于 LLM 搭建多语言智能客服 Agent，处理80%的售前咨询与售后FAQ")).toBeInTheDocument();
    expect(screen.queryByText("[4]")).not.toBeInTheDocument();
    expect(screen.queryByText("后FAQ")).not.toBeInTheDocument();
  });

  test("runs an AI interviewer session and produces a final report", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.selectOptions(screen.getByLabelText("职位描述（JD）"), "text");
    await user.selectOptions(screen.getByLabelText("候选人简历"), "text");
    await user.type(screen.getByLabelText("JD 文本兜底"), "高级 Python 后端工程师，5年以上经验。");
    await user.type(screen.getByLabelText("简历文本兜底"), "王五，7年 Python 后端经验。");
    await user.click(screen.getByRole("button", { name: /开始智能筛选/ }));

    await screen.findByText("候选人总览");
    await user.click(screen.getByRole("button", { name: "模拟面试 配置面试练习" }));
    expect(screen.getByText("面试模式")).toBeInTheDocument();
    expect(screen.getByText("面试方向")).toBeInTheDocument();
    expect(screen.getByText("难度")).toBeInTheDocument();
    expect(screen.getByText("面试官风格")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始 AI 面试" }));
    expect(await screen.findByText("面试问题 1")).toBeInTheDocument();

    await user.type(
      screen.getByLabelText("候选人回答"),
      "我做过 RAG 系统，主要用了 FastAPI，效果还可以。"
    );
    await user.click(screen.getByRole("button", { name: "发送回答" }));

    await waitFor(() => expect(screen.getAllByText("面试记录").length).toBeGreaterThan(0));
    expect(screen.getByText("我做过 RAG 系统，主要用了 FastAPI，效果还可以。")).toBeInTheDocument();
    expect(screen.getAllByText("你刚才提到效果还可以，能具体说明你个人负责的环节和用什么指标验证效果吗？").length).toBeGreaterThan(0);
    expect(screen.getByText("缺少个人职责")).toBeInTheDocument();
    expect(screen.getByText("清晰度 42")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "生成最终报告" }));

    expect(await screen.findByText("最终评估报告")).toBeInTheDocument();
    expect(screen.getByText("谨慎推进，补充验证关键缺口")).toBeInTheDocument();
    expect(screen.getByText("总分 53")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "面试记录 管理面试历史" }));
    expect(screen.getAllByText("谨慎推进，补充验证关键缺口").length).toBeGreaterThan(0);
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
