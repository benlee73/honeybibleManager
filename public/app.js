const API_ENDPOINT = "/analyze";

const THEME_KEY = "honeybible-theme";
const themeToggle = document.getElementById("themeToggle");
const themeIcon = themeToggle ? themeToggle.querySelector(".theme-icon") : null;
const themeLabel = themeToggle ? themeToggle.querySelector(".theme-label") : null;
const cheerButton = document.getElementById("cheerButton");

const applyTheme = (theme, persist) => {
  document.documentElement.dataset.theme = theme;
  if (themeToggle) {
    const isDark = theme === "dark";
    themeToggle.setAttribute("aria-pressed", String(isDark));
    if (themeIcon) {
      themeIcon.textContent = isDark ? "☀️" : "🌙";
    }
    if (themeLabel) {
      themeLabel.textContent = isDark ? "라이트 모드" : "다크 모드";
    }
  }
  if (persist) {
    localStorage.setItem(THEME_KEY, theme);
  }
};

if (themeToggle) {
  const storedTheme = localStorage.getItem(THEME_KEY);
  const prefersDark = window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initialTheme = storedTheme || (prefersDark ? "dark" : "light");

  applyTheme(initialTheme, Boolean(storedTheme));

  themeToggle.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === "dark"
      ? "light"
      : "dark";
    applyTheme(nextTheme, true);
  });
}

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

let currentObjectUrl = null;

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
};

const isCsvFile = (file) => {
  if (!file || !file.name) {
    return false;
  }
  return file.name.toLowerCase().endsWith(".csv");
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

const parseFilename = (contentDisposition) => {
  if (!contentDisposition) {
    return null;
  }
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch (error) {
      return utf8Match[1];
    }
  }
  const asciiMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return asciiMatch ? asciiMatch[1] : null;
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
  }
};

const parseCsvText = (text) => {
  const cleaned = text.replace(/^\uFEFF/, "");
  const lines = cleaned.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length === 0) {
    return { headers: [], rows: [] };
  }
  const parse = (line) => {
    const result = [];
    let current = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"' && line[i + 1] === '"') {
          current += '"';
          i += 1;
        } else if (ch === '"') {
          inQuotes = false;
        } else {
          current += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        result.push(current);
        current = "";
      } else {
        current += ch;
      }
    }
    result.push(current);
    return result;
  };
  const headers = parse(lines[0]);
  const rows = lines.slice(1).map(parse);
  return { headers, rows };
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

  let topName = "-";
  let topCount = 0;
  for (const [name, count] of Object.entries(nameCounts)) {
    if (count > topCount) {
      topCount = count;
      topName = name;
    }
  }

  return { members, dates: dateCount, avgRate, topName };
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

const showResults = (csvText, trackMode) => {
  if (!resultsSection) {
    return;
  }
  const { headers, rows } = parseCsvText(csvText);
  if (headers.length === 0) {
    return;
  }

  const stats = computeStats(headers, rows, trackMode);

  const statMembers = document.getElementById("statMembers");
  const statDates = document.getElementById("statDates");
  const statAvg = document.getElementById("statAvg");
  const statTop = document.getElementById("statTop");

  if (statMembers) animateValue(statMembers, stats.members, 600, "");
  if (statDates) animateValue(statDates, stats.dates, 600, "");
  if (statAvg) animateValue(statAvg, stats.avgRate, 800, "%");
  if (statTop) statTop.textContent = stats.topName;

  renderPreviewTable(headers, rows);

  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth" });
};

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];

  resetDownload();
  hideResults();

  if (!file) {
    analyzeButton.disabled = true;
    fileMeta.textContent = "선택된 파일 없음";
    setStatus("idle", "CSV 업로드를 기다리는 중입니다.");
    return;
  }

  if (!isCsvFile(file)) {
    analyzeButton.disabled = true;
    fileMeta.textContent = `선택됨: ${file.name}`;
    setStatus("error", ".csv 파일만 업로드할 수 있습니다.");
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
    setStatus("error", "분석 전에 CSV 파일을 선택하세요.");
    return;
  }

  if (!isCsvFile(file)) {
    setStatus("error", "선택한 파일이 CSV가 아닙니다.");
    return;
  }

  resetDownload();
  setFormEnabled(false);
  setStatus("loading", "CSV를 분석하는 중입니다. 잠시만 기다려주세요...");

  try {
    const formData = new FormData();
    formData.append("file", file, file.name);
    const trackMode = document.querySelector('input[name="trackMode"]:checked').value;
    formData.append("track_mode", trackMode);

    const response = await fetch(API_ENDPOINT, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await readErrorMessage(response));
    }

    const blob = await response.blob();
    const filename =
      parseFilename(response.headers.get("Content-Disposition")) ||
      "honeybible-results.csv";

    clearObjectUrl();
    currentObjectUrl = URL.createObjectURL(blob);
    downloadButton.href = currentObjectUrl;
    downloadButton.download = filename;
    downloadButton.classList.remove("is-disabled");
    downloadButton.setAttribute("aria-disabled", "false");

    setStatus("success", "분석 완료. 다운로드 준비가 끝났습니다.");

    const csvText = await blob.text();
    showResults(csvText, trackMode);
  } catch (error) {
    const message = error instanceof Error ? error.message : "분석에 실패했습니다.";
    setStatus("error", message);
  } finally {
    const canAnalyze = Boolean(fileInput.files[0]) && isCsvFile(fileInput.files[0]);
    fileInput.disabled = false;
    analyzeButton.disabled = !canAnalyze;
  }
});

window.addEventListener("beforeunload", () => {
  clearObjectUrl();
});
