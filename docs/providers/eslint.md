# eslint

Lint JavaScript and TypeScript with project-local ESLint.

- **Languages**: javascript, typescript
- **Extensions**: .js, .jsx, .mjs, .cjs, .ts, .tsx
- **Check**: Yes
- **Fix**: Yes
- **Format**: No
- **Range formatting**: No
- **Batch execution**: Yes
- **Upstream documentation**: https://eslint.org/docs/latest/

## Default configuration

```yaml
providers:
  eslint:
    enabled: auto
    executable: auto
    config: discover
    fix: true
    timeout_seconds: 30
```
