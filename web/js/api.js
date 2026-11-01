const BASE = "/api/v1";

async function parse(responsePromise) {
  let response;
  try {
    response = await responsePromise;
  } catch (cause) {
    const wrapped = new Error("连不上服务：确认后端是否在运行，或检查网络。");
    wrapped.code = "NETWORK";
    throw wrapped;
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`服务返回了非 JSON 内容（HTTP ${response.status}）`);
  }
  if (!payload || payload.ok !== true) {
    const error = payload && payload.error ? payload.error : { code: "UNKNOWN", message: `HTTP ${response.status}` };
    const wrapped = new Error(error.message || error.code);
    wrapped.code = error.code;
    wrapped.details = error;
    throw wrapped;
  }
  return payload.data;
}

async function request(method, path, body) {
  const init = { method, headers: {} };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json; charset=utf-8";
    init.body = JSON.stringify(body);
  }
  return parse(fetch(BASE + path, init));
}

export const api = {
  health: () => request("GET", "/health"),

  /** 图片上传：字段名固定 file，与小程序 wx.uploadFile 保持一致。 */
  fromImage: async (files, targetLevel, title) => {
    const form = new FormData();
    files.forEach((file) => form.append("file", file, file.name || "page.png"));
    form.append("target_level", targetLevel);
    if (title) form.append("title", title);
    return parse(await fetch(`${BASE}/documents/from-image`, { method: "POST", body: form }));
  },

  createDocument: (text, targetLevel, title) =>
    request("POST", "/documents", { text, target_level: targetLevel, title: title || null }),
  analyze: (docId, stages) => request("POST", `/documents/${docId}/analyze`, { stages }),
  document: (docId) => request("GET", `/documents/${docId}`),
  sentences: (docId, page = 1, pageSize = 200) =>
    request("GET", `/documents/${docId}/sentences?page=${page}&page_size=${pageSize}`),
  runs: (docId) => request("GET", `/documents/${docId}/runs`),
};

export const ERROR_TEXT = {
  NO_IMAGE: "请先上传文章图片。",
  IMAGE_UNSUPPORTED: "图片格式不支持，仅接受 PNG / JPG / WEBP。",
  IMAGE_TOO_LARGE: "图片太大，单张请控制在 10MB 以内。",
  IMAGE_COUNT_EXCEEDED: "图片数量超出上限（最多 5 张）。",
  DOC_TOO_LARGE: "识别出的正文太长，超出单篇上限，请拆成多篇。",
  SEGMENT_INCOMPLETE: "分段没有完成。可以稍后重试，或先看结构分析。",
  LLM_BAD_OUTPUT: "没能识别出英文正文，或模型返回内容无法解析。",
  LLM_UNAVAILABLE: "模型服务不可用。检查 API Key、网络或稍后再试。",
  QUOTA_EXCEEDED: "今日分析额度已用完。",
  STAGE_NOT_ALLOWED: "当前文档状态不允许该操作。",
  NOT_FOUND: "找不到该文档。",
  BAD_REQUEST: "请求参数有误。",
  INTERNAL: "服务器内部错误，请查看后端日志。",
};

export function describeError(error) {
  const known = ERROR_TEXT[error.code];
  const extra = error.details && error.details.notes ? ` ${error.details.notes}` : "";
  if (known) return `${known}（${error.code}）${extra}`;
  return (error.message || "未知错误") + extra;
}
