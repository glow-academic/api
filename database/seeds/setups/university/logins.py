"""University logins seed — profile-based logins for the university setup.

Auth-based logins are seeded in the base phase (from glow-deploy.yaml config).
This module creates profile-based logins for the profiles linked to the
university setting.
"""

from database.seeds.setups.university.settings import UNI_LOGINS

logins = UNI_LOGINS
