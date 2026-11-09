/* 问题看板视图：待解决 / 已解决状态流转。 */
const IssuesView = {
  render(container) {
    container.innerHTML = `
      <section class="card">
        <h2>问题看板</h2>
        <p class="hint">跨排练跟踪问题闭环：待解决 → 已解决。</p>
        <div id="issue-list"></div>
      </section>`;

    api.listIssues().then((issues) => {
      const list = document.getElementById("issue-list");
      if (issues.length === 0) {
        list.innerHTML = "<p class='hint'>暂无问题条目。</p>";
        return;
      }
      list.innerHTML = issues
        .map(
          (issue) =>
            `<p>${issue.status === "open" ? "🔴" : "🟢"} ${issue.description}（${issue.owner}）</p>`
        )
        .join("");
    });
  },
};
