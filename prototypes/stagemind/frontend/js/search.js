/* 检索视图：关键词搜索日志条目。 */
const SearchView = {
  render(container) {
    container.innerHTML = `
      <section class="card">
        <h2>检索</h2>
        <label>关键词
          <input id="search-input" placeholder="例如：走位、灯光、道具">
        </label>
        <button id="search-btn" type="button">搜索</button>
        <div id="search-result"></div>
      </section>`;

    const runSearch = () => {
      const query = document.getElementById("search-input").value.trim();
      const result = document.getElementById("search-result");
      if (!query) return;
      api.search(query).then((items) => {
        result.innerHTML =
          items.length === 0
            ? "<p class='hint'>没有匹配条目。</p>"
            : items
                .map((item) => `<p>[${item.item_type}] ${item.summary}（${item.status}）</p>`)
                .join("");
      });
    };

    document.getElementById("search-btn").addEventListener("click", runSearch);
  },
};
