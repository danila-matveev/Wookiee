#!/usr/bin/env python3
"""Export a Playwright storage_state for a Yandex 360 Business user.

One-time tool. Run on your Mac. Opens a real Chromium window, lets you log in
to passport.yandex.ru, then dumps cookies + localStorage to a JSON file. Copy
that file to the production server and point TELEMOST_STORAGE_STATE_PATH at
it — the recorder will then join Telemost as an authenticated participant and
stop getting kicked by Yandex anti-bot.

Usage:
    python scripts/telemost_export_cookies.py [--out data/telemost_storage_state.json]

Flow:
    1. Chromium opens to https://passport.yandex.ru/
    2. You log in (recorder@wookiee.shop or whichever Yandex 360 user)
    3. Script auto-navigates to https://telemost.yandex.ru/ to seed those
       cookies + localStorage too
    4. Return to this terminal, press Enter
    5. JSON file is saved
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright  # noqa: E402


_DEFAULT_OUT = PROJECT_ROOT / "data" / "telemost_storage_state.json"


_LOGIN_SELECTORS = (
    "input[name='login']",
    "input#passp-field-login",
    "input[autocomplete='username']",
    "input[data-t='field:input-login']",
    "input[type='email']",
)
_PASSWORD_SELECTORS = (
    "input[name='passwd']",
    "input#passp-field-passwd",
    "input[autocomplete='current-password']",
    "input[data-t='field:input-passwd']",
    "input[type='password']",
)
_SUBMIT_SELECTORS = (
    "button[type='submit']",
    "button[data-t='button:action:submit']",
    "button[data-t='button:action']",
)


async def _fill_first_match(page, selectors: tuple[str, ...], value: str, timeout_ms: int) -> bool:
    """Try a list of selectors; fill the first one that becomes visible. Returns True on success."""
    deadline_attempts = max(1, timeout_ms // (200 * len(selectors)))
    for _ in range(deadline_attempts):
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=200):
                    await loc.fill(value)
                    return True
            except Exception:
                continue
        await asyncio.sleep(0.5)
    return False


async def _click_first_match(page, selectors: tuple[str, ...]) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=500):
                await loc.click()
                return True
        except Exception:
            continue
    return False


async def _auto_login(page, login: str, password: str, debug_dir: Path) -> bool:
    """Best-effort auto-fill of the Yandex passport login form. Returns True
    when the page leaves passport.yandex.ru/auth (login succeeded), False if
    we never get off auth within the timeout window.

    Design: never blocks on stdin — when run from a non-interactive harness
    (like Claude Code's Bash tool), there is no terminal for the operator
    to press Enter in. Instead the script auto-fills what it can, leaves
    the browser open, and watches the URL for up to 7 minutes. The operator
    interacts with the live Chromium window if Yandex throws a captcha,
    SMS, or new form layout. On selector mismatch we still wait for URL
    change because the operator can finish the form by hand in the window.
    """
    await page.goto("https://passport.yandex.ru/auth", wait_until="domcontentloaded")
    await asyncio.sleep(2)  # let React hydrate

    # Username step. If selectors don't match — operator handles it in the window.
    filled_login = await _fill_first_match(page, _LOGIN_SELECTORS, login, timeout_ms=15_000)
    if filled_login:
        await _click_first_match(page, _SUBMIT_SELECTORS)
        await asyncio.sleep(1.5)
    else:
        await _dump_debug(page, debug_dir, "login_form_not_found")
        print("WARN: did not find the login input automatically. Layout may have changed.")
        print(f"      Debug screenshot+HTML saved to {debug_dir}.")
        print("      Continue the login manually in the open Chromium window.")

    # Password step. Same fallback.
    filled_pw = await _fill_first_match(page, _PASSWORD_SELECTORS, password, timeout_ms=15_000)
    if filled_pw:
        await _click_first_match(page, _SUBMIT_SELECTORS)
    elif filled_login:
        # Login was auto-filled but password field never appeared — likely
        # captcha or "send code to phone" interstitial. Operator solves it.
        await _dump_debug(page, debug_dir, "password_form_not_found")
        print("WARN: did not see the password field automatically — captcha or SMS likely.")
        print("      Finish the login flow in the Chromium window.")

    # The only reliable "logged in" signal is the Session_id cookie. Just
    # leaving /auth is not enough — Yandex commonly redirects to phone-binding
    # ("введите номер телефона"), forced password change for first-login of a
    # Yandex 360 employee, or a captcha-cleared-but-not-authed page, none of
    # which set Session_id. Poll the cookie jar instead.
    context = page.context
    print(">> Waiting for Session_id cookie (up to 7 minutes). Solve captcha/SMS/phone-bind in the open Chromium window.")
    import time as _time
    deadline = _time.monotonic() + 420
    while _time.monotonic() < deadline:
        cookies = await context.cookies()
        if any(c.get("name") == "Session_id" and "yandex" in c.get("domain", "") for c in cookies):
            return True
        await asyncio.sleep(2)
    await _dump_debug(page, debug_dir, "login_timeout_no_session_id")
    print(f"      Final URL: {page.url}")
    return False


async def _dump_debug(page, debug_dir: Path, label: str) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    try:
        await page.screenshot(path=str(debug_dir / f"{label}.png"))
    except Exception:  # noqa: BLE001
        pass
    try:
        html = await page.content()
        (debug_dir / f"{label}.html").write_text(html, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


async def _run(out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    login = os.environ.get("TELEMOST_LOGIN", "").strip()
    password = os.environ.get("TELEMOST_PASSWORD", "")
    auto_mode = bool(login and password)

    print("=" * 70)
    print("  Telemost cookie export — Yandex 360 Business")
    print("=" * 70)
    print()
    if auto_mode:
        print(f"Auto-login mode (TELEMOST_LOGIN={login}).")
        print("Chromium window will open — if Yandex asks for captcha or SMS,")
        print("solve it in that window. The script auto-saves once login completes.")
    else:
        print("Interactive mode. In the Chromium window that opens:")
        print("  1. Log in via passport.yandex.ru with your bot account")
        print("  2. Pass any captcha / SMS / 2FA prompts")
        print("  3. Once on your inbox / personal page — return here, press Enter")
    print()
    print(f"Output will be written to: {out_path}")
    print()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        if auto_mode:
            debug_dir = out_path.parent / "telemost_export_debug"
            ok = await _auto_login(page, login, password, debug_dir)
            if not ok:
                print("ERROR: auto-login did not complete. Aborting without saving.")
                await context.close()
                await browser.close()
                return 2
            print(">> Login detected (left passport.yandex.ru). Seeding Telemost cookies...")
        else:
            try:
                await page.goto("https://passport.yandex.ru/", wait_until="domcontentloaded")
            except Exception as exc:  # noqa: BLE001
                print(f"WARN: initial navigation failed ({exc}). Type the URL by hand.")
            print(">> When you've finished logging in, press Enter here to save cookies...")
            await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

        # Seed Telemost cookies + localStorage by visiting the SPA at least once.
        # Some Telemost auth bits live in localStorage of telemost.yandex.ru,
        # not just *.yandex.ru cookies, so this step is load-bearing.
        try:
            await page.goto("https://telemost.yandex.ru/", wait_until="domcontentloaded", timeout=15_000)
            await asyncio.sleep(2)  # let the SPA hydrate / set localStorage
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: could not visit telemost.yandex.ru ({exc}). Saving anyway.")

        state = await context.storage_state()
        await context.close()
        await browser.close()

    out_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    cookies = state.get("cookies", [])
    origins = state.get("origins", [])
    yandex_cookies = [c for c in cookies if "yandex" in c.get("domain", "")]
    has_session = any(c.get("name") == "Session_id" for c in yandex_cookies)

    print()
    print("=" * 70)
    print(f"Saved: {out_path}")
    print(f"  cookies: {len(cookies)} total, {len(yandex_cookies)} for *.yandex.*")
    print(f"  origins with localStorage: {len(origins)}")
    if not has_session:
        print()
        print("WARNING: did not see a Session_id cookie for yandex.ru.")
        print("You may not be fully logged in. Re-run and complete the login flow.")
        return 1
    print()
    print("Next steps:")
    print("  scp this file to the server, e.g.:")
    print(f"    scp {out_path} timeweb:/opt/wookiee/secrets/telemost_storage_state.json")
    print("  then add to the API container env (in docker-compose):")
    print("    TELEMOST_STORAGE_STATE_PATH=/opt/wookiee/secrets/telemost_storage_state.json")
    print("  and mount that path read-only into the API container.")
    print("=" * 70)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help=f"Output JSON path (default: {_DEFAULT_OUT})",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.out))


if __name__ == "__main__":
    sys.exit(main())
