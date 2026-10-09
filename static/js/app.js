/**
 * Feels - Main App Controller
 * Manages live processing stages, local Qwen AI inference,
 * SerpAPI place curation, smart rotation refreshes, and quotas.
 */


document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements - Nav & Status
  const navDisconnectBtn = document.getElementById("nav-disconnect-btn");
  const navConnectBtn = document.getElementById("nav-connect-btn");
  const modelText = document.getElementById("model-text");
  const modelStatusDot = document.getElementById("model-status-dot");
  const quotaBadgeText = document.getElementById("quota-badge-text");

  // DOM Elements - Auth Prompt Callout
  const authPromptCard = document.getElementById("auth-prompt-card");
  const promptConnectBtn = document.getElementById("prompt-connect-btn");
  const promptDemoBtn = document.getElementById("prompt-demo-btn");

  // DOM Elements - Processing Steps
  const analysisProgress = document.getElementById("analysis-progress");
  const progressStatusBadge = document.getElementById("progress-status-badge");
  const progressHeaderTitle = document.getElementById("progress-header-title");
  const progressHeaderDesc = document.getElementById("progress-header-desc");
  const step1 = document.getElementById("step-1");
  const step2 = document.getElementById("step-2");
  const step3 = document.getElementById("step-3");
  const step4 = document.getElementById("step-4");

  // DOM Elements - Results Container
  const resultsSection = document.getElementById("results-section");
  const tracksContainer = document.getElementById("tracks-container");
  const tracksCacheBadge = document.getElementById("tracks-cache-badge");
  const energyLevelBadge = document.getElementById("energy-level-badge");
  const moodTitleText = document.getElementById("mood-title-text");
  const moodSummaryText = document.getElementById("mood-summary-text");
  const moodQualitiesRow = document.getElementById("mood-qualities-row");
  const moodReasoningText = document.getElementById("mood-reasoning-text");
  const placesGrid = document.getElementById("places-grid");

  // DOM Elements - Floating Control Bar
  const refreshBtn = document.getElementById("refresh-btn");
  const disconnectBtn = document.getElementById("disconnect-btn");
  const quotaMeterFill = document.getElementById("quota-meter-fill");
  const quotaBottomText = document.getElementById("quota-bottom-text");

  // DOM Elements - Errors & Modals
  const errorCard = document.getElementById("error-card");
  const errorTitle = document.getElementById("error-title");
  const errorMessage = document.getElementById("error-message");
  const errorActionBtn = document.getElementById("error-action-btn");
  const errorDemoBtn = document.getElementById("error-demo-btn");
  const setupModal = document.getElementById("setup-modal");
  const modalSampleBtn = document.getElementById("modal-sample-btn");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const disconnectModal = document.getElementById("disconnect-modal");
  const confirmDisconnectBtn = document.getElementById("confirm-disconnect-btn");
  const cancelDisconnectBtn = document.getElementById("cancel-disconnect-btn");

  // State
  let currentAuthState = { authenticated: false };
  let currentQuotaState = { remaining_count: 15, daily_limit: 15 };
  let isRequestPending = false;

  // Initialize
  checkSystemHealth();
  handleInitialRouting();

  // --- Health Check ---
  async function checkSystemHealth() {
    try {
      const resp = await fetch("/api/health");
      if (resp.ok) {
        const data = await resp.json();
        if (data.ollama_connected) {
          if (modelText) modelText.textContent = `⚡ ${data.ollama_model} (Local)`;
          if (modelStatusDot) modelStatusDot.style.backgroundColor = "#10B981";
        } else {
          if (modelText) modelText.textContent = `⚠️ Ollama Offline`;
          if (modelStatusDot) modelStatusDot.style.backgroundColor = "#F59E0B";
        }
      }
    } catch (e) {
      console.warn("Health check error:", e);
    }
  }

  // --- Initial Routing & Parameter Handling ---
  async function handleInitialRouting() {
    const urlParams = new URLSearchParams(window.location.search);
    const isDemo = urlParams.get("demo") === "true";
    const isConnected = urlParams.get("connected") === "true";

    // Clean up query string from address bar without reloading
    if (isConnected || isDemo) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Check authentication status
    try {
      const resp = await fetch("/auth/status");
      if (resp.ok) {
        const data = await resp.json();
        currentAuthState = data;
        updateQuotaDisplay(data.quota);

        if (data.authenticated) {
          showAuthenticatedNav();
          loadRecommendations();
        } else if (isDemo) {
          showDemoNav();
          runSampleDemo();
        } else {
          showUnauthenticatedState();
        }
      } else {
        if (isDemo) runSampleDemo();
        else showUnauthenticatedState();
      }
    } catch (err) {
      console.warn("Initial routing auth check failed:", err);
      if (isDemo) runSampleDemo();
      else showUnauthenticatedState();
    }
  }

  function showAuthenticatedNav() {
    if (navDisconnectBtn) {
      navDisconnectBtn.style.display = "inline-flex";
      navDisconnectBtn.onclick = () => showDisconnectModal();
    }
    if (navConnectBtn) navConnectBtn.style.display = "none";
    if (authPromptCard) authPromptCard.style.display = "none";
  }

  function showDemoNav() {
    if (navConnectBtn) {
      navConnectBtn.style.display = "inline-flex";
      navConnectBtn.textContent = "Connect Real Spotify";
      navConnectBtn.onclick = () => window.location.href = "/auth/login";
    }
    if (navDisconnectBtn) navDisconnectBtn.style.display = "none";
    if (authPromptCard) authPromptCard.style.display = "none";
  }

  function showUnauthenticatedState() {
    if (navConnectBtn) {
      navConnectBtn.style.display = "inline-flex";
      navConnectBtn.textContent = "Connect Spotify";
      navConnectBtn.onclick = () => window.location.href = "/auth/login";
    }
    if (navDisconnectBtn) navDisconnectBtn.style.display = "none";
    if (analysisProgress) analysisProgress.style.display = "none";
    if (resultsSection) resultsSection.style.display = "none";
    if (authPromptCard) authPromptCard.style.display = "block";
  }

  // --- Load Real Recommendations ---
  async function loadRecommendations() {
    if (isRequestPending) return;
    isRequestPending = true;

    hideError();
    if (authPromptCard) authPromptCard.style.display = "none";
    if (resultsSection) resultsSection.style.display = "none";

    showProgressStep(1, "Reading Spotify History", "Fetching your 10 most recently played tracks from Spotify Web API...");

    const t1 = setTimeout(() => {
      showProgressStep(2, "Local Qwen 2.5 Inference", "Synthesizing tempo, BPM dynamics, and emotional atmosphere locally via Ollama...");
    }, 700);

    const t2 = setTimeout(() => {
      showProgressStep(3, "SerpAPI Pune Discovery", "Searching real trails, lake sanctuaries, and viewpoints in Pune matching the mood...");
    }, 1800);

    try {
      const resp = await fetch("/api/recommendations");
      clearTimeout(t1);
      clearTimeout(t2);

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        if (resp.status === 401) {
          showSetupModal();
          hideProgress();
          showUnauthenticatedState();
          isRequestPending = false;
          return;
        }
        throw new Error(errData.detail || `Server error (${resp.status})`);
      }

      showProgressStep(4, "Curating Grounded Spots", "Applying deduplication and writing non-hallucinated place explanations...");
      const data = await resp.json();

      setTimeout(() => {
        renderResults(data);
        hideProgress();
        isRequestPending = false;
      }, 500);

    } catch (err) {
      clearTimeout(t1);
      clearTimeout(t2);
      console.error("Load recommendations failed:", err);
      hideProgress();
      showError("Could Not Generate Recommendations", err.message);
      isRequestPending = false;
    }
  }

  // --- Run Preview Demo ---
  async function runSampleDemo() {
    if (isRequestPending) return;
    isRequestPending = true;

    hideSetupModal();
    hideError();
    if (authPromptCard) authPromptCard.style.display = "none";
    if (resultsSection) resultsSection.style.display = "none";

    showProgressStep(1, "Loading Sample Session", "Initializing 10 representative test tracks (Eminem, The 1975, Woodkid, M83)...");

    const t1 = setTimeout(() => {
      showProgressStep(2, "Local Qwen 2.5 Inference", "Synthesizing tempo, BPM dynamics, and emotional atmosphere locally via Ollama...");
    }, 600);

    const t2 = setTimeout(() => {
      showProgressStep(3, "SerpAPI Pune Discovery", "Searching real trails, lake sanctuaries, and viewpoints in Pune matching the mood...");
    }, 1600);

    try {
      const resp = await fetch("/api/preview-demo", { method: "POST" });
      clearTimeout(t1);
      clearTimeout(t2);

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || "Demo failed");
      }

      showProgressStep(4, "Curating Grounded Spots", "Applying deduplication and writing non-hallucinated place explanations...");
      const data = await resp.json();

      setTimeout(() => {
        renderResults(data);
        hideProgress();
        isRequestPending = false;
      }, 500);

    } catch (err) {
      clearTimeout(t1);
      clearTimeout(t2);
      console.error("Sample demo failed:", err);
      hideProgress();
      showError("Demo Execution Notice", err.message);
      isRequestPending = false;
    }
  }

  // --- Refresh Recommendations ---
  async function refreshRecommendations() {
    if (isRequestPending) return;
    if (currentQuotaState.remaining_count <= 0) {
      showError(
        "Daily Refresh Limit Reached",
        `You have used all ${currentQuotaState.daily_limit} refreshes for today. Your quota resets at midnight (${currentQuotaState.resets_at || 'Asia/Kolkata'}). Time to close the screen and explore Pune!`
      );
      return;
    }

    isRequestPending = true;
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = `<span>Curating new spots...</span>`;

    try {
      const resp = await fetch("/api/refresh", { method: "POST" });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        if (resp.status === 429) {
          showError("Refresh Limit Exhausted", errData.detail || "15 / 15 daily refreshes used.");
        } else {
          throw new Error(errData.detail || "Refresh failed");
        }
        return;
      }

      const data = await resp.json();
      renderResults(data);
    } catch (err) {
      console.error("Refresh error:", err);
      showError("Refresh Failed", err.message);
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Discover Different Places`;
      isRequestPending = false;
    }
  }

  // --- Render Results ---
  function renderResults(data) {
    updateQuotaDisplay(data.quota);

    // 1. Render Tracks
    if (tracksContainer) {
      tracksContainer.innerHTML = "";
      if (data.tracks && data.tracks.length > 0) {
        data.tracks.forEach(t => {
          const card = document.createElement("div");
          card.className = "track-cassette-card";
          const art = t.album_art_url || "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=300&q=80";
          card.innerHTML = `
            <div class="track-cover-frame">
              <img src="${art}" alt="${escapeHtml(t.name)}" loading="lazy">
            </div>
            <div class="track-name" title="${escapeHtml(t.name)}">${escapeHtml(t.name)}</div>
            <div class="track-artists" title="${escapeHtml(t.artists.join(', '))}">${escapeHtml(t.artists.join(', '))}</div>
          `;
          tracksContainer.appendChild(card);
        });
        if (tracksCacheBadge) {
          tracksCacheBadge.textContent = data.is_cached_listening ? "Cached for Today" : "Freshly Fetched";
        }
      }
    }

    // 2. Render AI Mood Profile
    if (data.mood_profile) {
      const mood = data.mood_profile;
      if (moodTitleText) moodTitleText.textContent = mood.mood_title;
      if (moodSummaryText) moodSummaryText.textContent = mood.mood_summary;

      if (energyLevelBadge) {
        energyLevelBadge.textContent = `${mood.energy_level.toUpperCase()} ENERGY`;
        if (mood.energy_level.toLowerCase() === "high") {
          energyLevelBadge.className = "pill-badge orange";
        } else if (mood.energy_level.toLowerCase() === "low") {
          energyLevelBadge.className = "pill-badge soft-green";
        } else {
          energyLevelBadge.className = "pill-badge active-lime";
        }
      }

      // Render Qualities
      if (moodQualitiesRow) {
        moodQualitiesRow.innerHTML = "";
        (mood.dominant_qualities || []).forEach(q => {
          const tag = document.createElement("div");
          tag.className = "quality-tag";
          tag.textContent = q;
          moodQualitiesRow.appendChild(tag);
        });

        // Activities
        (mood.suitable_outdoor_activities || []).forEach(act => {
          const tag = document.createElement("div");
          tag.className = "quality-tag";
          tag.style.backgroundColor = "var(--accent-lime)";
          tag.textContent = `📍 ${act}`;
          moodQualitiesRow.appendChild(tag);
        });
      }

      // Grounded reasoning
      if (moodReasoningText) {
        moodReasoningText.innerHTML = `
          <strong>AI Synthesis (Local Qwen 2.5 Coder 7B):</strong><br>
          ${escapeHtml(mood.reasoning)}
        `;
      }
    }

    // 3. Render Curated Places
    if (placesGrid) {
      placesGrid.innerHTML = "";
      if (data.places && data.places.length > 0) {
        data.places.forEach(p => {
          const card = document.createElement("div");
          card.className = "place-card";
          const photo = p.photo_url || "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80";
          const sourceLabel = p.source === "serpapi" ? "Live SerpAPI Discovery" : "Verified Pune Index";

          card.innerHTML = `
            <div class="place-photo-frame">
              <span class="place-source-pill">${sourceLabel}</span>
              <img src="${photo}" alt="${escapeHtml(p.title)}" loading="lazy">
            </div>
            <div class="place-content">
              <div class="place-category">${escapeHtml(p.category)}</div>
              <h3 class="place-title">${escapeHtml(p.title)}</h3>
              <div class="place-neighborhood">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                ${escapeHtml(p.neighborhood)}
              </div>
              <div class="place-why-box">
                <strong>Why it suits your soundtrack</strong>
                ${escapeHtml(p.why_it_fits)}
              </div>
              <div class="place-footer">
                <div class="place-rating">
                  ${p.rating ? `★ ${p.rating} <span style="font-size:0.75rem; color:var(--text-muted);">(${p.reviews_count || 'Verified'})</span>` : '🌿 Scenic Spot'}
                </div>
                <a href="${p.directions_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-primary">
                  Directions ↗
                </a>
              </div>
            </div>
          `;
          placesGrid.appendChild(card);
        });
      }
    }

    // Show Results Section
    if (resultsSection) {
      resultsSection.style.display = "block";
      resultsSection.scrollIntoView({ behavior: "smooth" });
    }
  }

  // --- Quota Display ---
  function updateQuotaDisplay(quota) {
    if (!quota) return;
    currentQuotaState = quota;
    const limit = quota.daily_limit;
    const remaining = quota.remaining_count;

    if (quotaBadgeText) quotaBadgeText.textContent = `${remaining} / ${limit} Refreshes Left`;
    if (quotaBottomText) quotaBottomText.textContent = `${remaining} / ${limit} Refreshes Remaining Today (${quota.timezone || 'Asia/Kolkata'})`;

    if (quotaMeterFill) {
      const percentage = Math.max(0, Math.min(100, (remaining / limit) * 100));
      quotaMeterFill.style.width = `${percentage}%`;
      if (remaining <= 3) {
        quotaMeterFill.style.backgroundColor = "var(--accent-orange)";
      } else {
        quotaMeterFill.style.backgroundColor = "var(--accent-lime)";
      }
    }

    if (refreshBtn) {
      if (remaining <= 0) {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Daily Refresh Limit Reached (15/15)";
      } else {
        refreshBtn.disabled = false;
      }
    }
  }

  // --- Progress Steps ---
  function showProgressStep(activeStep, title, desc) {
    if (analysisProgress) {
      analysisProgress.style.display = "block";
      analysisProgress.classList.add("active");
    }
    if (progressHeaderTitle && title) progressHeaderTitle.textContent = title;
    if (progressHeaderDesc && desc) progressHeaderDesc.textContent = desc;

    [step1, step2, step3, step4].forEach((step, idx) => {
      if (!step) return;
      const stepNum = idx + 1;
      step.classList.remove("active", "completed");
      if (stepNum < activeStep) {
        step.classList.add("completed");
      } else if (stepNum === activeStep) {
        step.classList.add("active");
      }
    });
  }

  function hideProgress() {
    if (analysisProgress) {
      analysisProgress.classList.remove("active");
      analysisProgress.style.display = "none";
    }
  }

  // --- Error Handling ---
  function showError(title, msg) {
    if (errorTitle) errorTitle.textContent = title;
    if (errorMessage) errorMessage.textContent = msg;
    if (errorCard) {
      errorCard.style.display = "block";
      errorCard.scrollIntoView({ behavior: "smooth" });
    }
  }

  function hideError() {
    if (errorCard) errorCard.style.display = "none";
  }

  // --- Modals ---
  function showSetupModal() {
    if (setupModal) setupModal.classList.add("active");
  }

  function hideSetupModal() {
    if (setupModal) setupModal.classList.remove("active");
  }

  function showDisconnectModal() {
    if (disconnectModal) disconnectModal.classList.add("active");
  }

  function hideDisconnectModal() {
    if (disconnectModal) disconnectModal.classList.remove("active");
  }

  async function handleDisconnect() {
    try {
      const resp = await fetch("/auth/disconnect", { method: "POST" });
      if (resp.ok) {
        hideDisconnectModal();
        window.location.href = "/";
      }
    } catch (e) {
      console.error("Disconnect error:", e);
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Event Listeners
  if (promptDemoBtn) promptDemoBtn.addEventListener("click", runSampleDemo);
  if (modalSampleBtn) modalSampleBtn.addEventListener("click", runSampleDemo);
  if (modalCloseBtn) modalCloseBtn.addEventListener("click", hideSetupModal);
  if (refreshBtn) refreshBtn.addEventListener("click", refreshRecommendations);
  if (disconnectBtn) disconnectBtn.addEventListener("click", showDisconnectModal);
  if (confirmDisconnectBtn) confirmDisconnectBtn.addEventListener("click", handleDisconnect);
  if (cancelDisconnectBtn) cancelDisconnectBtn.addEventListener("click", hideDisconnectModal);
  if (errorActionBtn) {
    errorActionBtn.addEventListener("click", () => {
      hideError();
      loadRecommendations();
    });
  }
  if (errorDemoBtn) {
    errorDemoBtn.addEventListener("click", () => {
      hideError();
      runSampleDemo();
    });
  }
});
