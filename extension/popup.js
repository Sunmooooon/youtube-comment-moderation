document.getElementById("fetchBtn").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const videoId = new URL(tab.url).searchParams.get("v");

  if (videoId) {
    document.getElementById("status").textContent = "Menghubungi dashboard lokal…";

    fetch("http://127.0.0.1:5000/fetch-comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ videoId })
    })
    .then(async (res) => {
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    })
    .then(data => {
      document.getElementById("status").textContent = `${data.comment_count} komentar ditemukan.`;
    })
    .catch(err => {
      document.getElementById("status").textContent = `Gagal: ${err.message}`;
      console.error(err);
    });
  } else {
    document.getElementById("status").textContent = "Buka halaman video YouTube terlebih dahulu.";
  }
});
