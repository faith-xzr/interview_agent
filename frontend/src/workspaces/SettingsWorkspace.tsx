import { AlertCircle, Cpu, KeyRound, Settings } from "lucide-react";
import { useEffect, useState } from "react";

import {
  getModelProviders,
  updateDefaultModelProvider,
  updateModelProviderApiKey
} from "../api";
import { PageTitle } from "../components/PageTitle";
import type { ModelProvider } from "../types";

const FALLBACK_MODEL_PROVIDERS: ModelProvider[] = [
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
];

export function SettingsWorkspace() {
  const [providers, setProviders] = useState<ModelProvider[]>(FALLBACK_MODEL_PROVIDERS);
  const [defaultProvider, setDefaultProvider] = useState("openai-compatible");
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [editingApiKeyProvider, setEditingApiKeyProvider] = useState<string | null>(null);
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [savingApiKeyProvider, setSavingApiKeyProvider] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadProviders() {
      setLoading(true);
      setError(null);
      try {
        const payload = await getModelProviders();
        if (cancelled) return;
        setProviders(payload.providers);
        setDefaultProvider(payload.default_provider_id);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "模型服务配置加载失败。");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    loadProviders();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSetDefault(providerId: string) {
    if (providerId === defaultProvider || savingProvider) return;
    setSavingProvider(providerId);
    setError(null);
    try {
      const payload = await updateDefaultModelProvider(providerId);
      setProviders(payload.providers);
      setDefaultProvider(payload.default_provider_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "默认模型服务切换失败。");
    } finally {
      setSavingProvider(null);
    }
  }

  function openApiKeyEditor(providerId: string) {
    setEditingApiKeyProvider(providerId);
    setApiKeyDraft("");
    setError(null);
  }

  function closeApiKeyEditor() {
    setEditingApiKeyProvider(null);
    setApiKeyDraft("");
  }

  async function handleSaveApiKey(providerId: string) {
    const apiKey = apiKeyDraft.trim();
    if (!apiKey || savingApiKeyProvider) {
      if (!apiKey) setError("请先粘贴 API Key。");
      return;
    }
    setSavingApiKeyProvider(providerId);
    setError(null);
    try {
      const payload = await updateModelProviderApiKey(providerId, apiKey);
      setProviders(payload.providers);
      setDefaultProvider(payload.default_provider_id);
      closeApiKeyEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : "API Key 保存失败。");
    } finally {
      setSavingApiKeyProvider(null);
    }
  }

  return (
    <div className="workspace-stack">
      <PageTitle icon={Settings} title="设置" subtitle="管理模型服务和默认推理配置" />
      {error ? (
        <div className="error-banner">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}
      <section className="settings-grid">
        {providers.map((provider) => {
          const isEditingApiKey = editingApiKeyProvider === provider.id;
          const isSavingApiKey = savingApiKeyProvider === provider.id;
          const apiKeyInputId = `provider-api-key-${provider.id}`;
          return (
            <article className={defaultProvider === provider.id ? "provider-card card active" : "provider-card card"} key={provider.id}>
              <div className="provider-head">
                <span className="document-icon"><Cpu size={20} aria-hidden="true" /></span>
                <div>
                  <h2>{provider.name}</h2>
                  <p>{defaultProvider === provider.id ? "默认聊天服务" : "备用模型服务"}</p>
                </div>
              </div>
              <label>
                模型名称
                <input value={provider.model} readOnly />
              </label>
              <label>
                Base URL
                <input value={provider.base_url} readOnly />
              </label>
              <div className="provider-field">
                <span className="provider-field-label">API Key</span>
                <span className="secret-input">
                  <KeyRound size={16} aria-hidden="true" />
                  {providerApiKeyLabel(provider)}
                </span>
              </div>
              {isEditingApiKey ? (
                <div className="provider-key-editor">
                  <label htmlFor={apiKeyInputId}>
                    新的 API Key
                    <input
                      aria-label={`${provider.name} API Key`}
                      autoComplete="off"
                      id={apiKeyInputId}
                      onChange={(event) => setApiKeyDraft(event.target.value)}
                      placeholder="粘贴 API Key"
                      type="password"
                      value={apiKeyDraft}
                    />
                  </label>
                  <div className="provider-key-actions">
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={isSavingApiKey}
                      onClick={() => handleSaveApiKey(provider.id)}
                    >
                      <span>{isSavingApiKey ? "保存中..." : "保存 Key"}</span>
                    </button>
                    <button
                      className="secondary-button subtle"
                      type="button"
                      disabled={isSavingApiKey}
                      onClick={closeApiKeyEditor}
                    >
                      <span>取消</span>
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  className="secondary-button subtle"
                  type="button"
                  disabled={loading || savingProvider !== null || savingApiKeyProvider !== null}
                  onClick={() => openApiKeyEditor(provider.id)}
                >
                  <KeyRound size={16} aria-hidden="true" />
                  <span>粘贴 API Key</span>
                </button>
              )}
              <button
                className="secondary-button"
                type="button"
                disabled={loading || savingProvider !== null || savingApiKeyProvider !== null || defaultProvider === provider.id}
                onClick={() => handleSetDefault(provider.id)}
              >
                <span>
                  {savingProvider === provider.id
                    ? "切换中..."
                    : defaultProvider === provider.id
                      ? "当前默认"
                      : "设为默认"}
                </span>
              </button>
            </article>
          );
        })}
      </section>
    </div>
  );
}

function providerApiKeyLabel(provider: ModelProvider) {
  if (provider.api_key_source === "saved") return "已保存到本地配置";
  if (provider.api_key_source === "env") return "已通过环境变量配置";
  if (provider.api_key_configured) return "已配置";
  return "未配置，可粘贴";
}
