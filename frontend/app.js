"use strict";

const API_BASE = "";
const POLL_MS = 2000;

const $ = (id) => document.getElementById(id);
const icon = (d) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICONS = {
  file: icon(
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  ),
  text: icon('<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h10"/>'),
  copy: icon(
    '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  ),
  download: icon(
    '<path d="M12 4v12"/><path d="m6 10 6 6 6-6"/><path d="M4 20h16"/>',
  ),
  delete: icon(
    '<path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/>',
  ),
};

const dropper = $("dropper");
let entries = []; // latest list from the server
let staged = null; // item waiting for submit, or null
let uploading = false;
let lastSignature = "";
let maxTextLength = 0; // set from /config
let maxFileBytes = 0; // set from /config
let maxTtl = 0; // minutes, set from /config

// current/max - under the textarea; red when over
function updateCounter() {
  const len = $("staged-text").value.length;
  $("char-count").hidden = $("staged-text").hidden;
  $("char-count").textContent = maxTextLength
    ? `${len.toLocaleString()} / ${maxTextLength.toLocaleString()}`
    : len.toLocaleString();
  $("char-count").classList.toggle(
    "over",
    maxTextLength && len > maxTextLength,
  );
}
$("staged-text").addEventListener("input", updateCounter);

// staging - show preview for a file or text
function stage(item) {
  if (uploading) return;
  staged = item;
  const isFile = item.type === "file";
  $("staged-file").hidden = !isFile;
  $("staged-text").hidden = isFile;
  if (isFile) {
    $("staged-file-name").textContent = item.file.name || "untitled";
    $("staged-file-size").textContent = formatBytes(item.file.size);
  } else {
    $("staged-text").value = item.text;
  }
  toggleStaged(true);
  updateCounter();
  (isFile ? $("submit-btn") : $("staged-text")).focus();
}

function clearStaged() {
  staged = null;
  toggleStaged(false);
}

// switch between drop hint and preview
function toggleStaged(on) {
  $("dropper-hint").hidden = on;
  $("staged").hidden = !on;
  dropper.classList.toggle("has-staged", on);
  setStatus("");
  setProgress($("progress"), null);
}

// confirm leaving page while uploading is true
window.addEventListener("beforeunload", (e) => {
  if (uploading) e.preventDefault();
});

// open file dropper on click, ignore while previewing
dropper.addEventListener("click", (e) => {
  if (!staged && !e.target.closest("button, input")) $("file-input").click();
});

$("file-input").addEventListener("change", (e) => {
  if (e.target.files[0]) stage({ type: "file", file: e.target.files[0] });
  e.target.value = "";
});

// focusing textbox opens full size textbox
$("quick-text").addEventListener("focus", () =>
  stage({ type: "text", text: "" }),
);

// stop the browser from opening files dropped outside of the dropper
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => e.preventDefault());
// highlight when dragging item over the dropper - stage on drop
dropper.addEventListener("dragover", () => dropper.classList.add("dragging"));
dropper.addEventListener("dragleave", (e) => {
  if (!dropper.contains(e.relatedTarget)) dropper.classList.remove("dragging");
});
dropper.addEventListener("drop", (e) => {
  dropper.classList.remove("dragging");
  if (e.dataTransfer.files[0])
    stage({ type: "file", file: e.dataTransfer.files[0] });
});

// ctrl+v anywhere to stage files; text gets pasted into full size textbox
document.addEventListener("paste", (e) => {
  if (settings.open) return;
  const file = e.clipboardData.files[0];
  const text = e.clipboardData.getData("text/plain");
  if (e.target === $("staged-text") && !file) return;
  e.preventDefault();
  if (file) stage({ type: "file", file });
  else if (text) stage({ type: "text", text });
});

// settings popup
const settings = $("settings");
$("settings-btn").addEventListener("click", () => settings.showModal());
$("settings-close").addEventListener("click", () => settings.close());
settings.addEventListener("click", (e) => {
  if (e.target === settings) settings.close();
});

$("submit-btn").addEventListener("click", upload);
$("cancel-btn").addEventListener("click", clearStaged);

// send staged item to /entries POST endpoint; show progress for files
async function upload() {
  if (!staged || uploading) return;
  const form = new FormData();
  form.append("type", staged.type);
  if (staged.type === "file") {
    if (maxFileBytes && staged.file.size > maxFileBytes)
      return setStatus(
        `File too large. Maximum: ${formatBytes(maxFileBytes)}`,
        true,
      );
    form.append("file", staged.file);
  } else if ($("staged-text").value.trim())
    form.append("text", $("staged-text").value);
  else return setStatus("Nothing to submit.", true);

  const ttl = Math.round(+$("ttl-h").value * 60 + +$("ttl-m").value);
  if (maxTtl && (ttl < 1 || ttl > maxTtl))
    return setStatus(`Expiry must be 1m – ${formatDuration(maxTtl)}`, true);
  if (ttl) form.append("ttl_minutes", ttl);

  const isFile = staged.type === "file";
  setUploading(true);
  setStatus("Sending…");
  try {
    await request("POST", `${API_BASE}/entries`, form, (pct) => {
      if (!isFile) return;
      setProgress($("progress"), pct);
      setStatus(pct < 100 ? `Uploading… ${pct}%` : "Processing…");
    });
    clearStaged();
    showToast("Synced");
    loadConfig();
    refresh();
  } catch (msg) {
    setProgress($("progress"), null);
    setStatus(msg, true);
  }
  setUploading(false);
}

function setUploading(on) {
  uploading = on;
  $("submit-btn").disabled = on;
  $("cancel-btn").disabled = on;
  $("staged-text").readOnly = on;
  $("submit-btn").textContent = on ? "Sending…" : "Submit";
}

// API calls (XHR for reporting upload progress)
function request(method, url, body, onProgress, responseType = "") {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    xhr.responseType = responseType;
    if (onProgress) {
      (body ? xhr.upload : xhr).onprogress = (e) => {
        if (e.lengthComputable)
          onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }
    xhr.onload = () =>
      xhr.status < 300 ? resolve(xhr.response) : reject(errorMessage(xhr));
    xhr.onerror = () => reject("Couldn't reach the server.");
    // if body (file upload), no timeout
    xhr.timeout = body ? 0 : 10000;
    xhr.ontimeout = () => reject("Server timed out.");
    xhr.send(body);
  });
}

// get FastAPI detail message from error response
function errorMessage(xhr) {
  try {
    const { detail } = JSON.parse(xhr.responseText);
    const msg = Array.isArray(detail) ? detail[0]?.msg : detail;
    if (msg) return msg;
  } catch {}
  return `Something went wrong (${xhr.status}).`;
}

// get entries, update the connection dot, rebuild the list if it changed
async function refresh() {
  try {
    entries = await request("GET", `${API_BASE}/entries`, null, null, "json");
    document
      .querySelectorAll(".conn")
      .forEach((element) => element.classList.remove("offline"));
    document
      .querySelectorAll(".conn")
      .forEach((element) => (element.title = "Connected"));
  } catch {
    document
      .querySelectorAll(".conn")
      .forEach((element) => element.classList.add("offline"));
    document
      .querySelectorAll(".conn")
      .forEach((element) => (element.title = "Can't reach the server"));
    return;
  }

  const signature = entries.map((e) => e.id + e.expires_at).join();
  if (signature !== lastSignature) {
    lastSignature = signature;
    $("list-section").hidden = !entries.length;
    $("count").textContent =
      `${entries.length} item${entries.length === 1 ? "" : "s"}`;
    $("entries").innerHTML = entries.map(entryHtml).join("");
  }
  updateTimes();
}

// one list row
function entryHtml(entry) {
  const isFile = entry.type === "file";
  const btn = (action, label) =>
    `<button class="btn" data-action="${action}">${ICONS[action]}<span class="btn-label">${label}</span></button>`;
  return `
    <li class="entry" data-id="${esc(entry.id)}" draggable="${isFile}">
      <div class="entry-icon">${isFile ? ICONS.file : ICONS.text}</div>
      <div class="entry-info">
        <div class="entry-name">${esc(isFile ? entry.name : entry.name)}</div>
        <div class="entry-meta">${isFile ? formatBytes(entry.size) : `${esc(entry.size)} chars`} · <span class="ttl" data-expires="${esc(entry.expires_at)}"></span></div>
      </div>
      <div class="entry-actions">${isFile ? btn("download", "Download") : btn("copy", "Copy")}${btn("delete", "Delete")}</div>
    </li>`;
}

// maps a button's data-action to its fn
const actions = {
  copy: copyEntry,
  download: downloadEntry,
  delete: deleteEntry,
};

// a listener per row
$("entries").addEventListener("click", (e) => {
  const row = e.target.closest(".entry");
  if (!row) return;
  const entry = entries.find((x) => x.id === row.dataset.id);
  const button = e.target.closest("[data-action]");
  const action =
    button?.dataset.action ?? (entry.type === "file" ? "download" : "copy");
  actions[action](entry, row, button);
});

// download a file from the server
function downloadEntry(entry) {
  const a = document.createElement("a");
  a.href = entryUrl(entry.id);
  a.download = entry.name;
  a.click();
}

// check if entry.name = size in db. copy current if true, request from db if false to get full textcontent
async function copyEntry(entry) {
  try {
    const text =
      entry.size === entry.name.length
        ? entry.name
        : await request("GET", entryUrl(entry.id), null, null, "json");
    showToast((await copyText(text)) ? "Copied" : "Couldn't copy");
  } catch {
    showToast("Couldn't copy");
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.cssText = "position:fixed;opacity:0";
    document.body.append(textarea);
    textarea.select();
    textarea.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    textarea.remove();
    return ok;
  }
}

async function deleteEntry(entry, row, btn) {
  if (!confirmed(btn)) return;
  await request("DELETE", entryUrl(entry.id)).catch(() =>
    showToast("Couldn't delete"),
  );
  refresh();
}

$("delete-all-btn").addEventListener("click", async (e) => {
  if (!confirmed(e.currentTarget, "Confirm delete all")) return;
  await request("DELETE", `${API_BASE}/entries`).catch(() =>
    showToast("Couldn't delete"),
  );
  refresh();
});

function confirmed(btn, label = "Confirm") {
  if (btn.classList.contains("confirm")) return true;
  const labelEl = btn.querySelector(".btn-label");
  const original = labelEl.textContent;
  btn.classList.add("confirm");
  labelEl.textContent = label;
  setTimeout(() => {
    btn.classList.remove("confirm");
    labelEl.textContent = original;
  }, 3000);
  return false;
}

const entryUrl = (id) => `${API_BASE}/entries/${encodeURIComponent(id)}`;

// cleanse server values before parsing to HTML
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

const firstLine = (text = "") =>
  text
    .split("\n")
    .find((l) => l.trim())
    ?.trim() || "Text";

function updateTimes() {
  for (const el of document.querySelectorAll(".ttl")) {
    const left = Math.floor(el.dataset.expires - Date.now() / 1000);
    el.textContent =
      left > 0 ? `${formatRemainingTime(left)} left` : "expiring…";
    el.classList.toggle("soon", left <= 60);
  }
}

function formatRemainingTime(s) {
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (s < 60) return `${s}s`;
  if (m < 60) return `${m}m`;
  if (h < 24) return m % 60 ? `${h}h ${m % 60}m` : `${h}h`;
  if (d < 7) return h % 24 ? `${d}d ${h % 24}h` : `${d}d`;
  if (d < 30) return `${Math.floor(d / 7)}w`;
  return `${Math.floor(d / 30)}mo`;
}

// exact duration for config labels, 90 = "1h 30m"
function formatDuration(minutes) {
  const d = Math.floor(minutes / 1440);
  const h = Math.floor((minutes % 1440) / 60);
  const m = minutes % 60;
  return (
    [d && `${d}d`, h && `${h}h`, m && `${m}m`].filter(Boolean).join(" ") || "0m"
  );
}

function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return `${i > 0 && bytes < 10 ? bytes.toFixed(1) : Math.round(bytes)} ${units[i]}`;
}

function setStatus(msg, isError = false) {
  $("status").textContent = msg;
  $("status").classList.toggle("error", isError);
}

function setProgress(bar, pct) {
  bar.hidden = pct === null;
  bar.firstElementChild.style.width = `${pct ?? 0}%`;
}

let toastTimer;
function showToast(msg) {
  $("toast").textContent = msg;
  $("toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").classList.remove("show"), 1800);
}

async function getConfig() {
  try {
    const res = await request("GET", `${API_BASE}/config`, null, null, "json");
    return res;
  } catch {
    showToast("Couldn't get config");
    return null;
  }
}

// populate settings labels from server values
async function loadConfig() {
  const res = await getConfig();
  if (!res) return;
  maxTextLength = res["max_text_length"];
  maxFileBytes = res["max_file_size_mb"] * 1024 * 1024;
  maxTtl = res["max_ttl_minutes"];
  $("ttl-h").max = Math.floor(maxTtl / 60);
  $("ttl-h").value = Math.floor(res["default_ttl_minutes"] / 60);
  $("ttl-m").value = res["default_ttl_minutes"] % 60;
  $("cfg-max-file").textContent = formatBytes(
    res["max_file_size_mb"] * 1024 * 1024,
  );
  $("cfg-max-text").textContent =
    res["max_text_length"].toLocaleString() + " Characters";
  $("cfg-default-ttl").textContent = formatDuration(res["default_ttl_minutes"]);
  $("cfg-max-ttl").textContent = formatDuration(res["max_ttl_minutes"]);
}

refresh();
loadConfig();
setInterval(updateTimes, 1000);
setInterval(() => {
  if (!document.hidden) refresh();
}, POLL_MS);
