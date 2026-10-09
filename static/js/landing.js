/**
 * Feels - Landing Page Controller
 * Checks local health status and authentication, updates CTA buttons.
 */

document.addEventListener("DOMContentLoaded", () => {
  const modelText = document.getElementById("model-text");
  const modelStatusDot = document.getElementById("model-status-dot");
  const navAuthBtn = document.getElementById("nav-auth-btn");
  const heroPrimaryBtn = document.getElementById("hero-primary-btn");
  const heroDemoBtn = document.getElementById("hero-demo-btn");
  const setupModal = document.getElementById("setup-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalSampleBtn = document.getElementById("modal-sample-btn");

  // Check health and auth status
  checkHealth();
  checkAuth();

  async function checkHealth() {
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

  async function checkAuth() {
    try {
      const resp = await fetch("/auth/status");
      if (resp.ok) {
        const data = await resp.json();
        if (data.authenticated) {
          // If already logged in, primary action launches the app
          if (navAuthBtn) {
            navAuthBtn.textContent = "Open App →";
            navAuthBtn.onclick = () => window.location.href = "/app";
          }
          if (heroPrimaryBtn) {
            heroPrimaryBtn.innerHTML = `Open Your Soundtrack →`;
            heroPrimaryBtn.onclick = () => window.location.href = "/app";
          }
        } else {
          if (navAuthBtn) {
            navAuthBtn.textContent = "Connect Spotify";
            navAuthBtn.onclick = () => window.location.href = "/auth/login";
          }
          if (heroPrimaryBtn) {
            heroPrimaryBtn.onclick = () => window.location.href = "/auth/login";
          }
        }
      }
    } catch (e) {
      console.warn("Auth check error:", e);
    }
  }

  if (heroDemoBtn) {
    heroDemoBtn.onclick = () => window.location.href = "/app?demo=true";
  }

  // Handle URL errors
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("auth_error")) {
    const err = urlParams.get("auth_error");
    if (setupModal && err.includes("not configured")) {
      setupModal.classList.add("active");
    } else {
      alert(`Spotify authentication notice: ${err}`);
    }
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  if (modalCloseBtn && setupModal) {
    modalCloseBtn.onclick = () => setupModal.classList.remove("active");
  }
  if (modalSampleBtn) {
    modalSampleBtn.onclick = () => window.location.href = "/app?demo=true";
  }
});
