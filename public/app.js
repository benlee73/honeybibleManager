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
const imageToggle = document.getElementById("imageToggle");
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
  if (imageToggle) {
    imageToggle.hidden = true;
    imageToggle.classList.remove("is-open");
  }
  if (imageView) {
    imageView.hidden = true;
  }
  currentXlsxBase64 = null;
  currentDriveFilename = null;
  if (driveButton) {
    driveButton.classList.add("is-disabled");
    driveButton.disabled = true;
    driveButton.textContent = '구글 드라이브로 업로드';
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
  const nameIdx = headers.indexOf("이름");
  const dateStart = headers.findIndex(
    (h) => !["담당", "이름", "이모티콘", "트랙"].includes(h),
  );
  const dateCount = dateStart >= 0 ? headers.length - dateStart : 0;

  const nameSet = new Set();
  rows.forEach((row) => nameSet.add(row[nameIdx]));
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
    const name = row[nameIdx];
    nameCounts[name] = (nameCounts[name] || 0) + rowO;
  });

  const totalCells = rows.length * dateCount;
  const avgRate = totalCells > 0 ? Math.round((totalO / totalCells) * 100) : 0;

  let perfectCount = 0;
  const trackIdx = headers.indexOf("트랙");
  if (trackMode === "dual") {
    const oldNameCounts = {};
    rows.forEach((row) => {
      if (row[trackIdx] !== "구약") return;
      let rowO = 0;
      for (let i = dateStart; i < row.length; i += 1) {
        if (row[i] === "O") rowO += 1;
      }
      oldNameCounts[row[nameIdx]] = (oldNameCounts[row[nameIdx]] || 0) + rowO;
    });
    for (const [name, count] of Object.entries(oldNameCounts)) {
      if (dateCount > 0 && count === dateCount) perfectCount += 1;
    }
  } else {
    const nameTotalCells = {};
    rows.forEach((row) => {
      const name = row[nameIdx];
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

  const resultsTitle = document.getElementById("resultsTitle");
  if (resultsTitle) {
    resultsTitle.textContent = trackMode === "merged" ? "통합 결과" : "분석 결과";
  }

  if (trackMode === "merged") {
    if (imageToggle) { imageToggle.hidden = true; imageToggle.classList.remove("is-open"); }
    if (imageView) imageView.hidden = true;
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

const PROGRESS_STAGES = [
  { label: "메시지 분석 중", to: 50,  duration: 1200 },
  { label: "결과 생성 중",   to: 95,  duration: 8000 },
];

const setProgress = (percent, label) => {
  if (!progressBar) return;
  progressBar.hidden = false;
  progressFill.style.width = `${percent}%`;
  progressText.textContent = label || `${percent}%`;
};

const MIN_PROGRESS_MS = 1500;

const runStagedProgress = () => {
  let cancelled = false;
  let currentRaf = 0;
  let currentPercent = 0;
  const globalStart = performance.now();

  const animateStage = (from, to, duration, label) =>
    new Promise((resolve) => {
      const startTime = performance.now();
      const step = (now) => {
        if (cancelled) { resolve(); return; }
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        currentPercent = Math.round(from + (to - from) * eased);
        setProgress(currentPercent, label);
        if (progress < 1) {
          currentRaf = requestAnimationFrame(step);
        } else {
          resolve();
        }
      };
      currentRaf = requestAnimationFrame(step);
    });

  const run = async () => {
    let from = 0;
    for (const stage of PROGRESS_STAGES) {
      if (cancelled) break;
      await animateStage(from, stage.to, stage.duration, stage.label);
      from = stage.to;
    }
  };

  run();

  return {
    finish: () => {
      cancelled = true;
      cancelAnimationFrame(currentRaf);
      const elapsed = performance.now() - globalStart;
      const remaining = Math.max(0, MIN_PROGRESS_MS - elapsed);

      const pending = PROGRESS_STAGES
        .filter((s) => s.to > currentPercent)
        .map((s) => ({ to: s.to, label: s.label }));
      pending.push({ to: 100, label: "완료!" });

      if (remaining === 0) {
        setProgress(100, "완료!");
        return Promise.resolve();
      }

      const timePerStage = remaining / pending.length;

      return new Promise((resolve) => {
        let idx = 0;
        let from = currentPercent;
        const runNext = () => {
          if (idx >= pending.length) { resolve(); return; }
          const stage = pending[idx];
          const start = performance.now();
          const step = (now) => {
            const t = Math.min((now - start) / timePerStage, 1);
            const eased = 1 - Math.pow(1 - t, 3);
            setProgress(Math.round(from + (stage.to - from) * eased), stage.label);
            if (t < 1) {
              requestAnimationFrame(step);
            } else {
              from = stage.to;
              idx += 1;
              runNext();
            }
          };
          requestAnimationFrame(step);
        };
        runNext();
      });
    },
  };
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

  const staged = runStagedProgress();

  try {
    const formData = new FormData();
    formData.append("file", file, file.name);
    formData.append("theme", localStorage.getItem("theme") || "honey");

    const response = await fetch(API_ENDPOINT, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      await staged.finish();
      throw new Error(await readErrorMessage(response));
    }

    await staged.finish();
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
    showResults(headers, rows, data.track_mode);
    downloadButton.href = currentObjectUrl;
    downloadButton.download = filename;
    downloadButton.classList.remove("is-disabled");
    downloadButton.setAttribute("aria-disabled", "false");

    if (data.image_base64 && resultImage) {
      currentImageBase64 = data.image_base64;
      resultImage.src = `data:image/png;base64,${currentImageBase64}`;
      if (imageToggle) {
        imageToggle.hidden = false;
      }
    }

    if (data.xlsx_base64 && driveButton) {
      currentXlsxBase64 = data.xlsx_base64;
      currentDriveFilename = data.drive_filename || null;
      driveButton.classList.remove("is-disabled");
      driveButton.disabled = false;
    }
  } catch (error) {
    await staged.finish();
    const message = error instanceof Error ? error.message : "분석에 실패했습니다.";
    setStatus("error", message);
  } finally {
    const canAnalyze = Boolean(fileInput.files[0]) && isValidFile(fileInput.files[0]);
    fileInput.disabled = false;
    analyzeButton.disabled = !canAnalyze;
  }
});

if (imageToggle) {
  imageToggle.addEventListener("click", () => {
    if (!imageView) return;
    const opening = imageView.hidden;
    imageView.hidden = !opening;
    imageToggle.classList.toggle("is-open", opening);
    if (opening) {
      imageView.scrollIntoView({ behavior: "smooth" });
    }
  });
}

if (driveButton) {
  driveButton.addEventListener("click", async () => {
    if (!currentXlsxBase64) return;

    const originalText = driveButton.textContent;
    driveButton.textContent = '업로드 중...';
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
        driveButton.textContent = '업로드 완료!';
        setTimeout(() => {
          driveButton.textContent = originalText;
          driveButton.disabled = false;
        }, 3000);
      } else {
        const msg = result.message || "업로드에 실패했습니다.";
        driveButton.textContent = `실패: ${msg}`;
        setTimeout(() => {
          driveButton.textContent = originalText;
          driveButton.disabled = false;
        }, 4000);
      }
    } catch (error) {
      driveButton.textContent = '업로드 오류 발생';
      setTimeout(() => {
        driveButton.textContent = originalText;
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
  note.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== target;
  });
  const toggle = note.querySelector(".guide-toggle");
  if (toggle) {
    toggle.dataset.active = target;
    toggle.querySelectorAll(".guide-toggle-btn").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.tab === target);
    });
  }
};

document.querySelectorAll(".guide-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const toggle = btn.closest(".guide-toggle");
    const current = toggle ? toggle.dataset.active || "pc" : "pc";
    switchGuideTab(current === "pc" ? "mobile" : "pc");
  });
});

if (/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
  switchGuideTab("mobile");
}

/* 패널 탭 전환 */
const panelTabs = document.querySelector(".panel-tabs");
if (panelTabs) {
  panelTabs.querySelectorAll(".panel-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      panelTabs.dataset.active = target;
      panelTabs.querySelectorAll(".panel-tab").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.tab === target);
      });
      const panel = panelTabs.closest(".panel");
      panel.querySelectorAll(".panel-content").forEach((content) => {
        content.hidden = content.dataset.panel !== target;
      });
    });
  });
}

/* 통합 진도표 */
const mergeButton = document.getElementById("mergeButton");
const mergeStatus = document.getElementById("mergeStatus");
const mergeStatusText = mergeStatus ? mergeStatus.querySelector(".status-text") : null;
const mergeProgressBar = document.getElementById("mergeProgressBar");
const mergeProgressFill = document.getElementById("mergeProgressFill");
const mergeProgressText = document.getElementById("mergeProgressText");
const mergeStats = document.getElementById("mergeStats");
const mergeWarnings = document.getElementById("mergeWarnings");

const setMergeStatus = (state, message) => {
  if (!mergeStatus) return;
  mergeStatus.hidden = false;
  mergeStatus.dataset.state = state;
  if (mergeStatusText) mergeStatusText.textContent = message;
};

const setMergeProgress = (percent, label) => {
  if (!mergeProgressBar) return;
  mergeProgressBar.hidden = false;
  if (mergeProgressFill) mergeProgressFill.style.width = `${percent}%`;
  if (mergeProgressText) mergeProgressText.textContent = label || `${percent}%`;
};

if (mergeButton) {
  mergeButton.addEventListener("click", async () => {
    mergeButton.disabled = true;
    setMergeStatus("loading", "Drive에서 파일을 가져오는 중...");
    setMergeProgress(0);

    if (mergeStats) mergeStats.hidden = true;
    if (mergeWarnings) {
      mergeWarnings.hidden = true;
      mergeWarnings.textContent = "";
    }

    // 진행 바 애니메이션
    let progressCancelled = false;
    const animateProgress = () => {
      let current = 0;
      const step = () => {
        if (progressCancelled) return;
        current = Math.min(current + 0.5, 90);
        setMergeProgress(Math.round(current), "파일 처리 중...");
        if (current < 90) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    animateProgress();

    try {
      const dualModeEl = document.querySelector('input[name="dualMode"]:checked');
      const selectedDualMode = dualModeEl ? dualModeEl.value : "separate";

      const response = await fetch("/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dual_mode: selectedDualMode }),
      });

      progressCancelled = true;

      const data = await response.json();

      if (!data.success) {
        setMergeProgress(100, "실패");
        setMergeStatus("error", data.message || "통합에 실패했습니다.");
        mergeButton.disabled = false;
        return;
      }

      setMergeProgress(100, "완료!");
      setMergeStatus("success", "통합 완료! 결과를 확인하세요.");

      // 통계 표시
      if (mergeStats && data.stats) {
        const s = data.stats;
        document.getElementById("mergeStatRooms").textContent = `${s.room_count}개 방`;
        document.getElementById("mergeStatBible").textContent = `성경일독 ${s.bible_count}명`;
        document.getElementById("mergeStatNt").textContent = `신약일독 ${s.nt_count}명`;
        const dualStatEl = document.getElementById("mergeStatDual");
        if (dualStatEl) {
          if (s.dual_count) {
            dualStatEl.textContent = `투트랙 ${s.dual_count}명`;
            dualStatEl.hidden = false;
          } else {
            dualStatEl.textContent = "";
            dualStatEl.hidden = true;
          }
        }
        mergeStats.hidden = false;
      }

      // 스킵 경고
      if (mergeWarnings && data.skipped_files && data.skipped_files.length > 0) {
        const lines = data.skipped_files.map(
          (f) => `${f.name}: ${f.reason}`
        );
        mergeWarnings.textContent = `건너뛴 파일: ${lines.join(", ")}`;
        mergeWarnings.hidden = false;
      }

      // 결과 표시 (기존 results 섹션 재사용)
      const { headers, rows } = data.preview;
      const trackMode = "merged";

      // XLSX 다운로드 준비
      const xlsxBinary = atob(data.xlsx_base64);
      const xlsxArray = new Uint8Array(xlsxBinary.length);
      for (let i = 0; i < xlsxBinary.length; i += 1) {
        xlsxArray[i] = xlsxBinary.charCodeAt(i);
      }
      const blob = new Blob([xlsxArray], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      clearObjectUrl();
      currentObjectUrl = URL.createObjectURL(blob);

      showResults(headers, rows, trackMode);
      downloadButton.href = currentObjectUrl;
      downloadButton.download = data.filename || "통합_꿀성경_진도표.xlsx";
      downloadButton.classList.remove("is-disabled");
      downloadButton.setAttribute("aria-disabled", "false");

      if (data.xlsx_base64 && driveButton) {
        currentXlsxBase64 = data.xlsx_base64;
        currentDriveFilename = data.drive_filename || null;
        driveButton.classList.remove("is-disabled");
        driveButton.disabled = false;
      }

      resultsSection.hidden = false;
      resultsSection.classList.add("pop-in");
      resultsSection.scrollIntoView({ behavior: "smooth" });
    } catch (error) {
      progressCancelled = true;
      setMergeProgress(100, "오류");
      const message = error instanceof Error ? error.message : "통합에 실패했습니다.";
      setMergeStatus("error", message);
    } finally {
      mergeButton.disabled = false;
    }
  });
}
