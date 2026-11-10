"""Compatibility facade for the core modules.

Operators, the UI and tests keep importing from :mod:`logic`; the actual code
lives in :mod:`core.common`, :mod:`core.output`, :mod:`core.scene`,
:mod:`core.framing` and :mod:`core.job`.
"""

from .core.common import *  # noqa: F401,F403
from .core.output import *  # noqa: F401,F403
from .core.scene import *  # noqa: F401,F403
from .core.framing import *  # noqa: F401,F403
from .core.job import *  # noqa: F401,F403
