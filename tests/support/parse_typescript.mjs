// Syntax-checks TypeScript samples handed to it as JSON on stdin.
//
// Parsing, not typechecking: the samples are fragments naming types and helpers
// defined nowhere (`OrderSchema`, `PublicUser`), so a `tsc` run would report
// resolution errors on content that is correct as an illustration.
// `createSourceFile` populates `parseDiagnostics` and resolves nothing, which is
// exactly the line this lane wants to hold.
//
// stdin:  [{ "id": "<path>:<line>", "source": "<fence body>" }, ...]
// stdout: { "checked": <n>, "problems": [{ "id", "line", "message" }, ...] }
// exit 3: the pinned typescript is not installed (the caller skips rather than fails)

let ts;
try {
  ts = (await import("typescript")).default;
} catch {
  process.stderr.write("typescript is not installed; run `npm ci`\n");
  process.exit(3);
}

// The compiler API this lane uses belongs to the 5.x line. TypeScript 7's npm
// package is the native port and exports only `version`, so a blind major bump
// lands here rather than somewhere subtle.
if (typeof ts.createSourceFile !== "function") {
  process.stderr.write(
    `typescript ${ts.version} exposes no createSourceFile; this lane needs the 5.x compiler API\n`,
  );
  process.exit(3);
}

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const samples = JSON.parse(Buffer.concat(chunks).toString("utf8"));

const problems = [];
for (const { id, source } of samples) {
  // `ScriptKind.TS` states the intent; it does not change what is reported here,
  // because TypeScript runs one parser for both kinds and the rules that differ
  // are checker-level. Verified rather than assumed — a mutation to `ScriptKind.JS`
  // produces byte-identical diagnostics on every construct these samples use.
  const parsed = ts.createSourceFile(id, source, ts.ScriptTarget.Latest, false, ts.ScriptKind.TS);
  // `parseDiagnostics` is internal — present at runtime, absent from the public
  // types. The public route to syntactic diagnostics is a Program, which wants a
  // CompilerHost and a filesystem to check fragments that belong to neither. The
  // reason this is safe to depend on is not that it is stable: it is that the
  // caller sends a deliberately broken control sample with every batch and fails
  // when it comes back clean. If this property ever disappears, `?? []` reports
  // everything as fine and that control is what notices.
  for (const diagnostic of parsed.parseDiagnostics ?? []) {
    const { line } = parsed.getLineAndCharacterOfPosition(diagnostic.start ?? 0);
    problems.push({
      id,
      line: line + 1,
      message: ts.flattenDiagnosticMessageText(diagnostic.messageText, "; "),
    });
  }
}

process.stdout.write(JSON.stringify({ checked: samples.length, problems }));
