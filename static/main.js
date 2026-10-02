const dialog = document.querySelector("#video-dialog");
const title = document.querySelector("#video-title");
const stats = document.querySelector("#video-stats");
const comments = document.querySelector("#comment-list");
const analysis = document.querySelector("#analysis");
const processButton = document.querySelector("#process-video");
const processStatus = document.querySelector("#process-status");
let currentVideoId = null;
let analysisTimer = null;

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request gagal (${response.status})`);
  }
  return payload;
}

function renderStats(video) {
  stats.replaceChildren();
  const entries = [
    ["Views", video.views],
    ["Likes", video.likes],
    ["Komentar", video.comments],
  ];
  entries.forEach(([label, value]) => {
    const item = document.createElement("div");
    const labelNode = document.createElement("span");
    const valueNode = document.createElement("strong");
    labelNode.textContent = label;
    valueNode.textContent = value;
    item.append(labelNode, valueNode);
    stats.append(item);
  });
}

function renderComments(items) {
  comments.replaceChildren();
  if (!items.length) {
    comments.textContent = "Belum ada komentar publik.";
    return;
  }
  items.forEach((comment) => {
    const item = document.createElement("p");
    // textContent is intentional: YouTube comments are untrusted input.
    item.textContent = comment.text;
    comments.append(item);
  });
}

async function refreshAnalysis() {
  if (!currentVideoId) return;
  try {
    const result = await requestJson(`/api/videos/${currentVideoId}/analysis`);
    processStatus.textContent = result.state === "running" ? "Sedang diproses…" : result.state;
    if (result.analysis) analysis.textContent = result.analysis;
    if (["completed", "failed"].includes(result.state)) {
      clearInterval(analysisTimer);
      analysisTimer = null;
      processButton.disabled = false;
      if (result.state === "failed") analysis.textContent = result.error || "Proses gagal.";
    }
  } catch (error) {
    if (!error.message.includes("404")) processStatus.textContent = error.message;
  }
}

async function openVideo(videoId) {
  currentVideoId = videoId;
  title.textContent = "Memuat…";
  stats.replaceChildren();
  comments.textContent = "Memuat komentar…";
  analysis.textContent = "Belum ada analisis.";
  processStatus.textContent = "";
  dialog.showModal();

  try {
    const [video, commentPayload] = await Promise.all([
      requestJson(`/api/videos/${videoId}`),
      requestJson(`/api/videos/${videoId}/comments`),
    ]);
    title.textContent = video.title;
    renderStats(video);
    renderComments(commentPayload.comments);
    await refreshAnalysis();
  } catch (error) {
    processStatus.textContent = error.message;
  }
}

document.querySelectorAll(".video-card").forEach((button) => {
  button.addEventListener("click", () => openVideo(button.dataset.videoId));
});

document.querySelector("#close-dialog")?.addEventListener("click", () => {
  dialog.close();
});

dialog?.addEventListener("close", () => {
  if (analysisTimer) clearInterval(analysisTimer);
  analysisTimer = null;
});

processButton?.addEventListener("click", async () => {
  if (!currentVideoId) return;
  const action = window.APP_CONFIG.autoModeration
    ? "Komentar yang diklasifikasikan sebagai judol akan ditolak dari channel. Lanjutkan?"
    : "Komentar akan dianalisis tanpa dimoderasi. Lanjutkan?";
  if (!window.confirm(action)) return;

  processButton.disabled = true;
  processStatus.textContent = "Memulai…";
  try {
    await requestJson(`/api/videos/${currentVideoId}/process`, { method: "POST" });
    processStatus.textContent = "Sedang diproses…";
    analysisTimer = setInterval(refreshAnalysis, 3000);
  } catch (error) {
    processStatus.textContent = error.message;
    processButton.disabled = false;
  }
});
