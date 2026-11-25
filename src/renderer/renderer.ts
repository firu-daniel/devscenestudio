const versionsElement = document.querySelector<HTMLElement>("#versions");

if (versionsElement) {
  const { electron, chrome, node } = window.studio.versions;
  versionsElement.textContent = `Electron ${electron} · Chromium ${chrome} · Node ${node}`;
}
