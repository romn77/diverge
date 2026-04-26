"""Compatibility entrypoint for historical metadata backfill helpers."""

from __future__ import annotations

import sys

from web.backend.devops import backfill_metadata as _impl

sys.modules[__name__] = _impl
