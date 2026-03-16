#!/bin/bash
# Test script to compare home API endpoints between localhost and production
# Usage: ./scripts/test-home-api.sh [localhost|production|both]

set -e

# Localhost cookies (from browser)
LOCALHOST_COOKIES="authjs.callback-url=http%3A%2F%2Flocalhost%3A3000%2Fhome; authjs.csrf-token=6200349dadca1d5e85449903260ab407a2962686c05e6a734707453d63386538%7Cf5ee2394d1c9268a88b390fdefd66cdd67fce63af09302fbe73ca7c5125a7a0f; authjs.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIiwia2lkIjoieDF1ejg2MjBRNzF5TUxIdVFMUzctcFhHdnYtQ1ZUVzR5Wkp3aGxHZUtyUWFBYzUwaVY4a0FRV09LSHFQRF9vemtnWGhMS3NnMjdCQTVaMUdwVnoxLUEifQ..JqXHOZ1rzOtXRE0JSzgJwg.Y-bmBTohNvz5taPKTByYUZ6N2qNWYPgpgwlCrH31YsAgU7v1HsM0rYJ_PiFk8UiiCzZNZjvZ2v9egCWDBMVhfSXbxfx6z9YzZu3pbYLQjFkJNfc91yYw9dx6YmGrZkdw7ZjdZf1wupE6EmmHCe5qBKztAJRj-7Wt0THrcD4lzM0vT5DiiAlna6kUfAa9AYfoNZATHsS3Z3qku2xkS9DWMprMXkB63WWXxDT0KTYNTPPoZFAX5K4Nh_G5ZOG9PNAuDm4I2lDP_Tq-vE41GNVYJCwZnDZcauW3R7y3Giml9aJnwTTmlsxZEyKtbICV6h7ATlUTEOc__gElCUM7ApZJh9scWgWRwD3rntJ_T_GHA2_x_CKTqsewQi9g3nN5XL1_z1sb5KScXIYftaoNGRVMw_hWi8YUIebObSn9GJ_HQar4l9NCrqiMYRkWtgrfmQ801UP8L1zwBwdnxWICV3-OxN1j4P_FqoiVpezO93J7kOKh9dcC6avmPB_JXEbMEyieK7xI6DAQfUqNN8Vv9syxw1IHk3y3n1moC_DSXwVkNkcvh3Rs1nFLiaRnAQTKuT6QOqRiJUDtdNB2kzvkxr0kAD6KbsBVZpHuqlRcnDM2ZW26QJMzqRzspHTd0AZxEn7OogMx0vwKznbc9KzsCNBU8C76dGORFRp7lafrPj5bSfo7iV5Sd673-NnfarbdS7YuGv5PmNghOMB1XNT9nISEWZrwL1pLxgf_SwQyINuCqWpFghNMJatS6rR4D7sUoPVouy_ixSMa8B8amJQh4jbQIHzA3Q2PN50qCqQOhLmfAH-YVWMXHnJiDPxE3wvPoupz9Uqoc0Ey60qA_UIgoRcOM5a4X-OyigAI3-XsnCl5Ko6HCwB-QnIHnVkarD8o3Z59xEBYMSzIxonfrbufDjRgF2WFamBT6dVWcKMtuBsL--IFaeUXOORkPHpR1fW2soFtIyiVDiRo8znidrucODHQcIQBxG5FRVWqlyZcABPzgvszYrV3praI1Q-AQq3FmT7HRR1RZME7_akii-y2gtRdbAuEp9HMaVEo0aEQuEsjvsYhAU8EPfoGoNeV3EcQBPv28K1dgcuvAeNpYkCi8K1G4cgQWmE5j59cMUt8y3uByXIcKAUvMZZmeO3Cb1e2BQMf3Ko_mYlE1u-fCYiKR82z7pZqiBbk5b4eW7ePU0DHJSbb15xeV1Ssvd9Wc3oDUymqNRS5PiCETHU9OyLW0Rexn1Jdwbdry_1OTNiasPr6h9ttWtq9ucWuRYBv4KN2JBq-cS_Q_NjmotryU0HcQNSyDuHJvwSz42b9HXRKyN58_dTgjuqa6AOMIsSIDvaDL-ZvPgzc0YDvTA3P6DsQjpU6OeQswQu62MuYNiiNHLluYbiWxIfAL_1kR2ul1R2_F84I_MWppWca8Un6c5svGCOmBNadAzSmi85_n5riVs0Vay2K-oKN2aZaWT2N5fU-A0L1uuQw5dmMwAbax8gGAZPlDACEaCUPXj3DgHKdrbF1XZiGmPT9Xt0JebOKFdTSK5lRko089ntv1kL2y9r8LPiUH78LHr8TE9E-NwGrndB9yw0nipQf1WzawITUPQ1MXN6IkC3BV2EJh3PE8cmdtC40ZdszzyVsxSe4BsKFmuvLJzhwc-T6nEIzqTQTf3ViDnaHehMzj8dL94CcWgrEDESifHHxb5JmuBFK9fVQYCERvxWbCtyfoP-3JgDZOQMViABdvTFU3x0Pl0nYiqp0NO8lyKKRsNiFgPIXoDKfBc48TEDn6MSNZKDTgui3lzenp10ssX_-A4LbZ4Hnaj1YJh2Mddx3Z8BQ8JAIn5FonuU7XGJ63yGo7mBIywZ_fu0vr98DH-CWLUhpZ3Yd2LqW86UqZgCIqjL-tVxiFV7V5cwkGU1QF7Dy0VlWKGSnj7NqDR4crKN4CArpec7wAxNmIf7w-Vtj6jRvv0N5I0grmETdzRGTb_N8sCxqs5XvARxU4SF1pQ7onooGGA47kXb3YU1V6g.6J-KZE0KOUyt_ZesDBJPmz6_J0udDvo74iVDFHYirW8; realm-name=master"

# Production cookies (from curl-with-auth.sh default)
PRODUCTION_COOKIES="__Host-authjs.csrf-token=0595e1dada24c3d4a85d155a7a95b5e112426267449e4590f2b6ea7acc994de4%7C1e2f7c3f3ef91424b2a47d288905c9b9d2349ac8846df35c21ab91139ec29717; __Secure-authjs.callback-url=https%3A%2F%2Fglow.ashoksaravanan.com%2Fhome; __Secure-authjs.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIiwia2lkIjoieDNLQUdtMGFBdERFMHR3THZmQlhrOWJsZ3hhbHNwUGNSdmhrNzBhcjVPUEtkbXlISEJ2cXNwRWU5NjdXQnZ5Sm5DS01xN2Fzb2N0WnVQblA3VUdTZFEifQ..vOR-yU4HsbAow9R4Y26KVQ.zBxouxwhp3j5SB9wEOpdCxAEMXd8_3n19eCbP3xywkolULSaKM7auZjAv4FM7BTo4ib7xDHa0yZb_h4ZhWFHlDK-jQlWElXu5w47-0E6xYrpveiAlDDMCw8VdNKh9cDVwkBDNjsAEJCtwNlLM0i6_ew2ZRKYUM4Ak-aIksG_BEWu_0yysic24BMjxwi9A3K4wK5_hFS-KwIuXMxZcJwmBGKVU1boks4vaVSFC9hyHyXhBxmxiwFsw4fe2rk3QXKf-PlQn1ua2dejYofe_bMlvQhOF7WXmtNDeKnoP_WfOlzxn9DFuN7OgBqtKb6aMHAZTYcsTUES6N_gSaBOId_gnQv5wvF__fGFU2mVx3hsA6_nD1NPqtuTgzaQiL3M-Jt1_GzgRjfgvpEVhFSE3-LtL9hc1Uj2mvvdASChPUAFsqI_xmKpYPj9un57Q_E9j0-TquLxe4-mB5v17V7NfwP_RzQiBsO4BJOSYsBS7EyuM5zKQQpLM-PEn0Ie4S86jmk8057UuxXmimOUMSyNPbqe-YHNyJcy_5C8Mecf-H3JNBEV_8mbodP2H_tnYmu0IiFZQpKD8xrWKBYRBx53GXc69mnPer6gF1YF9S_Y4-c38tECHDS7zRQw9-7m2B_WyLvH33NJar4tMnIPflsod-9bqOY0RRV7tSvvGwY9tdFn3TS07R4SeJIvNYo3Zic5yQTZhmJfoQRHyHqTWV4vyKm2DX_nWhKdYYxvRdx0wswuF4yl6SqlkJGiOtnqTJwsZdTSWKXUuvGSsjVnFfAo6w_KAdmifBHyDSD260z31Br57XjE2xSVw9v7HdKlB6LOukO84qbHXk2i_KXE5Huyzq_KGJxpa03zNQQ4GiKk0eslStJj7JFVtLN4OrUx1v2mxbpPWD6W8AkHc4v3CzPeVxQNm3thkmoZPZduPUMGY9chFG4EWKJ6yrOZAly7nWW72VXTAtirczKVFz1xnjtRYVCPFffESi1j1kZaw-IQOgHWLoUDSrd6MgDAf8Kns7MGcG8SghYzZ4gulzQa5ibcudolVxxoYG9rFIQuLXYLFV4acWQnSOsjafiQ8lM9fa-I1gnmPKzA4w2Ek-Jez-8rsXmcYAMot_N4Fu8S6vmzK-GbWhq954BofJCi3mSgzNrwAyiZ_ThoOAKGlMrbacWW3fVov0OBVeYmO9rRqDNnlDM4M0N35ciQO7lMoiHA8coD47NiIyM5DHMa-BqZSCIFU3IpQkeufcRGdMsIlqQ1QP8dcsIbdvn3-0MREDRlDRe7zrm4m0LdoKo16MZl5iACLNLpOFqA0AmjCv0tOaeHzT8qpD0UbJL-rzbqw12oL447toXcJfb0i5dpfBiPL1xbvMQAQ7k1n6ES-mqSP1zN3e_OUz6sbRzUD_uXRxoLaWV8USAX4BRSGC_SfQqt6xrwhodHA1KCCv1pB1J8z1nGX2_AvF9-vW_lNVUFhzyydq3gf6d1fTBSnZ0rAwH_BDUUIUeKNPwzZOZrr6sM1SIKHlp36ohvnrSB9ByRoKnq9FXE-5tnfGQSLJ6c7sb73vblhHfELBAa1fcCD7puE23jNIDvnZkKsV2D0Y72w07cvul9KznJ_nn-B7Bo0Jjzee2RJFsDP4HWo3yYVov2UIoLSV0w2TIu0ZsrsU8ofkIsYB9V3ngJ8ndkw4rRVpoc_o4K3DFfcB5WVohGymqSRyVfbKLzCjX73bLjs1vr-X76l4a5LuSpRKSI3-kL0mI5H4OKuk6gqpWgTTWXnOjm_medlZpDiEUuh08oveyL9HBGDOwaKEEHsPLXIRHOlVIcdvosbGzZVEH_UZo-KbsP4Q0QrACHFsrHpxME3qZG2Cjh8U1PGDTR0mQPSiOiPBOM0v6hRocBl_Vorwzse5zlyxakuu8TOdfXdjB2rkdi5UiZKc581r17VTv_UxF5ICIcfvMJaEf43a76bj-4blN1PwzGUI4h6mQz3lKZXSqdVkn-67x6fa2C1ZI4oCuH7197tKrTjjPRBmxZTObjsdCo2iOmJKO6Mfs.1LuIPeNlnGAvVeVdstHNxl3xV_HLizQ-Y_1EwS6Zcd8; realm-name=master"

# Profile ID from api.md
PROFILE_ID="019b3be4-36f0-7ebd-ac27-52e3dba461f1"

# API request body
REQUEST_BODY='{
  "start_date": "2025-08-01T00:00:00Z",
  "end_date": "2025-11-01T23:59:59Z",
  "cohort_ids": [
    "c2759723-9baa-4289-8fa4-5e5a36276321",
    "cd0d0d90-4ff0-4ef0-a8ed-9bc6b0c70b5e",
    "d60309d7-51a3-54bd-81f3-b22f8dd2e007"
  ],
  "department_ids": [
    "001c8926-9dd8-4eaa-8b7f-e8f1868c5aeb",
    "0258cdab-7cf4-4d2f-96ec-98fae38df1bc",
    "083f55e9-08af-4b0a-8e1b-32f28d3afea3",
    "5af0d09d-1661-4610-9e0c-f768d1e87e36",
    "a9cc891d-859f-4ef8-b09d-2f6beabb618d",
    "c7692d34-b875-5122-af69-074f85981205",
    "fc3d3994-6274-4b87-ae85-2b845282c194"
  ]
}'

test_localhost() {
    echo "=========================================="
    echo "Testing LOCALHOST API"
    echo "=========================================="
    echo ""
    
    curl -X POST http://localhost:8000/api/v4/home/overview \
        -H "Content-Type: application/json" \
        -H "X-Profile-Id: $PROFILE_ID" \
        -H "Cookie: $LOCALHOST_COOKIES" \
        -d "$REQUEST_BODY" \
        -s | jq '.' > /tmp/localhost-api-response.json
    
    echo "Response saved to /tmp/localhost-api-response.json"
    echo ""
    echo "Summary:"
    cat /tmp/localhost-api-response.json | jq '{mode, has_data, items_count: (.items | length), standard_groups_count: (.standard_groups | length), standards_count: (.standards | length), simulations_count: (.simulations | length)}'
    echo ""
}

test_production() {
    echo "=========================================="
    echo "Testing PRODUCTION API"
    echo "=========================================="
    echo ""
    
    curl -X POST https://glow.ashoksaravanan.com/api/v4/home/overview \
        -H "Content-Type: application/json" \
        -H "X-Profile-Id: $PROFILE_ID" \
        -H "Cookie: $PRODUCTION_COOKIES" \
        -d "$REQUEST_BODY" \
        -s | jq '.' > /tmp/production-api-response.json
    
    echo "Response saved to /tmp/production-api-response.json"
    echo ""
    echo "Summary:"
    cat /tmp/production-api-response.json | jq '{mode, has_data, items_count: (.items | length), standard_groups_count: (.standard_groups | length), standards_count: (.standards | length), simulations_count: (.simulations | length)}'
    echo ""
}

compare_responses() {
    echo "=========================================="
    echo "COMPARING RESPONSES"
    echo "=========================================="
    echo ""
    
    if [ ! -f /tmp/localhost-api-response.json ] || [ ! -f /tmp/production-api-response.json ]; then
        echo "Error: One or both response files are missing"
        return 1
    fi
    
    echo "Differences in key fields:"
    echo ""
    echo "LOCALHOST:"
    cat /tmp/localhost-api-response.json | jq '{mode, has_data, items_count: (.items | length), cohort_ids_in_request: ["c2759723-9baa-4289-8fa4-5e5a36276321", "cd0d0d90-4ff0-4ef0-a8ed-9bc6b0c70b5e", "d60309d7-51a3-54bd-81f3-b22f8dd2e007"]}'
    echo ""
    echo "PRODUCTION:"
    cat /tmp/production-api-response.json | jq '{mode, has_data, items_count: (.items | length), cohort_ids_in_request: ["c2759723-9baa-4289-8fa4-5e5a36276321", "cd0d0d90-4ff0-4ef0-a8ed-9bc6b0c70b5e", "d60309d7-51a3-54bd-81f3-b22f8dd2e007"]}'
    echo ""
    
    echo "Full responses saved to:"
    echo "  - /tmp/localhost-api-response.json"
    echo "  - /tmp/production-api-response.json"
    echo ""
    echo "To compare in detail:"
    echo "  diff /tmp/localhost-api-response.json /tmp/production-api-response.json"
    echo "  or: jq -S '.' /tmp/localhost-api-response.json > /tmp/localhost-sorted.json"
    echo "      jq -S '.' /tmp/production-api-response.json > /tmp/production-sorted.json"
    echo "      diff /tmp/localhost-sorted.json /tmp/production-sorted.json"
}

MODE="${1:-both}"

case "$MODE" in
    localhost)
        test_localhost
        ;;
    production)
        test_production
        ;;
    both)
        test_localhost
        test_production
        compare_responses
        ;;
    *)
        echo "Usage: $0 [localhost|production|both]"
        exit 1
        ;;
esac

