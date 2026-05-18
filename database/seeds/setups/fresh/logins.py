"""Fresh logins seed — profile-based logins for the fresh setup.

Auth-based logins are seeded in the base phase (from glow-deploy.yaml config).
This module creates profile-based logins for the profiles linked to the
fresh setting.
"""

from database.seeds.setups.fresh.settings import FRESH_LOGINS

logins = FRESH_LOGINS
