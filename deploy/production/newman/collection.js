"use strict";

const fs = require("node:fs");
const path = require("node:path");
const YAML = require("yaml");

const NAMES = {
  public: "Superstore Public",
  staff: "Superstore Staff Journey",
};

function readYaml(file) {
  return YAML.parse(fs.readFileSync(file, "utf8"));
}

function loadCollection(root, kind) {
  const name = NAMES[kind];
  if (!name) throw new Error("Collection must be public or staff");

  const folder = path.join(root, "collections", name);
  const definition = readYaml(path.join(folder, ".resources", "definition.yaml"));
  if (definition.$kind !== "collection" || definition.name !== name) {
    throw new Error(`Unexpected collection definition: ${name}`);
  }

  const items = fs.readdirSync(folder)
    .filter((file) => file.endsWith(".request.yaml"))
    .map((file) => {
      const source = readYaml(path.join(folder, file));
      source.name ||= file.slice(0, -".request.yaml".length);
      return source;
    })
    .sort((a, b) => a.order - b.order);

  if (items.length === 0) throw new Error(`${name}: no requests found`);
  const orders = items.map(({ order }) => order);
  if (new Set(orders).size !== orders.length) {
    throw new Error(`${name}: request order values must be unique`);
  }
  const loginOrder = items.find((item) => item.url.endsWith("/staff/login"))?.order;
  const logoutOrder = items.find((item) => item.url.endsWith("/staff/logout"))?.order;
  if (kind === "staff" && !(loginOrder < logoutOrder)) {
    throw new Error(`${name}: login must precede logout`);
  }

  return {
    info: {
      name,
      schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    item: items.map((source) => {
      if (source.$kind !== "http-request" || !source.name || !source.url ||
          !Number.isFinite(source.order)) {
        throw new Error(`Invalid request in ${name}`);
      }

      const request = {
        method: source.method,
        url: source.url,
        header: Object.entries(source.headers || {})
          .filter(([key]) => key.trim())
          .map(([key, value]) => ({ key, value: String(value) })),
      };

      // Carry only the token created by this run; never reuse a browser cookie jar.
      if (kind === "staff" && source.order > loginOrder && source.order <= logoutOrder) {
        request.header.push({ key: "Cookie", value: "superstore_staff={{staff_session}}" });
      }

      if (source.body) {
        if (source.body.type !== "json") throw new Error(`Unsupported body: ${source.name}`);
        request.body = {
          mode: "raw",
          raw: source.body.content,
          options: { raw: { language: "json" } },
        };
      }

      const event = (source.scripts || []).map((script) => {
        const listen = {
          beforeRequest: "prerequest",
          afterResponse: "test",
        }[script.type];
        if (!listen) throw new Error(`Unsupported script: ${source.name}`);
        return {
          listen,
          script: { type: "text/javascript", exec: script.code.split("\n") },
        };
      });

      return {
        name: source.name,
        request,
        event,
        ...((kind === "staff" || source.settings?.disableCookies === true)
          ? { protocolProfileBehavior: { disableCookies: true } }
          : {}),
      };
    }),
  };
}

function loadEnvironment(root) {
  const file = path.join(root, "environments", "Superstore https.environment.yaml");
  const source = readYaml(file);
  return Object.fromEntries(source.values.map(({ key, value }) => [key, String(value)]));
}

module.exports = { loadCollection, loadEnvironment };
