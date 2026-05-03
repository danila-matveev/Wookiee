import platform
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from services.telemost_recorder.config import BROWSER_FLAGS, HEADLESS

# Injected into every page before any site script runs.
# Intercepts all three ways JS can navigate to a custom protocol URL.
# Mutes all outgoing audio by disabling tracks returned by getUserMedia.
# Prevents the Chromium fake-device 440 Hz tone from being transmitted to
# other meeting participants. Video track is kept (needed for Telemost to
# accept the join), but audio is silenced from the very first frame.
_MEDIA_MUTE_SCRIPT = """
(function () {
    var orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = function (constraints) {
        return orig(constraints).then(function (stream) {
            stream.getAudioTracks().forEach(function (t) { t.enabled = false; });
            return stream;
        });
    };
})();
"""

_BTN_BLOCKER_SCRIPT = """
(function () {
    var proto = Object.getPrototypeOf(window.location);

    var _assign = proto.assign;
    proto.assign = function (url) {
        if (typeof url === 'string' && url.indexOf('btn://') === 0) return;
        return _assign.apply(this, arguments);
    };

    var _replace = proto.replace;
    proto.replace = function (url) {
        if (typeof url === 'string' && url.indexOf('btn://') === 0) return;
        return _replace.apply(this, arguments);
    };

    var hrefDesc = Object.getOwnPropertyDescriptor(proto, 'href');
    if (hrefDesc && hrefDesc.set) {
        Object.defineProperty(proto, 'href', {
            get: hrefDesc.get,
            set: function (url) {
                if (typeof url === 'string' && url.indexOf('btn://') === 0) return;
                return hrefDesc.set.call(this, url);
            },
            configurable: true,
            enumerable: true,
        });
    }

    var _open = window.open;
    window.open = function (url) {
        if (typeof url === 'string' && url.indexOf('btn://') === 0) return null;
        return _open.apply(this, arguments);
    };
})();
"""


def _start_xvfb() -> Optional[subprocess.Popen]:
    """Start virtual display on Linux. Returns process handle or None on macOS/Windows."""
    if platform.system() != "Linux":
        return None
    proc = subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


@asynccontextmanager
async def launch_browser() -> AsyncIterator[tuple[Browser, BrowserContext, Page]]:
    """
    Async context manager: launches Chromium headful (Xvfb on Linux) with fake
    media devices. Yields (browser, context, page). Cleans up on exit.

    Usage:
        async with launch_browser() as (browser, context, page):
            await page.goto(url)
    """
    xvfb = _start_xvfb() if not HEADLESS else None
    env = {"DISPLAY": ":99"} if (platform.system() == "Linux" and not HEADLESS) else {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            env=env,
            args=BROWSER_FLAGS,
        )
        context = await browser.new_context()
        # Block btn:// protocol navigations before any page script runs.
        # Telemost automatically does window.location.href='btn://...' on load to
        # try opening the native app — this triggers a macOS/Linux OS dialog.
        # Patching Location.prototype via Object.getPrototypeOf avoids the dialog;
        # Telemost's own fallback timer then shows the web join form normally.
        await context.add_init_script(_MEDIA_MUTE_SCRIPT)
        await context.add_init_script(_BTN_BLOCKER_SCRIPT)
        page = await context.new_page()
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()

    if xvfb is not None:
        xvfb.terminate()
        xvfb.wait()
