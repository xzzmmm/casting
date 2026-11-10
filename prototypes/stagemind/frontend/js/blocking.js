/* 台位动线视图：舞台俯视 + 时间滑块。 */
const BlockingView = {
  render(container) {
    container.innerHTML = `
      <section class="card">
        <h2>台位动线图</h2>
        <p class="hint">W6-W8 接入姿态估计后，这里会绘制舞台俯视轨迹并支持时间滑块回放。</p>
        <canvas id="blocking-canvas" width="880" height="480"></canvas>
      </section>`;

    const canvas = document.getElementById("blocking-canvas");
    const ctx = canvas.getContext("2d");
    const palette = getComputedStyle(canvas);
    ctx.fillStyle = palette.getPropertyValue("--stage").trim();
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = palette.getPropertyValue("--muted").trim();
    ctx.font = "14px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("舞台俯视（待接入数据）", canvas.width / 2, canvas.height / 2);
  },
};
