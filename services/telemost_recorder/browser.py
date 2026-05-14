import os
import platform
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from services.telemost_recorder.config import BROWSER_FLAGS, HEADLESS

# Injected into every page before any site script runs.
# Intercepts all three ways JS can navigate to a custom protocol URL.
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

# Disables audio on all MediaStream tracks produced by getUserMedia.
# --use-fake-device-for-media-stream emits a 440 Hz tone; this mutes it
# at the WebRTC level before Telemost can transmit it to other participants.
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
    Async context manager: launches Chromium headless with fake media devices
    and silenced audio. Yields (browser, context, page). Cleans up on exit.

    Usage:
        async with launch_browser() as (browser, context, page):
            await page.goto(url)
    """
    xvfb = _start_xvfb() if not HEADLESS else None
    env: dict[str, str] = {}
    if platform.system() == "Linux" and not HEADLESS:
        env["DISPLAY"] = ":99"
        # Chrome finds PulseAudio via dlopen(libpulse.so.0); it reads PULSE_SERVER
        # to locate the socket. Without this, it silently falls back to null audio.
        pulse_server = os.environ.get("PULSE_SERVER", "")
        if not pulse_server:
            try:
                result = subprocess.run(
                    ["pactl", "info"], capture_output=True, text=True, timeout=3
                )
                for line in result.stdout.splitlines():
                    if line.startswith("Server String:"):
                        pulse_server = line.split(":", 1)[1].strip()
                        break
            except Exception:
                pass
        if pulse_server:
            env["PULSE_SERVER"] = pulse_server
        # AudioCapture exports PULSE_SINK so Chrome routes output to our null-sink.
        # Without this, Chrome falls back to PulseAudio's "default" which isn't
        # always our sink even after `pactl set-default-sink`.
        pulse_sink = os.environ.get("PULSE_SINK", "")
        if pulse_sink:
            env["PULSE_SINK"] = pulse_sink

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
        await context.add_init_script(_BTN_BLOCKER_SCRIPT)
        # Mute the fake 440 Hz tone from --use-fake-device-for-media-stream.
        await context.add_init_script(_MEDIA_MUTE_SCRIPT)
        page = await context.new_page()
        # Default Playwright locator timeout = 30 секунд. Это плохо подходит для
        # join.py, где is_visible() гоняется в горячем цикле каждые 0.5с —
        # один зависший selector задерживал детект состояния на половину минуты.
        # 5 секунд достаточно для самой медленной попытки react-рендера и
        # совпадает с верхней границей наших explicit timeout=200/300/500 вызовов.
        page.set_default_timeout(5000)
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()

    if xvfb is not None:
        xvfb.terminate()
        xvfb.wait()
