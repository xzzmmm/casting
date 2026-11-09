/* 后端 API 封装。 */
const API_BASE = "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`请求失败(${response.status})：${detail}`);
  }
  return response.json();
}

const api = {
  uploadRehearsal: (formData) => request("/upload", { method: "POST", body: formData }),
  listRehearsals: () => request("/rehearsals"),
  getRehearsal: (id) => request(`/rehearsals/${id}`),
  updateRehearsalDate: (id, date) =>
    request(`/rehearsals/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    }),
  listLogs: (id) => request(`/rehearsals/${id}/logs`),
  listBlocking: (id) => request(`/rehearsals/${id}/blocking`),
  listIssues: (status = "") => request(`/issues${status ? `?status=${status}` : ""}`),
  search: (query) => request(`/search?q=${encodeURIComponent(query)}`),
};
