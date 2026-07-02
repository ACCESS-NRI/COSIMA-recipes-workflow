const DATA_URL = "dashboard-data.json";
const STATUS_LABELS = {
  "passed": "Passed",
  "failed": "Failed",
  "timeout": "Timed out",
  "missing-result": "Missing result",
  "incomplete": "Incomplete",
  "submitted": "Submitted",
  "not-run": "Not run",
  "disabled": "Disabled",
};

const state = { data: null, view: "overview", environment: "", filter: "" };

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
}

function statusBadge(status) {
  const key = status || "not-run";
  return `<span class="status status-${esc(key)}">${esc(STATUS_LABELS[key] || key)}</span>`;
}

function selectedStatus(recipe) {
  return recipe.statuses?.[state.environment] || { status: "not-run" };
}

function filteredRecipes() {
  const q = state.filter.trim().toLowerCase();
  const recipes = state.data.recipes || [];
  if (!q) return recipes;
  return recipes.filter(recipe => [recipe.title, recipe.path, recipe.style_label, recipe.name].join(" ").toLowerCase().includes(q));
}

function countStatuses(recipes) {
  return recipes.reduce((counts, recipe) => {
    const status = selectedStatus(recipe).status || "unknown";
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, {});
}

function renderStats(recipes) {
  const counts = countStatuses(recipes);
  const cards = [
    ["Recipes", recipes.length],
    ["Passed", counts.passed || 0],
    ["Failed", counts.failed || 0],
    ["Attention", (counts.timeout || 0) + (counts["missing-result"] || 0) + (counts.incomplete || 0)],
    ["Not run", counts["not-run"] || 0],
  ];
  return `<section class="stats-grid">${cards.map(([label, value]) => `<div class="stat-card"><div class="stat-number">${value}</div><div class="stat-label">${label}</div></div>`).join("")}</section>`;
}

function renderStyleBars(recipes) {
  const counts = recipes.reduce((acc, recipe) => {
    acc[recipe.style_label] = (acc[recipe.style_label] || 0) + 1;
    return acc;
  }, {});
  const total = Math.max(recipes.length, 1);
  return `<section class="panel"><h2 class="view-title">Recipe style mix</h2><div class="style-bars">${Object.entries(counts).map(([label, count]) => `
    <div class="bar-row"><strong>${esc(label)}</strong><div class="bar-track"><div class="bar-fill" style="width:${(count / total) * 100}%"></div></div><span>${count}</span></div>
  `).join("")}</div></section>`;
}

function recipeCard(recipe) {
  const status = selectedStatus(recipe);
  const duration = status.duration_seconds ? `${Math.round(status.duration_seconds / 60)} min` : "—";
  return `<article class="recipe-card style-${esc(recipe.style)}">
    <h3>${esc(recipe.title)}</h3>
    <div class="recipe-path">${esc(recipe.path)}</div>
    <div class="recipe-meta">${statusBadge(status.status)}<span class="chip">${esc(recipe.style_label)}</span><span class="chip">${esc(duration)}</span></div>
    <p class="muted">${esc(recipe.style_description)}</p>
  </article>`;
}

function renderOverview() {
  const recipes = filteredRecipes();
  const examples = recipes.slice(0, 8);
  return `${renderStats(recipes)}${renderStyleBars(recipes)}<section><h2 class="view-title">Recipe snapshot</h2><p class="view-sub">Showing ${examples.length} of ${recipes.length} recipes for ${esc(state.environment)}.</p><div class="overview-grid">${examples.map(recipeCard).join("")}</div></section>`;
}

function renderCards() {
  const recipes = filteredRecipes();
  return `<h2 class="view-title">Recipe cards</h2><p class="view-sub">Per-recipe status and style for ${esc(state.environment)}.</p><div class="overview-grid">${recipes.map(recipeCard).join("")}</div>`;
}

function renderTable() {
  const recipes = filteredRecipes();
  return `<h2 class="view-title">Recipe table</h2><p class="view-sub">Sortable by source manifest order. Filter with the search box above.</p><table class="recipe-table"><thead><tr><th>Recipe</th><th class="hide-small">Path</th><th>Style</th><th>Status</th><th class="hide-small">Duration</th><th class="hide-small">Log</th></tr></thead><tbody>${recipes.map(recipe => {
    const status = selectedStatus(recipe);
    const duration = status.duration_seconds ? `${status.duration_seconds}s` : "—";
    const log = status.log_path ? `<code>${esc(status.log_path)}</code>` : "—";
    return `<tr><td><strong>${esc(recipe.title)}</strong></td><td class="hide-small"><code>${esc(recipe.path)}</code></td><td>${esc(recipe.style_label)}</td><td>${statusBadge(status.status)}</td><td class="hide-small">${esc(duration)}</td><td class="hide-small">${log}</td></tr>`;
  }).join("")}</tbody></table>`;
}

function renderDetail() {
  const runs = state.data.runs || [];
  const assumptions = state.data.assumptions || [];
  const runHtml = runs.length ? runs.map(run => `<div class="detail-item"><strong>${esc(run.conda_module)}</strong> ${statusBadge(run.status)}<div class="detail-grid"><span>Expected: ${esc(run.expected_count ?? "—")}</span><span>Completed: ${esc(run.completed_count ?? "—")}</span><span>Passed: ${esc(run.passed_count ?? "—")}</span><span>Failed: ${esc(run.failed_count ?? "—")}</span><span>PBS: <code>${esc(run.pbs_job_id || "—")}</code></span><span>Generated: ${esc(run.generated_at || "—")}</span></div></div>`).join("") : `<div class="detail-item muted">No all-recipes summary JSON has been imported yet. All manifest recipes are shown as not run until a workflow summary is available. Bleak, but accurate.</div>`;
  return `<section class="panel"><h2 class="view-title">Run detail</h2><div class="detail-list">${runHtml}</div></section><section class="panel"><h2 class="view-title">Assumptions</h2><ul>${assumptions.map(item => `<li>${esc(item)}</li>`).join("")}</ul></section>`;
}

function render() {
  if (!state.data) return;
  const app = document.getElementById("app");
  app.innerHTML = ({ overview: renderOverview, cards: renderCards, table: renderTable, detail: renderDetail }[state.view] || renderOverview)();
  document.getElementById("meta").textContent = `Generated ${new Date(state.data.generated_at).toLocaleString()} · ${state.data.repository}`;
}

function initControls() {
  const select = document.getElementById("environment-select");
  select.innerHTML = state.data.environments.map(env => `<option value="${esc(env)}">${esc(env)}</option>`).join("");
  select.value = state.environment;
  select.addEventListener("change", event => { state.environment = event.target.value; render(); });
  document.getElementById("recipe-filter").addEventListener("input", event => { state.filter = event.target.value; render(); });
  document.querySelectorAll(".nav-btn").forEach(button => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      document.querySelectorAll(".nav-btn").forEach(btn => btn.classList.toggle("active", btn === button));
      render();
    });
  });
}

async function loadDashboard() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    state.environment = state.data.default_environment || state.data.environments?.[0] || "conda/analysis3";
    initControls();
    render();
  } catch (error) {
    document.getElementById("app").innerHTML = `<section class="panel"><h2 class="view-title">Unable to load dashboard data</h2><p>${esc(error.message)}</p></section>`;
  }
}

loadDashboard();
