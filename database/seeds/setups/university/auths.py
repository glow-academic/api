"""University auth-provider seed definitions.

Each auth is a dict mapping directly to ``CreateAuthItem`` and is created
through ``create_auth_impl`` (the same black-box path the config-driven
base auths use in ``database/seeds/auths.py``). The impl creates BOTH the
``auths_resource`` snapshot (``resource_id``) and the ``auth`` artifact
(``id``) from one item, resolving ``name``/``slug``/``protocol`` into their
resource rows — so the artifact↔resource linkage is always consistent.

Why this module exists: the default ``glow-deploy.yaml`` ships
``auth.providers: []``, so the base auth seed creates zero rows and the
``auths_resource`` table is empty. Every auths-* demo (overview, search,
idp, oidc, bulk) auto-skips on an empty table. Seeding a few realistic
SSO providers here (scoped to the University) unblocks those demos without
touching the shared deploy config (which would change every setup, incl.
``fresh``).

IDs are deterministic via ``sid("uni/auth/...")`` so re-runs are idempotent
at the DB layer (artifact/resource creates short-circuit on the same UUID).
"""

from database.seeds.ids import sid
from database.seeds.setups.university.departments import UNIVERSITY_DEPT_RESOURCE

# ---------------------------------------------------------------------------
# Deterministic IDs — artifact (``id``) vs resource snapshot (``resource_id``)
# are intentionally distinct, mirroring database/seeds/auths.py.
# ---------------------------------------------------------------------------

AUTH_ACTIVE_FLAG = sid("flag/auth-active")

# (slug, display name, protocol, description)
_AUTHS: list[tuple[str, str, str, str]] = [
    (
        "microsoft",
        "Microsoft Entra ID",
        "oidc",
        "Microsoft Entra ID (Azure AD) single sign-on for university staff and faculty.",
    ),
    (
        "google",
        "Google Workspace",
        "oidc",
        "Google Workspace single sign-on for university accounts.",
    ),
    (
        "okta",
        "Okta",
        "oidc",
        "Okta OIDC single sign-on for the university identity provider.",
    ),
]

# Exported resource IDs keyed by slug, in case other modules want to scope a
# setting to one of these auths in the future.
UNI_AUTH_RESOURCE_IDS = {
    slug: sid(f"uni/auth-resource/{slug}") for slug, _n, _p, _d in _AUTHS
}

# ---------------------------------------------------------------------------
# Auth definitions (creates) — dicts → CreateAuthItem
# ---------------------------------------------------------------------------

auths = [
    dict(
        id=sid(f"uni/auth/{slug}"),
        resource_id=sid(f"uni/auth-resource/{slug}"),
        name=name,
        description=description,
        slug=slug,
        protocol=protocol,
        flag_ids=[AUTH_ACTIVE_FLAG],
        active=True,
        department_ids=[UNIVERSITY_DEPT_RESOURCE],
    )
    for slug, name, protocol, description in _AUTHS
]
