/** 开发验收：真实事件到下一帧绘制后；仅 uiAudit=1 时记录，不改变业务状态。 */
export function installUiAudit() {
  if (!new URLSearchParams(window.location.search).has("uiAudit")) return;
  for (const type of ["click", "input", "change"]) {
    document.addEventListener(type, (event) => {
      const element = event.target instanceof Element ? event.target : null;
      const control = element?.closest("button,input,select,[role=menuitem],[role=radio],[role=tab]");
      if (!control) return;
      const label = control.getAttribute("aria-label") || control.getAttribute("name") ||
        control.textContent?.trim().slice(0, 60) || control.tagName;
      const start = event.timeStamp;
      // rAF 发生在绘制前，随后任务在该帧绘制后取样；保留调度开销作为保守值。
      requestAnimationFrame(() => setTimeout(() => {
        console.info("ARENA_UI_AUDIT " + JSON.stringify({
          type, label, duration_ms: Math.round((performance.now() - start) * 100) / 100,
          path: window.location.pathname,
        }));
      }, 0));
    }, { capture: true });
  }
}
