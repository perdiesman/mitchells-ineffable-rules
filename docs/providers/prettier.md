# prettier

Format JavaScript, TypeScript, styles, and HTML with Prettier.

- **Languages**: javascript, typescript, css, html
- **Extensions**: .js, .jsx, .mjs, .cjs, .ts, .tsx, .css, .scss, .html
- **Check**: Yes
- **Fix**: No
- **Format**: Yes
- **Range formatting**: Yes
- **Batch execution**: Yes
- **Upstream documentation**: https://prettier.io/docs/

## Default configuration

```yaml
providers:
  prettier:
    enabled: auto
    executable: auto
    config: discover
    required_version: null
    timeout_seconds: 30
```

## Executable examples

### formatted object
```
const options={enabled:true};

```
Expected output:
```
const options = { enabled: true };

```
