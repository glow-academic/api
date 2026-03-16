# Cookie Extraction Guide

This guide shows you how to extract cookies from your browser to use with curl or other tools.

## Quick Method: Browser DevTools

### Chrome/Edge/Brave

1. Open DevTools (F12 or Cmd+Option+I on Mac)
2. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
3. Click **Cookies** → `https://glow.ashoksaravanan.com`
4. Find these cookies:
   - `__Secure-authjs.session-token` (or `next-auth.session-token` - depends on NextAuth version)
   - `realm-name` (optional, defaults to "master")
   - `department-id` (for guest sessions)
   - `auth-mode` (for guest sessions)

5. Copy the cookie values and use them like this:

```bash
curl -H "Cookie: __Secure-authjs.session-token=YOUR_TOKEN_HERE; realm-name=master" \
     https://glow.ashoksaravanan.com/home
```

**Important**: Include the full cookie name including prefixes like `__Secure-` or `__Host-` when using with curl.

### Firefox

1. Open DevTools (F12)
2. Go to **Storage** tab
3. Click **Cookies** → `https://glow.ashoksaravanan.com`
4. Copy cookie values as above

## Using the Helper Script

We have a helper script that makes this easier:

```bash
# Option 1: Export cookies to cookies.txt (Netscape format)
# Then run:
./scripts/curl-with-auth.sh https://glow.ashoksaravanan.com/home

# Option 2: Set environment variable
export COOKIES='next-auth.session-token=YOUR_TOKEN; realm-name=master'
./scripts/curl-with-auth.sh https://glow.ashoksaravanan.com/home

# Option 3: Pass cookies directly
./scripts/curl-with-auth.sh https://glow.ashoksaravanan.com/home \
  'next-auth.session-token=YOUR_TOKEN; realm-name=master'
```

## Browser Extensions

### Cookie-Editor (Recommended)

1. Install [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) extension
2. Click the extension icon
3. Click "Export" → "Netscape format"
4. Save as `cookies.txt` in project root
5. Run: `./scripts/curl-with-auth.sh https://glow.ashoksaravanan.com/home`

### EditThisCookie

1. Install [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
2. Click extension icon
3. Export cookies
4. Convert to Netscape format or use directly

## Manual Cookie String Format

Cookies should be formatted as:
```
cookie-name-1=cookie-value-1; cookie-name-2=cookie-value-2
```

Example:
```
__Secure-authjs.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIiwia2lkIjoieDNLQUdtMGFBdERFMHR3THZmQlhrOWJsZ3hhbHNwUGNSdmhrNzBhcjVPUEtkbXlISEJ2cXNwRWU5NjdXQnZ5Sm5DS01xN2Fzb2N0WnVQblA3VUdTZFEifQ...; realm-name=master
```

**Note**: Cookie names may include prefixes like `__Secure-` or `__Host-`. Always use the full cookie name as shown in your browser's DevTools.

## Testing

Once you have cookies, test with:

```bash
# Test the home page
curl -v -H "Cookie: YOUR_COOKIES_HERE" \
     https://glow.ashoksaravanan.com/home

# Save response to file
curl -H "Cookie: YOUR_COOKIES_HERE" \
     https://glow.ashoksaravanan.com/home > authenticated-response.html
```

## Important Notes

- **Session tokens expire**: Cookies may expire, so you'll need to refresh them periodically
- **HttpOnly cookies**: Some cookies may be HttpOnly and not accessible via JavaScript (but still work with curl)
- **Secure cookies**: Make sure you're using HTTPS URLs
- **Domain matching**: Cookies are domain-specific, so use the exact domain (`glow.ashoksaravanan.com`)

## Troubleshooting

If you get "Access Denied":
1. Check that your session token is still valid (try refreshing the page in browser)
2. Make sure you're including all required cookies
3. Verify the cookie format is correct (no extra spaces, proper semicolons)

If cookies don't work:
1. Try logging out and back in to get fresh cookies
2. Check browser console for any authentication errors
3. Verify the `realm-name` cookie matches your authentication realm

