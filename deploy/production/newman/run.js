"use strict";

const fs = require("node:fs");
const path = require("node:path");
const newman = require("newman");
const { loadCollection, loadEnvironment } = require("./collection");

const kind = process.argv[2];
if (!(["public", "staff"].includes(kind))) {
  console.error("Usage: node run.js public|staff");
  process.exit(2);
}
const mode = process.env.NEWMAN_RUN_MODE || "manual";
if (!(["manual", "timer"].includes(mode))) throw new Error("Invalid run mode");

const postmanRoot = process.env.POSTMAN_ROOT || path.resolve(__dirname, "../../../postman");
const metricsDir = process.env.METRICS_DIR || path.resolve(__dirname, "metrics");
const environment = loadEnvironment(postmanRoot);
const collection = loadCollection(postmanRoot, kind);

function origin(key, fallback) {
  const value = process.env[key] || fallback;
  const parsed = new URL(value);
  if (parsed.protocol !== "https:" &&
      !(parsed.protocol === "http:" && ["localhost", "127.0.0.1"].includes(parsed.hostname))) {
    throw new Error(`${key} must use HTTPS, or HTTP on localhost for testing`);
  }
  return parsed.origin;
}

const variables = {
  ...environment,
  frontend_origin: origin("FRONTEND_ORIGIN", environment.frontend_origin),
  api_origin: origin("API_ORIGIN", environment.api_origin),
};

if (kind === "staff") {
  variables.monitor_email_sales = process.env.MONITOR_EMAIL_SALES || "";
  variables.monitor_password_sales = process.env.MONITOR_PASSWORD_SALES || "";
  if (!variables.monitor_email_sales || !variables.monitor_password_sales) {
    throw new Error("MONITOR_EMAIL_SALES and MONITOR_PASSWORD_SALES are required");
  }
  if (variables.monitor_email_sales.includes("YOUR_ALLOWED_DOMAIN") ||
      variables.monitor_password_sales === "CHANGE_ME") {
    throw new Error("Replace the example monitoring credentials before running");
  }
}

function atomicWrite(file, contents, mode = 0o600) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, contents, { mode });
  fs.chmodSync(temporary, mode);
  fs.renameSync(temporary, file);
}

function label(value) {
  return JSON.stringify(String(value));
}

function writeMetrics(result) {
  const stateFile = path.join(metricsDir, `newman-${kind}-${mode}.state.json`);
  const metricsFile = path.join(metricsDir, `newman-${kind}-${mode}.prom`);
  let state = { runs: 0, failed: 0, assertionsFailed: 0 };
  if (fs.existsSync(stateFile)) {
    state = JSON.parse(fs.readFileSync(stateFile, "utf8"));
  }
  state.runs += 1;
  state.failed += Number(!result.ok);
  state.assertionsFailed += result.assertionsFailed;

  const tags = `{collection=${label(kind)},mode=${label(mode)}}`;
  const lines = [
    "# HELP newman_last_run_success 1 if the most recent collection run passed.",
    "# TYPE newman_last_run_success gauge",
    `newman_last_run_success${tags} ${Number(result.ok)}`,
    "# HELP newman_last_run_timestamp_seconds Unix time of the most recent completed run.",
    "# TYPE newman_last_run_timestamp_seconds gauge",
    `newman_last_run_timestamp_seconds${tags} ${result.timestamp}`,
    "# HELP newman_last_run_duration_seconds Duration of the most recent collection run.",
    "# TYPE newman_last_run_duration_seconds gauge",
    `newman_last_run_duration_seconds${tags} ${result.durationSeconds}`,
    "# HELP newman_last_run_requests Number of requests in the most recent run.",
    "# TYPE newman_last_run_requests gauge",
    `newman_last_run_requests${tags} ${result.requests.length}`,
    "# HELP newman_last_run_assertions_failed Number of failed assertions in the most recent run.",
    "# TYPE newman_last_run_assertions_failed gauge",
    `newman_last_run_assertions_failed${tags} ${result.assertionsFailed}`,
    "# HELP newman_runs_total Completed collection runs.",
    "# TYPE newman_runs_total counter",
    `newman_runs_total${tags} ${state.runs}`,
    "# HELP newman_runs_failed_total Failed collection runs.",
    "# TYPE newman_runs_failed_total counter",
    `newman_runs_failed_total${tags} ${state.failed}`,
    "# HELP newman_assertions_failed_total Failed assertions across completed runs.",
    "# TYPE newman_assertions_failed_total counter",
    `newman_assertions_failed_total${tags} ${state.assertionsFailed}`,
    "# HELP newman_request_last_http_status HTTP status from each request in the most recent run.",
    "# TYPE newman_request_last_http_status gauge",
    "# HELP newman_request_last_duration_seconds Duration of each request in the most recent run.",
    "# TYPE newman_request_last_duration_seconds gauge",
  ];

  result.requests.forEach((request, index) => {
    const requestTags = `{collection=${label(kind)},mode=${label(mode)},step=${label(index + 1)},request=${label(request.name)}}`;
    lines.push(`newman_request_last_http_status${requestTags} ${request.status}`);
    lines.push(`newman_request_last_duration_seconds${requestTags} ${request.durationSeconds}`);
  });

  atomicWrite(stateFile, `${JSON.stringify(state)}\n`);
  atomicWrite(metricsFile, `${lines.join("\n")}\n`, 0o644);
}

const started = Date.now();
const requests = [];
let assertionsFailed = 0;

newman.run({
  collection,
  envVar: Object.entries(variables).map(([key, value]) => ({ key, value })),
  reporters: [],
  timeoutRequest: 30000,
  insecure: false,
}, (error, summary) => {
  const failures = summary?.run?.failures || [];
  const ok = !error && failures.length === 0 &&
    requests.length === collection.item.length &&
    requests.every((request) => request.status > 0);
  writeMetrics({
    ok,
    timestamp: Math.floor(Date.now() / 1000),
    durationSeconds: (Date.now() - started) / 1000,
    requests,
    assertionsFailed: Math.max(assertionsFailed, failures.length),
  });
  console.log(`${kind}: ${ok ? "PASS" : "FAIL"}; requests=${requests.length}; failed_assertions=${failures.length}`);
  for (const name of new Set(failures.map((failure) => failure.source?.name).filter(Boolean))) {
    console.error(`Failed check: ${name}`);
  }
  process.exitCode = ok ? 0 : 1;
})
  .on("request", (error, args) => {
    requests.push({
      name: args.item?.name || "unknown",
      status: args.response?.code || 0,
      durationSeconds: (args.response?.responseTime || 0) / 1000,
    });
    if (error) console.error(`Request failed: ${args.item?.name || "unknown"}`);
  })
  .on("assertion", (error) => {
    if (error) assertionsFailed += 1;
  });
