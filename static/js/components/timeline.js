document.addEventListener("DOMContentLoaded", () => {
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const units = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];

  document.querySelectorAll("time[data-relative-time]").forEach((node) => {
    const timestamp = new Date(node.dateTime).getTime();
    if (!Number.isFinite(timestamp)) return;
    const delta = Math.round((timestamp - Date.now()) / 1000);
    const [unit, seconds] = units.find(([, size]) => Math.abs(delta) >= size) || ["second", 1];
    node.textContent = formatter.format(Math.round(delta / seconds), unit);
    node.title = new Date(timestamp).toLocaleString();
  });
});
