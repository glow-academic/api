#!/bin/bash
# Helper script to curl authenticated endpoints using browser cookies
# 
# Usage:
#   ./scripts/curl-with-auth.sh https://glow.ashoksaravanan.com/home
#
# This script includes default example cookies (Ashok's session) for easy sharing
# with other agents or for quick testing. These cookies expire Feb 3, 2026.
#
# Cookie priority (highest to lowest):
#   1. A cookies.txt file (Netscape format) - export from browser extension
#   2. Manual cookie string passed as second argument
#   3. Environment variable COOKIES (semicolon-separated)
#   4. Default example cookies (included in script - expires Feb 3, 2026)

set -e

# Default example cookies (for testing/reference purposes)
# These are Ashok's current session cookies - expires Feb 3, 2026
# To use your own cookies, export COOKIES env var or pass as second argument
DEFAULT_COOKIES="__Host-authjs.csrf-token=0595e1dada24c3d4a85d155a7a95b5e112426267449e4590f2b6ea7acc994de4%7C1e2f7c3f3ef91424b2a47d288905c9b9d2349ac8846df35c21ab91139ec29717; __Secure-authjs.callback-url=https%3A%2F%2Fglow.ashoksaravanan.com%2Fhome; __Secure-authjs.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIiwia2lkIjoieDNLQUdtMGFBdERFMHR3THZmQlhrOWJsZ3hhbHNwUGNSdmhrNzBhcjVPUEtkbXlISEJ2cXNwRWU5NjdXQnZ5Sm5DS01xN2Fzb2N0WnVQblA3VUdTZFEifQ..vOR-yU4HsbAow9R4Y26KVQ.zBxouxwhp3j5SB9wEOpdCxAEMXd8_3n19eCbP3xywkolULSaKM7auZjAv4FM7BTo4ib7xDHa0yZb_h4ZhWFHlDK-jQlWElXu5w47-0E6xYrpveiAlDDMCw8VdNKh9cDVwkBDNjsAEJCtwNlLM0i6_ew2ZRKYUM4Ak-aIksG_BEWu_0yysic24BMjxwi9A3K4wK5_hFS-KwIuXMxZcJwmBGKVU1boks4vaVSFC9hyHyXhBxmxiwFsw4fe2rk3QXKf-PlQn1ua2dejYofe_bMlvQhOF7WXmtNDeKnoP_WfOlzxn9DFuN7OgBqtKb6aMHAZTYcsTUES6N_gSaBOId_gnQv5wvF__fGFU2mVx3hsA6_nD1NPqtuTgzaQiL3M-Jt1_GzgRjfgvpEVhFSE3-LtL9hc1Uj2mvvdASChPUAFsqI_xmKpYPj9un57Q_E9j0-TquLxe4-mB5v17V7NfwP_RzQiBsO4BJOSYsBS7EyuM5zKQQpLM-PEn0Ie4S86jmk8057UuxXmimOUMSyNPbqe-YHNyJcy_5C8Mecf-H3JNBEV_8mbodP2H_tnYmu0IiFZQpKD8xrWKBYRBx53GXc69mnPer6gF1YF9S_Y4-c38tECHDS7zRQw9-7m2B_WyLvH33NJar4tMnIPflsod-9bqOY0RRV7tSvvGwY9tdFn3TS07R4SeJIvNYo3Zic5yQTZhmJfoQRHyHqTWV4vyKm2DX_nWhKdYYxvRdx0wswuF4yl6SqlkJGiOtnqTJwsZdTSWKXUuvGSsjVnFfAo6w_KAdmifBHyDSD260z31Br57XjE2xSVw9v7HdKlB6LOukO84qbHXk2i_KXE5Huyzq_KGJxpa03zNQQ4GiKk0eslStJj7JFVtLN4OrUx1v2mxbpPWD6W8AkHc4v3CzPeVxQNm3thkmoZPZduPUMGY9chFG4EWKJ6yrOZAly7nWW72VXTAtirczKVFz1xnjtRYVCPFffESi1j1kZaw-IQOgHWLoUDSrd6MgDAf8Kns7MGcG8SghYzZ4gulzQa5ibcudolVxxoYG9rFIQuLXYLFV4acWQnSOsjafiQ8lM9fa-I1gnmPKzA4w2Ek-Jez-8rsXmcYAMot_N4Fu8S6vmzK-GbWhq954BofJCi3mSgzNrwAyiZ_ThoOAKGlMrbacWW3fVov0OBVeYmO9rRqDNnlDM4M0N35ciQO7lMoiHA8coD47NiIyM5DHMa-BqZSCIFU3IpQkeufcRGdMsIlqQ1QP8dcsIbdvn3-0MREDRlDRe7zrm4m0LdoKo16MZl5iACLNLpOFqA0AmjCv0tOaeHzT8qpD0UbJL-rzbqw12oL447toXcJfb0i5dpfBiPL1xbvMQAQ7k1n6ES-mqSP1zN3e_OUz6sbRzUD_uXRxoLaWV8USAX4BRSGC_SfQqt6xrwhodHA1KCCv1pB1J8z1nGX2_AvF9-vW_lNVUFhzyydq3gf6d1fTBSnZ0rAwH_BDUUIUeKNPwzZOZrr6sM1SIKHlp36ohvnrSB9ByRoKnq9FXE-5tnfGQSLJ6c7sb73vblhHfELBAa1fcCD7puE23jNIDvnZkKsV2D0Y72w07cvul9KznJ_nn-B7Bo0Jjzee2RJFsDP4HWo3yYVov2UIoLSV0w2TIu0ZsrsU8ofkIsYB9V3ngJ8ndkw4rRVpoc_o4K3DFfcB5WVohGymqSRyVfbKLzCjX73bLjs1vr-X76l4a5LuSpRKSI3-kL0mI5H4OKuk6gqpWgTTWXnOjm_medlZpDiEUuh08oveyL9HBGDOwaKEEHsPLXIRHOlVIcdvosbGzZVEH_UZo-KbsP4Q0QrACHFsrHpxME3qZG2Cjh8U1PGDTR0mQPSiOiPBOM0v6hRocBl_Vorwzse5zlyxakuu8TOdfXdjB2rkdi5UiZKc581r17VTv_UxF5ICIcfvMJaEf43a76bj-4blN1PwzGUI4h6mQz3lKZXSqdVkn-67x6fa2C1ZI4oCuH7197tKrTjjPRBmxZTObjsdCo2iOmJKO6Mfs.1LuIPeNlnGAvVeVdstHNxl3xV_HLizQ-Y_1EwS6Zcd8; realm-name=master"

URL="${1:-https://glow.ashoksaravanan.com/home}"
COOKIE_STRING="${2:-${COOKIES:-${DEFAULT_COOKIES}}}"

# Try to load cookies from cookies.txt file (Netscape format)
# You can export this using browser extensions like "Cookie-Editor" or "EditThisCookie"
if [ -f "cookies.txt" ]; then
    echo "📁 Loading cookies from cookies.txt..."
    # Convert Netscape format to curl format
    COOKIE_STRING=$(grep -v "^#" cookies.txt | grep -v "^$" | \
        awk -F'\t' '{printf "%s=%s; ", $7, $8}' | sed 's/; $//')
fi

# If no cookies found, show instructions
if [ -z "$COOKIE_STRING" ]; then
    echo "❌ No cookies found!"
    echo ""
    echo "To use this script, you need to export cookies from your browser:"
    echo ""
    echo "Option 1: Export to cookies.txt (Netscape format)"
    echo "  - Install a browser extension like 'Cookie-Editor' or 'EditThisCookie'"
    echo "  - Export cookies for glow.ashoksaravanan.com"
    echo "  - Save as 'cookies.txt' in the project root"
    echo ""
    echo "Option 2: Set COOKIES environment variable"
    echo "  export COOKIES='__Secure-authjs.session-token=YOUR_TOKEN; realm-name=master'"
    echo "  ./scripts/curl-with-auth.sh $URL"
    echo ""
    echo "Option 3: Pass cookies as second argument"
    echo "  ./scripts/curl-with-auth.sh $URL '__Secure-authjs.session-token=YOUR_TOKEN; realm-name=master'"
    echo ""
    echo "Key cookies to look for:"
    echo "  - __Secure-authjs.session-token (or next-auth.session-token)"
    echo "  - realm-name"
    echo "  - department-id (for guest sessions)"
    echo "  - auth-mode (for guest sessions)"
    echo ""
    echo "Note: Cookie names may have prefixes like __Secure- or __Host-"
    echo "      Include the full cookie name when using with curl"
    exit 1
fi

# Show which cookies we're using
if [ "$COOKIE_STRING" = "$DEFAULT_COOKIES" ]; then
    echo "ℹ️  Using default example cookies (expires Feb 3, 2026)"
else
    echo "🔐 Using provided cookies: ${COOKIE_STRING:0:80}..."
fi
echo ""

# Make the request with cookies
curl -v \
    -H "Cookie: $COOKIE_STRING" \
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
    "$URL" \
    2>&1 | tee /tmp/curl-response.txt

echo ""
echo ""
echo "✅ Response saved to /tmp/curl-response.txt"
echo "To see just the HTML body:"
echo "  cat /tmp/curl-response.txt | grep -A 1000 '^< HTTP' | tail -n +2"

