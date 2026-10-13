import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const [mode, projectRoot] = process.argv.slice(2);
const requireFromProject = createRequire(path.join(projectRoot, "package.json"));
const modulePath = requireFromProject.resolve(mode);
const loaded = await import(pathToFileURL(modulePath).href);
const tool = loaded.default || loaded;
const eslintClients = new Map();

async function runPrettier(request) {
  const ignorePath = request.ignorePath || path.join(projectRoot, ".prettierignore");
  const infoOptions = fs.existsSync(ignorePath) ? { ignorePath } : {};
  const info = await tool.getFileInfo(request.path, infoOptions);
  if (info.ignored || !info.inferredParser) {
    return { ignored: true, version: tool.version };
  }
  const resolveOptions = { editorconfig: true };
  if (request.config) resolveOptions.config = request.config;
  const discovered = (await tool.resolveConfig(request.path, resolveOptions)) || {};
  const options = { ...discovered, ...(request.options || {}), filepath: request.path };
  const content = await tool.format(request.content, options);
  return { content, version: tool.version };
}

async function runEslint(request) {
  const ESLint = loaded.ESLint || (loaded.default && loaded.default.ESLint);
  if (!ESLint) {
    throw new Error("Installed eslint package does not export the ESLint API");
  }
  const key = request.config || "discover";
  let client = eslintClients.get(key);
  if (!client) {
    const options = { cwd: projectRoot, fix: false };
    if (request.config) options.overrideConfigFile = request.config;
    client = new ESLint(options);
    eslintClients.set(key, client);
  }
  const results = await client.lintText(request.content, { filePath: request.path });
  const messages = results.length ? results[0].messages : [];
  const packageJson = requireFromProject("eslint/package.json");
  return { messages, version: packageJson.version };
}

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  let request;
  try {
    request = JSON.parse(line);
    const result = mode === "prettier" ? await runPrettier(request) : await runEslint(request);
    process.stdout.write(JSON.stringify({ requestId: request.requestId, ...result }) + "\n");
  } catch (error) {
    process.stdout.write(JSON.stringify({ requestId: request && request.requestId, error: String(error && error.stack || error) }) + "\n");
  }
}
