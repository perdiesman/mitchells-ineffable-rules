import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mir.providers.common import utf16_offset
from mir.providers.node_bridge import NodeBridgeError


@unittest.skipUnless(
    shutil.which("node"), "Node.js is required for the Prettier bridge"
)
class TestPrettierRanges(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        package = self.root / "node_modules" / "prettier"
        package.mkdir(parents=True)
        (self.root / "package.json").write_text("{}")
        (package / "package.json").write_text(
            json.dumps(
                {
                    "type": "module",
                    "exports": {
                        ".": "./index.mjs",
                        "./plugins/babel": "./parser.mjs",
                        "./plugins/typescript": "./parser.cjs",
                    },
                }
            )
        )
        (package / "index.mjs").write_text("""
import fs from 'node:fs';
export const version = '3.8.1';
export const getFileInfo = async file => ({inferredParser: file.endsWith('.ts') ? 'typescript' : 'babel'});
export const resolveConfig = async () => ({});
export const format = async (text, options) => JSON.stringify(options);
""")
        (package / "parser.mjs").write_text("""
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const fixture = fileURLToPath(new URL('../../ast.json', import.meta.url));
const parser = {astFormat: 'estree', parse: () => JSON.parse(fs.readFileSync(fixture, 'utf8')),
  locStart: node => node.start ?? node.range?.[0], locEnd: node => node.end ?? node.range?.[1]};
export const parsers = {babel: parser, typescript: parser};
""")
        (package / "parser.cjs").write_text("""
const fs = require('node:fs');
const path = require('node:path');
const parser = {astFormat: 'estree', parse: () => JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../ast.json'), 'utf8')),
  locStart: node => node.start ?? node.range?.[0], locEnd: node => node.end ?? node.range?.[1]};
module.exports = {parsers: {typescript: parser}};
""")

    def request(self, source, ast, options, extension="mjs"):
        (self.root / "ast.json").write_text(json.dumps(ast))
        bridge = Path(__file__).resolve().parents[1] / "mir/providers/node_bridge.mjs"
        request = {
            "path": str(self.root / f"sample.{extension}"),
            "content": source,
            "options": options,
        }
        process = subprocess.run(
            [
                shutil.which("node"),
                "--experimental-import-meta-resolve",
                str(bridge),
                "prettier",
                str(self.root),
            ],
            input=json.dumps(request) + "\n",
            text=True,
            capture_output=True,
            timeout=10,
            check=True,
        )
        result = json.loads(process.stdout)
        if result.get("error"):
            raise NodeBridgeError(result["error"])
        return json.loads(result["content"])

    def test_nested_control_flow_retains_the_complete_top_level_declaration(self):
        for statement in (
            "outer: for (const item of items) { while (item.skip) { continue outer; } }",
            "function run() { for (const item of items) { if (item.skip) return; } }",
            "class Child extends Parent { #value = 1; run() { return super.run(this.#value); } }",
            "switch (value) { case 1: if (enabled) { break; } }",
        ):
            with self.subTest(statement=statement):
                source = "const before = 1;\n" + statement + "\nconst after = 2;\n"
                start = source.index(statement)
                end = start + len(statement)
                requested = {"rangeStart": start + 12, "rangeEnd": end - 2}
                ast = {
                    "type": "File",
                    "program": {
                        "body": [
                            {"start": 0, "end": start - 1},
                            {"start": start, "end": end},
                            {"start": end + 1, "end": len(source) - 1},
                        ]
                    },
                }
                result = self.request(source, ast, requested)
                self.assertEqual(
                    (result["rangeStart"], result["rangeEnd"]), (start, end)
                )
                self.assertEqual(
                    requested, {"rangeStart": start + 12, "rangeEnd": end - 2}
                )
                repeated = self.request(source, ast, result)
                self.assertEqual(repeated, result)

    def test_typescript_program_ranges_keep_utf16_offsets_and_configuration(self):
        source = "// 😀\nexport class Item { count: number = 1; }\n"
        start = utf16_offset(source, source.index("export"))
        end = utf16_offset(source, len(source.rstrip()))
        result = self.request(
            source,
            {"type": "Program", "body": [{"range": [start, end]}]},
            {"rangeStart": start + 10, "rangeEnd": end - 2, "tabWidth": 4},
            "ts",
        )
        self.assertEqual((result["rangeStart"], result["rangeEnd"]), (start, end))
        self.assertEqual(result["tabWidth"], 4)

    def test_range_can_span_multiple_statements_without_reaching_unrelated_ones(self):
        source = "first();\nsecond();\nthird();\n"
        ast = {
            "body": [
                {"start": 0, "end": 8},
                {"start": 9, "end": 18},
                {"start": 19, "end": 27},
            ]
        }
        result = self.request(source, ast, {"rangeStart": 2, "rangeEnd": 12})
        self.assertEqual((result["rangeStart"], result["rangeEnd"]), (0, 18))

    def test_comments_and_full_file_ranges_do_not_need_statement_expansion(self):
        source = "// comment\nconst value = 1;\n"
        result = self.request(
            source,
            {"body": [{"start": 11, "end": len(source) - 1}]},
            {"rangeStart": 0, "rangeEnd": 10},
        )
        self.assertEqual((result["rangeStart"], result["rangeEnd"]), (0, 10))
        result = self.request(source, {}, {"rangeStart": 0, "rangeEnd": len(source)})
        self.assertEqual((result["rangeStart"], result["rangeEnd"]), (0, len(source)))

    def test_custom_grammars_and_preprocessors_keep_prettiers_own_range_handling(self):
        package = self.root / "node_modules" / "custom-parser"
        package.mkdir()
        (package / "package.json").write_text('{"type":"module","main":"index.mjs"}')
        for ast_format, preprocess in (
            ("custom", ""),
            ("estree", "preprocess: text => text,"),
        ):
            with self.subTest(ast_format=ast_format):
                (package / "index.mjs").write_text(
                    "export default {parsers: {babel: {astFormat: "
                    + json.dumps(ast_format)
                    + ","
                    + preprocess
                    + "parse() { throw new Error('Must not expand this grammar'); }}}};"
                )
                result = self.request(
                    "const value = 1;\n",
                    {},
                    {
                        "rangeStart": 2,
                        "rangeEnd": 5,
                        "plugins": ["custom-parser"],
                    },
                )
                self.assertEqual((result["rangeStart"], result["rangeEnd"]), (2, 5))

    def test_invalid_parser_boundaries_fail_explicitly(self):
        for ast in (
            {},
            {"body": [{"start": -1, "end": 2}]},
            {"body": [{"start": 0, "end": 1000}]},
        ):
            with (
                self.subTest(ast=ast),
                self.assertRaisesRegex(
                    NodeBridgeError, "program body|invalid statement range"
                ),
            ):
                self.request(
                    "const value = 1;\n", ast, {"rangeStart": 2, "rangeEnd": 5}
                )

    def test_import_only_plugin_resolves_from_the_consumer_project(self):
        package = self.root / "node_modules" / "import-only-plugin"
        package.mkdir()
        (package / "package.json").write_text(
            json.dumps({"type": "module", "exports": {".": {"import": "./index.mjs"}}})
        )
        (package / "index.mjs").write_text(
            "export {parsers} from 'prettier/plugins/babel';"
        )
        source = "const value = 1;\n"
        result = self.request(
            source,
            {"body": [{"start": 0, "end": len(source) - 1}]},
            {"rangeStart": 2, "rangeEnd": 5, "plugins": ["import-only-plugin"]},
        )
        self.assertEqual(
            (result["rangeStart"], result["rangeEnd"]), (0, len(source) - 1)
        )


if __name__ == "__main__":
    unittest.main()
