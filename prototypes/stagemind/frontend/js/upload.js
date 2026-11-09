/* 上传与处理视图：W9 起实现拖拽上传与任务状态轮询。 */
const UploadView = {
  render(container) {
    container.innerHTML = `
      <section class="card">
        <h2>上传排练录音 / 视频</h2>
        <form id="upload-form">
          <label>剧目 <input name="play" required></label>
          <label>排练次数 <input name="rehearsal_no" type="number" min="1" required></label>
          <label>日期 <input name="date" type="date" required></label>
          <input name="media" type="file" accept="audio/*,video/*" required>
          <button type="submit">上传并处理</button>
        </form>
        <p class="hint">W3-W5 接入 ASR 与 LLM 结构化后，此处会展示自动生成的日志。</p>
      </section>`;

    document.getElementById("upload-form").addEventListener("submit", (event) => {
      event.preventDefault();
      // TODO(W9): 调用 api.uploadRehearsal(new FormData(form)) 并轮询处理状态
    });
  },
};
