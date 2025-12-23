"""Patching yfinance to bypass blocked domain checks."""

import os
import logging
import yfinance.data

logger = logging.getLogger(__name__)

def patch_yfinance():
    """Apply the cookie check bypass patch to yfinance."""
    if os.getenv("YFINANCE_SKIP_COOKIE_CHECK", "1") == "1":
        logger.info("Applying yfinance cookie check bypass patch")
        
        def _get_cookie_basic_patched(self, timeout=30):
            return True

        yfinance.data.YfData._get_cookie_basic = _get_cookie_basic_patched
    else:
        logger.info("yfinance patch skipped (YFINANCE_SKIP_COOKIE_CHECK != 1)")

# Apply immediately on import
patch_yfinance()
