"use strict";

const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { loadCollection } = require("../collection");

const root = path.resolve(__dirname, "../../../../postman");
const metrics = ["kpi", "revenue-trend", "by-category", "by-region", "top-products"];
const rows = {
  kpi: { REVENUE: 1, GROSS_PROFIT: 1, ORDERS: 1, AVG_ORDER_VALUE: 1, MARGIN_PCT: 1 },
  "revenue-trend": { MONTH_DATE_KEY: 20230101, REVENUE: 1, COGS: 1, GROSS_PROFIT: 1 },
  "by-category": { CATEGORY: "Test", REVENUE: 1, GROSS_PROFIT: 1 },
  "by-region": { REGION: "Test", REVENUE: 1, GROSS_PROFIT: 1 },
  "top-products": { PRODUCT_ID: 1, PRODUCT_NAME: "Test", CATEGORY: "Test", REVENUE: 1, GROSS_PROFIT: 1, QUANTITY: 1 },
};

function run(kind, origin, metricsDir) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [path.resolve(__dirname, "../run.js"), kind], {
      env: {
        ...process.env,
        API_ORIGIN: origin,
        FRONTEND_ORIGIN: origin,
        MONITOR_EMAIL_SALES: "monitor@example.test",
        MONITOR_PASSWORD_SALES: "test-password-only",
        METRICS_DIR: metricsDir,
      },
    });
    let output = "";
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.stderr.on("data", (chunk) => { output += chunk; });
    child.on("close", (code) => resolve({ code, output }));
  });
}

test("YAML collections run offline and publish secret-free metrics", async () => {
  assert.equal(loadCollection(root, "public").item.length, 5);
  assert.equal(loadCollection(root, "staff").item.length, 13);

  let kpiCalls = 0;
  const server = http.createServer((request, response) => {
    const pathname = new URL(request.url, "http://localhost").pathname;
    const send = (code, body, headers = {}) => {
      response.writeHead(code, { "Content-Type": "application/json", ...headers });
      response.end(typeof body === "string" ? body : JSON.stringify(body));
    };

    if (pathname === "/api/health/live") return send(200, { status: "ok", release: "0".repeat(40) });
    if (pathname === "/api/health") return send(200, { status: "ok", api: "up" });
    if (pathname === "/login") return send(200, "Staff sign in");
    if (pathname === "/api/health/ready" || pathname === "/metrics") return send(404, {});
    if (pathname === "/api/internal/staff/login") {
      return send(200, { role: "sales", metrics }, {
        "Set-Cookie": "superstore_staff=test-token; HttpOnly; Secure; SameSite=Lax; Path=/",
      });
    }
    if (pathname === "/api/internal/staff/logout") {
      return send(200, {}, { "Set-Cookie": "superstore_staff=; Max-Age=0; Path=/" });
    }
    if (pathname === "/api/internal/staff/me") {
      return request.headers.cookie === "superstore_staff=test-token"
        ? send(200, { role: "sales" }) : send(401, {});
    }
    if (pathname === "/api/internal/dashboard") return send(200, { metrics });
    if (pathname === "/dashboard") return send(200, "Dashboard kinh doanh");
    const metric = pathname.split("/").pop();
    if (rows[metric]) {
      if (metric === "kpi") kpiCalls += 1;
      return send(200, { metric, data: [rows[metric]], row_count: 1, cached: kpiCalls > 1 });
    }
    return send(404, {});
  });

  const metricsDir = fs.mkdtempSync(path.join(os.tmpdir(), "superstore-newman-test-"));
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;

  try {
    for (const kind of ["public", "staff"]) {
      const result = await run(kind, origin, metricsDir);
      assert.equal(result.code, 0, result.output);
      const promFile = path.join(metricsDir, `newman-${kind}-manual.prom`);
      const stateFile = path.join(metricsDir, `newman-${kind}-manual.state.json`);
      const text = fs.readFileSync(promFile, "utf8");
      assert.match(text, new RegExp(`newman_last_run_success\\{collection="${kind}",mode="manual"\\} 1`));
      assert.doesNotMatch(text, /test-password-only|test-token/);
      assert.equal(fs.statSync(promFile).mode & 0o777, 0o644);
      assert.equal(fs.statSync(stateFile).mode & 0o777, 0o600);
    }
  } finally {
    server.close();
    fs.rmSync(metricsDir, { recursive: true, force: true });
  }
});
