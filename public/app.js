const API_ENDPOINT = "/analyze";

/* 테마 순환 */
const THEMES = [
  { id: "honey", label: "🍯 기본" },
  { id: "bw", label: "🖤 B&W" },
  { id: "brew", label: "☕ Brew" },
  { id: "neon", label: "⚡ 네온" },
];

const themeButton = document.getElementById("themeButton");

const applyTheme = (themeId) => {
  const theme = THEMES.find((t) => t.id === themeId) || THEMES[0];
  if (theme.id === "honey") {
    delete document.body.dataset.theme;
  } else {
    document.body.dataset.theme = theme.id;
  }
  if (themeButton) {
    themeButton.textContent = theme.label;
  }
  localStorage.setItem("theme", theme.id);
};

(() => {
  const saved = localStorage.getItem("theme");
  applyTheme(saved || "honey");
})();

if (themeButton) {
  themeButton.addEventListener("click", () => {
    const current = localStorage.getItem("theme") || "honey";
    const idx = THEMES.findIndex((t) => t.id === current);
    const next = THEMES[(idx + 1) % THEMES.length];
    applyTheme(next.id);
  });
}

const cheerButton = document.getElementById("cheerButton");

const spawnHearts = (originX, originY) => {
  if (!cheerButton) {
    return;
  }
  const count = 8 + Math.floor(Math.random() * 4);
  for (let index = 0; index < count; index += 1) {
    const heart = document.createElement("span");
    heart.className = "cheer-heart";
    heart.style.left = `${originX}px`;
    heart.style.top = `${originY}px`;
    heart.style.setProperty("--x", `${(Math.random() * 2 - 1) * 40}px`);
    heart.style.setProperty("--y", `${30 + Math.random() * 50}px`);
    heart.style.setProperty("--scale", (0.6 + Math.random() * 0.7).toFixed(2));
    heart.style.setProperty("--duration", `${900 + Math.random() * 600}ms`);
    heart.style.setProperty("--delay", `${Math.random() * 120}ms`);
    heart.style.setProperty("--rotation", `${35 + Math.random() * 20}deg`);
    cheerButton.appendChild(heart);

    const duration = Number.parseFloat(
      heart.style.getPropertyValue("--duration").replace("ms", ""),
    );
    const delay = Number.parseFloat(
      heart.style.getPropertyValue("--delay").replace("ms", ""),
    );
    window.setTimeout(() => {
      heart.remove();
    }, duration + delay + 120);
  }
};

if (cheerButton) {
  cheerButton.addEventListener("click", (event) => {
    const rect = cheerButton.getBoundingClientRect();
    const originX = event.clientX ? event.clientX - rect.left : rect.width / 2;
    const originY = event.clientY ? event.clientY - rect.top : rect.height / 2;
    spawnHearts(originX, originY);
  });
}

const form = document.getElementById("analyzeForm");
const fileInput = document.getElementById("csvFile");
const analyzeButton = document.getElementById("analyzeButton");
const downloadButton = document.getElementById("downloadButton");
const status = document.getElementById("status");
const statusText = status.querySelector(".status-text");
const fileMeta = document.getElementById("fileMeta");

const resultsSection = document.getElementById("results");
const previewTable = document.getElementById("previewTable");
const progressBar = document.getElementById("progressBar");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const imageView = document.getElementById("imageView");
const resultImage = document.getElementById("resultImage");
const driveButton = document.getElementById("driveButton");

let currentObjectUrl = null;
let currentImageBase64 = null;
let currentXlsxBase64 = null;
let currentDriveFilename = null;

const setStatus = (state, message) => {
  status.dataset.state = state;
  statusText.textContent = message;
};

const clearObjectUrl = () => {
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = null;
  }
};

const resetDownload = () => {
  clearObjectUrl();
  downloadButton.classList.add("is-disabled");
  downloadButton.setAttribute("aria-disabled", "true");
  downloadButton.removeAttribute("href");
  downloadButton.removeAttribute("download");
  currentImageBase64 = null;
  if (resultImage) {
    resultImage.removeAttribute("src");
  }
  currentXlsxBase64 = null;
  currentDriveFilename = null;
  if (driveButton) {
    driveButton.classList.add("is-disabled");
    driveButton.disabled = true;
    driveButton.innerHTML = '구글 드라이브로 업로드';
  }
  if (progressBar) {
    progressBar.hidden = true;
    progressFill.style.width = "0%";
    progressText.textContent = "0%";
  }
};

const VALID_EXTENSIONS = [".csv", ".txt", ".zip"];

const isValidFile = (file) => {
  if (!file || !file.name) {
    return false;
  }
  const name = file.name.toLowerCase();
  return VALID_EXTENSIONS.some((ext) => name.endsWith(ext));
};

const formatBytes = (bytes) => {
  if (!Number.isFinite(bytes)) {
    return "";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

const readErrorMessage = async (response) => {
  const contentType = response.headers.get("Content-Type") || "";
  try {
    if (contentType.includes("application/json")) {
      const data = await response.json();
      if (data && typeof data.message === "string") {
        return data.message;
      }
    }
    const text = await response.text();
    if (text && text.trim()) {
      return text.trim();
    }
  } catch (error) {
    // Ignore parsing errors.
  }
  return `서버 오류 (${response.status})`;
};

const setFormEnabled = (enabled) => {
  fileInput.disabled = !enabled;
  analyzeButton.disabled = !enabled;
};

const hideResults = () => {
  if (resultsSection) {
    resultsSection.hidden = true;
    resultsSection.classList.remove("pop-in");
  }
};

const computeStats = (headers, rows, trackMode) => {
  const dateStart = trackMode === "dual" ? 3 : 2;
  const dateCount = Math.max(0, headers.length - dateStart);

  const nameSet = new Set();
  rows.forEach((row) => nameSet.add(row[0]));
  const members = nameSet.size;

  let totalO = 0;
  const nameCounts = {};
  rows.forEach((row) => {
    let rowO = 0;
    for (let i = dateStart; i < row.length; i += 1) {
      if (row[i] === "O") {
        rowO += 1;
      }
    }
    totalO += rowO;
    const name = row[0];
    nameCounts[name] = (nameCounts[name] || 0) + rowO;
  });

  const totalCells = rows.length * dateCount;
  const avgRate = totalCells > 0 ? Math.round((totalO / totalCells) * 100) : 0;

  let perfectCount = 0;
  if (trackMode === "dual") {
    const oldNameCounts = {};
    rows.forEach((row) => {
      if (row[2] !== "구약") return;
      let rowO = 0;
      for (let i = dateStart; i < row.length; i += 1) {
        if (row[i] === "O") rowO += 1;
      }
      oldNameCounts[row[0]] = (oldNameCounts[row[0]] || 0) + rowO;
    });
    for (const [name, count] of Object.entries(oldNameCounts)) {
      if (dateCount > 0 && count === dateCount) perfectCount += 1;
    }
  } else {
    const nameTotalCells = {};
    rows.forEach((row) => {
      const name = row[0];
      nameTotalCells[name] = (nameTotalCells[name] || 0) + dateCount;
    });
    for (const [name, total] of Object.entries(nameTotalCells)) {
      if (total > 0 && nameCounts[name] === total) {
        perfectCount += 1;
      }
    }
  }

  return { members, dates: dateCount, avgRate, perfectCount };
};

const animateValue = (element, end, duration, suffix) => {
  const start = 0;
  const startTime = performance.now();
  const step = (now) => {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(start + (end - start) * eased);
    element.textContent = current + (suffix || "");
    if (progress < 1) {
      requestAnimationFrame(step);
    }
  };
  requestAnimationFrame(step);
};

const renderPreviewTable = (headers, rows) => {
  if (!previewTable) {
    return;
  }
  previewTable.textContent = "";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((h) => {
    const th = document.createElement("th");
    th.textContent = h;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  previewTable.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = cell;
      if (cell === "O") {
        td.className = "mark";
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  previewTable.appendChild(tbody);
};

const showResults = (headers, rows, trackMode) => {
  if (!resultsSection) {
    return;
  }
  if (headers.length === 0) {
    return;
  }

  const stats = computeStats(headers, rows, trackMode);

  const statMembers = document.getElementById("statMembers");
  const statPerfect = document.getElementById("statPerfect");
  const statDates = document.getElementById("statDates");
  const statAvg = document.getElementById("statAvg");

  if (statMembers) animateValue(statMembers, stats.members, 600, "");
  if (statPerfect) animateValue(statPerfect, stats.perfectCount, 600, "명");
  if (statDates) animateValue(statDates, stats.dates, 600, "");
  if (statAvg) animateValue(statAvg, stats.avgRate, 800, "%");

  renderPreviewTable(headers, rows);

  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth" });
};

const setProgress = (percent) => {
  if (!progressBar) return;
  progressBar.hidden = false;
  progressFill.style.width = `${percent}%`;
  progressText.textContent = `${percent}%`;
};

const animateProgress = (from, to, duration, callback) => {
  const startTime = performance.now();
  const step = (now) => {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(from + (to - from) * eased);
    setProgress(current);
    if (progress < 1) {
      requestAnimationFrame(step);
    } else if (callback) {
      callback();
    }
  };
  requestAnimationFrame(step);
};

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];

  resetDownload();
  hideResults();

  if (!file) {
    analyzeButton.disabled = true;
    fileMeta.textContent = "선택된 파일 없음";
    setStatus("idle", "파일 업로드를 기다리는 중입니다.");
    return;
  }

  if (!isValidFile(file)) {
    analyzeButton.disabled = true;
    fileMeta.textContent = `선택됨: ${file.name}`;
    setStatus("error", ".csv, .txt, .zip 파일만 업로드할 수 있습니다.");
    return;
  }

  analyzeButton.disabled = false;
  fileMeta.textContent = `선택됨: ${file.name} (${formatBytes(file.size)})`;
  setStatus("idle", "분석 준비 완료.");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files[0];
  if (!file) {
    setStatus("error", "분석 전에 파일을 선택하세요.");
    return;
  }

  if (!isValidFile(file)) {
    setStatus("error", "지원하지 않는 파일 형식입니다.");
    return;
  }

  resetDownload();
  setFormEnabled(false);
  setProgress(0);
  setStatus("loading", "파일을 분석하는 중입니다. 잠시만 기다려주세요...");

  setProgress(0);

  try {
    const formData = new FormData();
    formData.append("file", file, file.name);
    const trackMode = document.querySelector('input[name="trackMode"]:checked').value;
    formData.append("track_mode", trackMode);
    formData.append("theme", localStorage.getItem("theme") || "honey");

    const fetchPromise = fetch(API_ENDPOINT, {
      method: "POST",
      body: formData,
    });

    const progressPromise = new Promise((resolve) => {
      animateProgress(0, 100, 1000, resolve);
    });

    const [response] = await Promise.all([fetchPromise, progressPromise]);

    if (!response.ok) {
      throw new Error(await readErrorMessage(response));
    }

    const data = await response.json();
    const xlsxBinary = atob(data.xlsx_base64);
    const xlsxArray = new Uint8Array(xlsxBinary.length);
    for (let i = 0; i < xlsxBinary.length; i += 1) {
      xlsxArray[i] = xlsxBinary.charCodeAt(i);
    }
    const blob = new Blob([xlsxArray], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const filename = data.filename || "honeybible-results.xlsx";

    clearObjectUrl();
    currentObjectUrl = URL.createObjectURL(blob);

    const { headers, rows } = data.preview;

    setStatus("success", "다운로드 준비가 끝났습니다.");
    resultsSection.classList.add("pop-in");
    showResults(headers, rows, trackMode);
    downloadButton.href = currentObjectUrl;
    downloadButton.download = filename;
    downloadButton.classList.remove("is-disabled");
    downloadButton.setAttribute("aria-disabled", "false");

    if (data.image_base64 && resultImage) {
      currentImageBase64 = data.image_base64;
      resultImage.src = `data:image/png;base64,${currentImageBase64}`;
    }

    if (data.xlsx_base64 && driveButton) {
      currentXlsxBase64 = data.xlsx_base64;
      currentDriveFilename = data.drive_filename || null;
      driveButton.classList.remove("is-disabled");
      driveButton.disabled = false;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "분석에 실패했습니다.";
    setStatus("error", message);
  } finally {
    const canAnalyze = Boolean(fileInput.files[0]) && isValidFile(fileInput.files[0]);
    fileInput.disabled = false;
    analyzeButton.disabled = !canAnalyze;
  }
});

if (driveButton) {
  driveButton.addEventListener("click", async () => {
    if (!currentXlsxBase64) return;

    const originalHTML = driveButton.innerHTML;
    driveButton.innerHTML = '업로드 중...';
    driveButton.disabled = true;

    try {
      const response = await fetch("/upload-drive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          xlsx_base64: currentXlsxBase64,
          ...(currentDriveFilename && { filename: currentDriveFilename }),
        }),
      });

      const result = await response.json();

      if (result.success) {
        driveButton.innerHTML = '업로드 완료!';
        setTimeout(() => {
          driveButton.innerHTML = originalHTML;
          driveButton.disabled = false;
        }, 3000);
      } else {
        const msg = result.message || "업로드에 실패했습니다.";
        driveButton.innerHTML = `실패: ${msg}`;
        setTimeout(() => {
          driveButton.innerHTML = originalHTML;
          driveButton.disabled = false;
        }, 4000);
      }
    } catch (error) {
      driveButton.innerHTML = '업로드 오류 발생';
      setTimeout(() => {
        driveButton.innerHTML = originalHTML;
        driveButton.disabled = false;
      }, 4000);
    }
  });
}

window.addEventListener("beforeunload", () => {
  clearObjectUrl();
});

/* 사용 방법 탭 전환 */
const switchGuideTab = (target) => {
  const note = document.querySelector(".note");
  if (!note) return;
  note.querySelectorAll(".guide-tab").forEach((t) => {
    const active = t.dataset.tab === target;
    t.classList.toggle("is-active", active);
    t.setAttribute("aria-selected", String(active));
  });
  note.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== target;
  });
};

document.querySelectorAll(".guide-tab").forEach((tab) => {
  tab.addEventListener("click", () => switchGuideTab(tab.dataset.tab));
});

if (/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
  switchGuideTab("mobile");
}
