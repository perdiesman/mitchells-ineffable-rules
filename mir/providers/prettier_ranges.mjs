/** Give Prettier complete syntax without changing MIR's authorized edit scope. */
export async function expandPrettierRange(text, options, parser) {
  const start = options.rangeStart ?? 0;
  const end = options.rangeEnd ?? text.length;
  if (start === 0 && end >= text.length) return options;

  const ast = await parser.parse(text, options);
  const body = (ast.program ?? ast).body;
  if (!Array.isArray(body)) {
    throw new Error(
      "Prettier parser did not return a program body for range expansion",
    );
  }
  let rangeStart = start;
  let rangeEnd = end;
  // A whole top-level statement retains every enclosing loop, label, function,
  // or class that Prettier's isolated range reparse may otherwise lose.
  for (const statement of body) {
    const nodeStart = parser.locStart(statement);
    const nodeEnd = parser.locEnd(statement);
    if (
      !Number.isInteger(nodeStart) ||
      !Number.isInteger(nodeEnd) ||
      nodeStart < 0 ||
      nodeEnd < nodeStart ||
      nodeEnd > text.length
    ) {
      throw new Error("Prettier parser returned an invalid statement range");
    }
    if (nodeStart < end && nodeEnd > start) {
      rangeStart = Math.min(rangeStart, nodeStart);
      rangeEnd = Math.max(rangeEnd, nodeEnd);
    }
  }
  return { ...options, rangeStart, rangeEnd };
}
