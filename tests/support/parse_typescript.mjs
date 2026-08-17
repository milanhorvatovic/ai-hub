// Syntax-checks TypeScript samples handed to it as JSON on stdin.
//
// Parsing, not typechecking: the samples are fragments naming types and helpers
// defined nowhere (`OrderSchema`, `PublicUser`), so a full compile would report
// resolution errors on content that is correct as an illustration. The lane asks
// the compiler for syntactic diagnostics only, which is exactly the line it
// wants to hold.
//
// The pinned compiler is TypeScript 7, the native port. Its npm package ships no
// in-process compiler API; what it ships is a bridge (`typescript/unstable/async`)
// that spawns the bundled Go binary and speaks to it over stdio. The bridge
// addresses files rather than strings, so the fragments are written to a
// temporary project first. The `unstable/` path segment is the vendor's own
// churn warning — the exact version pin plus the control samples the caller
// sends with every batch are what turn a future shape change into a red check
// instead of a silent pass.
//
// stdin:  [{ "id": "<path>:<line>", "source": "<fence body>" }, ...]
// stdout: { "checked": <n>, "problems": [{ "id", "line", "message" }, ...] }
// exit 3: the pinned typescript is not usable here (the caller skips rather than fails)

import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

let API;
try {
  // Older majors publish neither the subpath nor the class, so both a missing
  // package and a wrong-major package land on the same exit: "no usable
  // compiler", reported before any work is attempted rather than as a
  // TypeError halfway through it.
  ({ API } = await import("typescript/unstable/async"));
} catch {
  process.stderr.write(
    "typescript with the unstable/async API is not installed (this lane needs the pinned 7.x); run `npm ci`\n",
  );
  process.exit(3);
}
if (typeof API !== "function") {
  process.stderr.write(
    "the installed typescript exports no unstable/async API class; this lane needs the 7.x bridge\n",
  );
  process.exit(3);
}

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const samples = JSON.parse(Buffer.concat(chunks).toString("utf8"));

// Sample ids are `<path>:<line>` labels, not usable filenames; each fragment
// gets an index-named file and the index maps diagnostics back to the id.
const dir = mkdtempSync(path.join(tmpdir(), "ts-sample-lane-"));
const fileFor = (index) => path.join(dir, `sample_${index}.ts`);
writeFileSync(
  path.join(dir, "tsconfig.json"),
  JSON.stringify({ compilerOptions: { noEmit: true }, include: ["*.ts"] }),
);
for (const [index, { source }] of samples.entries()) writeFileSync(fileFor(index), source);

let api;
const cleanup = async () => {
  await api?.close().catch(() => {});
  rmSync(dir, { recursive: true, force: true });
};

let snapshot;
try {
  api = new API({ cwd: dir });
  snapshot = await api.updateSnapshot({ openProjects: [path.join(dir, "tsconfig.json")] });
} catch (error) {
  // Startup is availability, not verdict: a platform without a bundled binary,
  // or a bridge that cannot spawn, is the same "cannot run here" the missing
  // package is. Anything after startup is a real failure and propagates.
  await cleanup();
  process.stderr.write(`the typescript API bridge failed to start: ${error?.message ?? error}\n`);
  process.exit(3);
}

try {
  // Exactly the one project this process opened; matching by count rather than
  // by config path sidesteps the bridge's own path normalization, and a bridge
  // that starts surfacing extra projects (say, an inferred one) fails here as
  // the protocol change it is instead of as diagnostics quietly run against
  // the wrong project.
  const projects = snapshot.getProjects();
  if (projects.length !== 1) {
    throw new Error(
      `the temporary project at ${dir} resolved to ${projects.length} projects instead of exactly one`,
    );
  }
  const { program } = projects[0];

  const problems = [];
  for (const [index, { id, source }] of samples.entries()) {
    for (const diagnostic of await program.getSyntacticDiagnostics(fileFor(index))) {
      problems.push({
        id,
        // Diagnostic positions are offsets into the file this process wrote, so
        // the line is recovered from the source it holds in memory.
        line: source.slice(0, diagnostic.pos ?? 0).split("\n").length,
        message: diagnostic.text.replace(/\r?\n\s*/g, "; "),
      });
    }
  }

  process.stdout.write(JSON.stringify({ checked: samples.length, problems }));
} finally {
  await cleanup();
}
