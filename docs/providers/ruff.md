# ruff

Lint and format Python with Ruff.

- **Languages**: python
- **Extensions**: .py, .pyi
- **Check**: Yes
- **Fix**: Yes
- **Format**: Yes
- **Range formatting**: Yes
- **Batch execution**: Yes
- **Upstream documentation**: https://docs.astral.sh/ruff/

## Default configuration

```yaml
providers:
  ruff:
    enabled: auto
    executable: auto
    config: discover
    check: true
    format: true
    unsafe_fixes: false
    timeout_seconds: 30
```

## Executable examples

### formatted function
```
def add( left,right ):
 return left+right

```
Expected output:
```
def add(left, right):
    return left + right

```