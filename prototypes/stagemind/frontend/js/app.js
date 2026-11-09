/* 视图切换：每个视图模块暴露 render(container)。 */
const views = {
  upload: UploadView,
  timeline: TimelineView,
  blocking: BlockingView,
  issues: IssuesView,
  search: SearchView,
};

function switchView(name) {
  document.querySelectorAll(".nav-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  const container = document.getElementById("view");
  container.innerHTML = "";
  views[name].render(container);
}

document.querySelectorAll(".nav-btn").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

switchView("upload");
