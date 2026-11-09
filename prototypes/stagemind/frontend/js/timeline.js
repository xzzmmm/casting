/* 排练时间轴视图：展示排练列表，支持修改排练日期并自动提醒全体。 */
const TimelineView = {
  render(container) {
    container.innerHTML = `
      <section class="card">
        <h2>排练时间轴</h2>
        <p class="hint">选择一场排练后，这里会按台词时间戳展示结构化日志，支持标签过滤。</p>
        <div id="timeline-list"></div>
      </section>`;

    api.listRehearsals().then((rehearsals) => {
      const list = document.getElementById("timeline-list");
      if (rehearsals.length === 0) {
        list.innerHTML = "<p class='hint'>还没有排练记录，先到「上传处理」上传一场。</p>";
        return;
      }
      // TODO(W9): 渲染每条日志与视频跳转
      list.innerHTML = rehearsals
        .map(
          (item) => `
          <div class="rehearsal-row">
            <span>${item.play} · 第${item.rehearsal_no}次排练（${item.status}）</span>
            ${item.review_pending ? "<span style='color:#e8a33d'>待人工复核</span>" : ""}
            <input type="date" id="date-${item.id}" value="${String(item.date).slice(0, 10)}" />
            <button id="save-${item.id}">保存日期</button>
            <span id="msg-${item.id}" class="hint"></span>
          </div>`
        )
        .join("");

      rehearsals.forEach((item) => {
        document.getElementById(`save-${item.id}`).addEventListener("click", async () => {
          const input = document.getElementById(`date-${item.id}`);
          const msg = document.getElementById(`msg-${item.id}`);
          msg.textContent = "";
          try {
            await api.updateRehearsalDate(item.id, input.value);
            msg.textContent = "已保存，已提醒所有人";
          } catch (error) {
            msg.textContent = `保存失败：${error.message}`;
          }
        });
      });
    });
  },
};
