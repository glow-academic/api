"""Output: test.* events."""

from . import (  # noqa: F401
    # Per-operation lifecycle dirs (started/completed/progress/error per op)
    end,
    end_all,
    grade,
    group,
    join,
    next,
    proceed,
    run,
    start,
    stop,
    # Grade bridge (generate_call_complete → test grade)
    generate_grade,
)
from app.ws.output.test import generate as _generate  # noqa: F401, E402
from app.ws.output.test import generations as _generations  # noqa: F401, E402
from app.ws.output.test import group as _group  # noqa: F401, E402
from app.ws.output.test import problem as _problem  # noqa: F401, E402
# Absorbed sub-modules
from app.ws.output.test import benchmark as _benchmark  # noqa: F401, E402
from app.ws.output.test import invocation as _invocation  # noqa: F401, E402
