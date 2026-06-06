# AI 招聘演示系统

本地演示版 AI 招聘筛选系统：上传 JD 和 1-20 份 PDF/DOCX/TXT 简历，生成结构化简历档案、匹配评分、推进建议、面试题、追问问题和 JSON 报告。

演示用的样本简历放在 `samples/resumes/`，可直接通过前端上传体验。

## 功能

- FastAPI 后端，React/Vite 前端。
- PDF/DOCX/TXT 文档解析，JD 与简历文本兜底输入。
- 图片型 PDF 简历在 macOS 本地演示环境会自动使用系统 Vision OCR 兜底解析。
- SQLite 保存运行报告，本地 Chroma/Hashing 向量索引保存证据片段。
- OpenAI-compatible LLM 可选；没有 `LLM_API_KEY` 时自动使用本地规则兜底。
- 外部 LLM 调用前会脱敏候选人姓名、电话、邮箱和微信号。

## 启动

首次安装依赖：

```bash
make install
```

演示启动：

```bash
make demo
```

打开 `http://localhost:5173`。

查看服务状态：

```bash
make status
```

也可以分开启动：

```bash
make backend
make frontend
```

`make dev` 和 `make demo` 都会同时启动前端和后端；`demo` 是给演示场景准备的更直观别名。

## 可选 LLM 配置

复制 `.env.example` 后设置：

```bash
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="..."
export LLM_MODEL="gpt-4o-mini"
```

DeepSeek 等兼容 OpenAI Chat Completions 的网关也可以使用相同变量。

## 验证

```bash
make test
cd frontend && npm run build
```
