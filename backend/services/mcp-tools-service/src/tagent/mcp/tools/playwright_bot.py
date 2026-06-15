"""Playwright automation to join a Teams meeting as a bot."""

import asyncio
import os
import pathlib
import sys
from datetime import datetime, timezone

from playwright.async_api import async_playwright, Page

def log(msg: str):
    """Write log to stderr to avoid corrupting MCP JSON-RPC on stdout."""
    sys.stderr.write(f"[BOT LOG] {msg}\n")
    sys.stderr.flush()


def _save_transcript(meeting_url: str, content: str) -> str:
    """Save transcript to /root/.tagent/transcripts/ and return the file path."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        # Build a safe filename from the meeting URL
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in meeting_url[-40:])
        transcript_dir = pathlib.Path("/root/.tagent/transcripts")
        transcript_dir.mkdir(parents=True, exist_ok=True)
        out_path = transcript_dir / f"transcript_{ts}_{safe}.txt"
        header = (
            f"Tagent AI Note-taker — Transcript\n"
            f"Meeting : {meeting_url}\n"
            f"Captured: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"{'─' * 60}\n\n"
        )
        out_path.write_text(header + content, encoding="utf-8")
        log(f"Transcript saved to {out_path}")
        return str(out_path)
    except Exception as e:
        log(f"Failed to save transcript: {e}")
        return ""

# ---------------------------------------------------------------------------
# JavaScript injected into the page to capture captions via MutationObserver.
# This is *much* more reliable than polling Playwright locators because
# Teams renders captions as transient DOM nodes that appear and disappear
# within a few seconds.
# ---------------------------------------------------------------------------
CAPTION_OBSERVER_JS = """
() => {
    // Initialise the global store
    window.__capturedCaptions = window.__capturedCaptions || [];
    window.__captionObserverActive = false;

    // Broad set of selectors that match Teams V2 caption containers.
    // Teams uses different class names / data-tid values across versions,
    // so we cast a wide net and let the MutationObserver handle it.
    const CAPTION_SELECTORS = [
        '[data-tid="closed-captions-container"]',
        '[data-tid="closed-captions-renderer"]',
        '[data-tid*="caption"]',
        '[class*="captions-"]',
        '[class*="caption-"]',
        '[class*="Captions"]',
        '[class*="Caption"]',
        '[class*="closed-caption"]',
        '[class*="cc-container"]',
        '[class*="subtitle"]',
        '[role="log"]',
        '[aria-label*="caption" i]',
        '[aria-label*="subtitle" i]',
        '[aria-live="polite"]',
        '[aria-live="assertive"]',
    ];

    function extractCaptionText(node) {
        if (!node || !node.textContent) return '';
        let text = node.textContent.trim();
        // Filter out noise — very short text or purely numeric (timestamps)
        if (text.length < 2 || /^[\\d:.]+$/.test(text)) return '';
        return text;
    }

    function scanForCaptions() {
        for (const sel of CAPTION_SELECTORS) {
            const els = document.querySelectorAll(sel);
            els.forEach(el => {
                const text = extractCaptionText(el);
                if (text) {
                    const last = window.__capturedCaptions[window.__capturedCaptions.length - 1];
                    // Deduplicate consecutive identical entries
                    if (!last || last.text !== text) {
                        window.__capturedCaptions.push({
                            text: text,
                            ts: new Date().toISOString()
                        });
                    }
                }
            });
        }
    }

    // Perform an initial scan
    scanForCaptions();

    // Set up a MutationObserver on the whole document body
    if (!window.__captionObserverActive) {
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                // Check added nodes
                for (const node of mutation.addedNodes) {
                    if (node.nodeType !== Node.ELEMENT_NODE) continue;
                    const text = extractCaptionText(node);
                    if (text) {
                        const last = window.__capturedCaptions[window.__capturedCaptions.length - 1];
                        if (!last || last.text !== text) {
                            window.__capturedCaptions.push({
                                text: text,
                                ts: new Date().toISOString()
                            });
                        }
                    }
                    // Also check children of added nodes
                    const children = node.querySelectorAll ? node.querySelectorAll('*') : [];
                    children.forEach(child => {
                        const ct = extractCaptionText(child);
                        if (ct) {
                            const last = window.__capturedCaptions[window.__capturedCaptions.length - 1];
                            if (!last || last.text !== ct) {
                                window.__capturedCaptions.push({
                                    text: ct,
                                    ts: new Date().toISOString()
                                });
                            }
                        }
                    });
                }
                // Check text changes in existing nodes (characterData)
                if (mutation.type === 'characterData') {
                    const text = (mutation.target.textContent || '').trim();
                    if (text.length >= 2 && !/^[\\d:.]+$/.test(text)) {
                        const last = window.__capturedCaptions[window.__capturedCaptions.length - 1];
                        if (!last || last.text !== text) {
                            window.__capturedCaptions.push({
                                text: text,
                                ts: new Date().toISOString()
                            });
                        }
                    }
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
            characterDataOldValue: true,
        });

        window.__captionObserverActive = true;
    }
    return 'Caption observer installed';
}
"""

COLLECT_CAPTIONS_JS = """
() => {
    const captions = window.__capturedCaptions || [];
    // Clear after collecting to avoid duplicates on next poll
    window.__capturedCaptions = [];
    return captions;
}
"""

# JS to do a broad scan of the page DOM for anything that looks like captions
SCAN_DOM_FOR_CAPTIONS_JS = """
() => {
    const results = [];
    // Look for elements with aria-live (screen reader updates, used by captions)
    document.querySelectorAll('[aria-live]').forEach(el => {
        const text = el.textContent.trim();
        if (text.length > 5) results.push({selector: 'aria-live', text: text.substring(0, 200)});
    });
    // Look for anything with "caption" in class/data attributes
    document.querySelectorAll('[class*="caption" i], [data-tid*="caption" i]').forEach(el => {
        const text = el.textContent.trim();
        if (text.length > 2) results.push({selector: 'caption-class', text: text.substring(0, 200)});
    });
    // Look for role="log" regions (chat, captions)
    document.querySelectorAll('[role="log"]').forEach(el => {
        const text = el.textContent.trim();
        if (text.length > 2) results.push({selector: 'role-log', text: text.substring(0, 200)});
    });
    // Look for aria-label containing "subtitle" or "transcript"
    document.querySelectorAll('[aria-label*="subtitle" i], [aria-label*="transcript" i]').forEach(el => {
        const text = el.textContent.trim();
        if (text.length > 2) results.push({selector: 'aria-subtitle', text: text.substring(0, 200)});
    });
    return results;
}
"""


async def join_teams_meeting(meeting_url: str, duration_seconds: int = 30) -> str:
    """
    Joins a Teams meeting using an invisible browser, waits for the duration, 
    and tries to extract captions.
    """
    log(f"Starting Playwright to join: {meeting_url}")
    
    # Resolve the Y4M avatar file path — same directory as this module.
    # Docker copies it alongside the source; local runs use the same path.
    _here = pathlib.Path(__file__).parent
    _y4m = _here / "notetaker_avatar.y4m"
    avatar_arg = f"--use-file-for-fake-video-capture={_y4m}" if _y4m.exists() else "--use-fake-device-for-media-stream"
    log(f"Camera source: {avatar_arg}")

    async with async_playwright() as p:
        # Launch browser with stealth and media flags
        browser = await p.chromium.launch(headless=True, args=[
            "--use-fake-ui-for-media-stream",  # Auto-grant mic/cam permissions
            "--use-fake-device-for-media-stream",
            avatar_arg,                         # Custom avatar image as camera feed
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
        ])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        # Grant permissions for camera and microphone (needed for Teams)
        await context.grant_permissions(["camera", "microphone"])
        
        page = await context.new_page()
        
        # Disable webdriver property to bypass bot detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        """)
        
        # Force web join by modifying the URL.
        # The new Teams short-link format (meet/) needs launchinbrowser to skip
        # the "Open in app?" interstitial that blocks headless browsers.
        if "teams.microsoft.com" in meeting_url:
            meeting_url = meeting_url.replace("&msLaunch=true", "")
            sep = "&" if "?" in meeting_url else "?"
            meeting_url += f"{sep}webjoin=true&suppressPrompt=true&launchinbrowser=true"

        # Navigate to the meeting URL.
        # Use domcontentloaded — Teams is a live SPA so networkidle NEVER fires
        # and always burns the full 60-second timeout before falling back.
        log("Navigating to meeting URL...")
        try:
            await page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            log("goto timed out (domcontentloaded), continuing anyway...")
        log("Navigated to meeting URL.")

        # Short pause for the SPA to hydrate — 2 s is enough after domcontentloaded
        await asyncio.sleep(2)
        
        # Take a debug screenshot to see what loaded
        debug_path = "/root/.tagent/teams_debug_loaded.png"
        try:
            os.makedirs("/root/.tagent", exist_ok=True)
            await page.screenshot(path=debug_path)
            log(f"Debug screenshot after load saved to {debug_path}")
        except Exception:
            pass

        # ── Step 0: Handle "Classic Teams is no longer available" error ───
        # Microsoft deprecated Classic Teams; if we land on the error page,
        # click "Use Teams on the web" to get to the new Teams v2.
        try:
            classic_teams_error = page.locator("h1:has-text('Classic Teams is no longer available')")
            if await classic_teams_error.count() > 0:
                log("Detected 'Classic Teams is no longer available' error page. Clicking 'Use Teams on the web'...")
                web_btn = page.locator("a#open-teams-on-web, a:has-text('Use Teams on the web')")
                if await web_btn.count() > 0:
                    await web_btn.first.click()
                    log("Clicked 'Use Teams on the web'. Waiting for redirect...")
                    await asyncio.sleep(3)
                    # Now navigate to the meeting URL again but with v2 path
                    v2_url = meeting_url.replace("teams.microsoft.com/", "teams.microsoft.com/v2/")
                    log(f"Navigating to Teams v2 URL: {v2_url}")
                    await page.goto(v2_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
        except Exception as e:
            log(f"Classic Teams error handler failed (non-fatal): {e}")

        # ── Step 1: Click "Continue on this browser" ──────────────────────
        # Teams V2 sometimes redirects and takes a long time to render.
        # We use a polling loop to keep checking for the button.
        continue_clicked = False
        for attempt in range(10):  # Try for up to 20 seconds (10 x 2s)
            try:
                continue_btn = page.locator(
                    "button:has-text('Continue on this browser'), "
                    "button:has-text('Join on the web'), "
                    "button:has-text('Continue here'), "
                    "a:has-text('Continue on this browser'), "
                    "a:has-text('Join on the web'), "
                    "[data-tid='joinOnWeb']"
                )
                if await continue_btn.count() > 0:
                    await continue_btn.first.click(force=True)
                    log("Clicked 'Continue on this browser'.")
                    continue_clicked = True
                    break
            except Exception:
                pass
            log(f"Waiting for 'Continue on this browser'... (attempt {attempt + 1}/10)")
            await asyncio.sleep(2)

        if not continue_clicked:
            log("'Continue on this browser' button not found. Checking if we went directly to pre-join...")

        # Short pause for the pre-join screen to render
        await asyncio.sleep(1)
        
        # Take another debug screenshot
        debug_path2 = "/root/.tagent/teams_debug_prejoin.png"
        try:
            await page.screenshot(path=debug_path2)
            log(f"Debug screenshot at pre-join saved to {debug_path2}")
        except Exception:
            pass
        
        # Log current URL for debugging
        log(f"Current URL: {page.url}")
        
        # ── Step 2: Enter name and join ───────────────────────────────────
        try:
            # Use a polling approach for the name input too
            name_input = None
            for attempt in range(15):  # Try for up to 30 seconds (15 x 2s)
                # Try multiple selectors — new Teams uses different data-tids
                for selector in [
                    "input[data-tid='prejoin-display-name-input']",
                    "input[data-tid*='name']",
                    "input[id='username']",
                    "input[id='guestName']",
                    "input[placeholder*='name' i]",
                    "input[aria-label*='name' i]",
                    "input[type='text']:visible",
                    "input[type='text']",
                ]:
                    try:
                        loc = page.locator(selector)
                        if await loc.count() > 0 and await loc.first.is_visible():
                            name_input = loc.first
                            log(f"Found name input with selector: {selector}")
                            break
                    except Exception:
                        continue

                if name_input:
                    break

                log(f"Waiting for name input... (attempt {attempt + 1}/15)")
                await asyncio.sleep(2)
            
            if not name_input:
                raise Exception("Could not find name input after 30 seconds of polling")
            
            # Turn off camera and mic if the toggles exist
            try:
                cam_toggle = page.locator("button[aria-label*='camera' i], button[aria-label*='video' i], div[role='checkbox'][aria-label*='video']")
                if await cam_toggle.count() > 0 and await cam_toggle.first.is_visible():
                    checked = await cam_toggle.first.get_attribute("aria-checked") or await cam_toggle.first.get_attribute("aria-pressed")
                    if checked == "true":
                        await cam_toggle.first.click()
                        log("Turned off camera.")
            except Exception:
                pass
                
            try:
                mic_toggle = page.locator("button[aria-label*='microphone' i], button[aria-label*='mic' i], div[role='checkbox'][aria-label*='microphone']")
                if await mic_toggle.count() > 0 and await mic_toggle.first.is_visible():
                    checked = await mic_toggle.first.get_attribute("aria-checked") or await mic_toggle.first.get_attribute("aria-pressed")
                    if checked == "true":
                        await mic_toggle.first.click()
                        log("Turned off microphone.")
            except Exception:
                pass

            # Enter bot name
            await name_input.fill("Tagent AI Note-taker")
            log("Entered bot name.")
            
            # Click Join — try multiple selectors
            join_clicked = False
            for join_sel in [
                "button[data-tid='prejoin-join-button']",
                "button:has-text('Join now')",
                "button:has-text('Join meeting')",
                "button:has-text('Join')",
            ]:
                try:
                    join_btn = page.locator(join_sel)
                    if await join_btn.count() > 0 and await join_btn.first.is_visible():
                        await join_btn.first.click()
                        join_clicked = True
                        log(f"Clicked join button with selector: {join_sel}")
                        break
                except Exception:
                    continue
            
            if not join_clicked:
                log("Could not find Join button, pressing Enter as fallback...")
                await page.keyboard.press("Enter")
            
            log("Waiting to be admitted...")
            
        except Exception as e:
            log(f"Failed at pre-join screen: {e}")
            error_path = "/root/.tagent/teams_error.png"
            try:
                await page.screenshot(path=error_path)
                log(f"Screenshot saved to {error_path}")
                # Also dump the page HTML for debugging
                html_content = await page.content()
                html_path = "/root/.tagent/teams_error.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                log(f"Page HTML saved to {html_path}")
            except Exception as se:
                log(f"Failed to capture debug info: {se}")
            await browser.close()
            return f"Failed to join: Could not navigate the pre-join screen. (Screenshot saved to {error_path})"

        # ── Step 3: Wait to enter the meeting ─────────────────────────────
        log("Waiting to be admitted to the meeting...")
        
        in_meeting = False
        for attempt in range(30):  # Wait up to 60 seconds (30 x 2s)
            try:
                # Check multiple indicators that we're in the meeting
                for indicator_sel in [
                    "button[id='more-button']",
                    "button[aria-label*='More' i]",
                    "button[data-tid='more-actions-menu']",
                    "button[aria-label*='Leave' i]",
                    "button[data-tid='hangup-button']",
                    "#hangup-button",
                ]:
                    loc = page.locator(indicator_sel)
                    if await loc.count() > 0 and await loc.first.is_visible():
                        log(f"In meeting! Detected via: {indicator_sel}")
                        in_meeting = True
                        break
            except Exception:
                pass
            
            if in_meeting:
                break
            log(f"Still waiting to enter meeting... (attempt {attempt + 1}/30)")
            await asyncio.sleep(2)
        
        if not in_meeting:
            error_path = "/root/.tagent/teams_lobby_timeout.png"
            try:
                await page.screenshot(path=error_path)
            except Exception:
                pass
            await browser.close()
            return "Failed to enter meeting: Timed out waiting in the lobby. The meeting host may need to admit the bot."

        log("Successfully entered the meeting!")

        # Take in-meeting screenshot for debugging
        try:
            meeting_ss_path = "/root/.tagent/teams_in_meeting.png"
            await page.screenshot(path=meeting_ss_path)
            log(f"In-meeting screenshot saved to {meeting_ss_path}")
        except Exception:
            pass

        # ── Step 4: Enable live captions ──────────────────────────────────
        # Strategy: Try multiple approaches to enable captions since Teams V2
        # keeps changing the menu structure.
        captions_enabled = False
        
        # Approach 1: More menu → Language and speech → Turn on live captions
        try:
            more_btn = page.locator(
                "button[id='more-button'], "
                "button[aria-label*='More' i], "
                "button[data-tid='more-actions-menu']"
            )
            if await more_btn.count() > 0:
                await more_btn.first.click()
                log("Clicked More actions button.")
                await asyncio.sleep(2)

                # Take screenshot of More menu for debugging
                try:
                    await page.screenshot(path="/root/.tagent/teams_more_menu.png")
                    log("Screenshot of More menu saved.")
                except Exception:
                    pass
                
                # Dump the menu items for debugging
                try:
                    menu_items = await page.evaluate("""
                        () => {
                            const items = [];
                            // Check for menu items / list items
                            document.querySelectorAll('[role="menuitem"], [role="menuitemcheckbox"], [role="option"], li').forEach(el => {
                                const text = el.textContent.trim();
                                if (text.length > 0 && text.length < 100) items.push(text);
                            });
                            return items;
                        }
                    """)
                    log(f"Menu items found: {menu_items}")
                except Exception as e:
                    log(f"Could not dump menu items: {e}")

                # Try clicking "Language and speech" submenu (Teams V2 new layout)
                lang_clicked = False
                for lang_sel in [
                    "text='Language and speech'",
                    "[data-tid*='language']",
                    "span:has-text('Language and speech')",
                    "[role='menuitem']:has-text('Language')",
                    "[role='menuitemcheckbox']:has-text('Language')",
                ]:
                    try:
                        lang_btn = page.locator(lang_sel)
                        if await lang_btn.count() > 0 and await lang_btn.first.is_visible():
                            await lang_btn.first.click()
                            log(f"Clicked 'Language and speech' via: {lang_sel}")
                            lang_clicked = True
                            await asyncio.sleep(1)
                            break
                    except Exception:
                        continue

                # Now look for captions toggle
                for cc_sel in [
                    "text='Turn on live captions'",
                    "text='Live captions'",
                    "[role='menuitem']:has-text('captions')",
                    "[role='menuitemcheckbox']:has-text('captions')",
                    "button:has-text('captions')",
                    "span:has-text('Turn on live captions')",
                    "span:has-text('Live captions')",
                    "[data-tid*='captions']",
                    "[data-tid*='live-caption']",
                ]:
                    try:
                        cc_btn = page.locator(cc_sel)
                        if await cc_btn.count() > 0 and await cc_btn.first.is_visible():
                            await cc_btn.first.click()
                            log(f"Turned on live captions via: {cc_sel}")
                            captions_enabled = True
                            break
                    except Exception:
                        continue

                if not captions_enabled and not lang_clicked:
                    log("Captions button not found in More menu. Trying keyboard shortcut...")
                
                # Close the menu if it's still open by pressing Escape
                try:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
                    
        except Exception as e:
            log(f"Could not enable captions via More menu: {e}")

        # Approach 2: Keyboard shortcut Ctrl+Shift+U (toggle captions in Teams)
        if not captions_enabled:
            try:
                await page.keyboard.press("Control+Shift+U")
                log("Sent Ctrl+Shift+U keyboard shortcut for captions.")
                await asyncio.sleep(2)
            except Exception as e:
                log(f"Keyboard shortcut failed: {e}")

        # Wait for captions container to appear
        await asyncio.sleep(3)

        # Take screenshot after enabling captions
        try:
            await page.screenshot(path="/root/.tagent/teams_captions_enabled.png")
            log("Screenshot after captions toggle saved.")
        except Exception:
            pass

        # ── Step 5: Inject MutationObserver and scrape captions ───────────
        log(f"Injecting caption observer and listening for {duration_seconds} seconds...")

        # Inject the MutationObserver
        try:
            result = await page.evaluate(CAPTION_OBSERVER_JS)
            log(f"Caption observer injection result: {result}")
        except Exception as e:
            log(f"Failed to inject caption observer: {e}")

        # Do an initial DOM scan to see what caption-like elements exist
        try:
            dom_scan = await page.evaluate(SCAN_DOM_FOR_CAPTIONS_JS)
            if dom_scan:
                log(f"DOM scan found {len(dom_scan)} caption-like elements:")
                for item in dom_scan[:10]:
                    log(f"  [{item.get('selector')}] {item.get('text', '')[:100]}")
            else:
                log("DOM scan: No caption-like elements found yet.")
        except Exception as e:
            log(f"DOM scan failed: {e}")

        # Now poll for captions using both the MutationObserver results
        # AND traditional locator-based scraping as a fallback
        start_time = asyncio.get_event_loop().time()
        all_captions = []
        poll_count = 0
        
        while (asyncio.get_event_loop().time() - start_time) < duration_seconds:
            await asyncio.sleep(2)
            poll_count += 1
            
            # Method 1: Collect from MutationObserver
            try:
                observer_captions = await page.evaluate(COLLECT_CAPTIONS_JS)
                if observer_captions:
                    for cap in observer_captions:
                        text = cap.get("text", "").strip()
                        ts = cap.get("ts", "")
                        if text and len(text) > 2:
                            all_captions.append(f"[{ts}] {text}")
                            log(f"Observer captured: {text[:80]}")
            except Exception as e:
                if poll_count <= 2:
                    log(f"Observer poll error: {e}")

            # Method 2: Traditional locator scraping (fallback)
            try:
                for loc_sel in [
                    "[data-tid='closed-captions-container']",
                    "[data-tid='closed-captions-renderer']",
                    "[data-tid*='caption-text']",
                    "[data-tid*='caption'] span",
                    "[class*='captions-'] span",
                    "[class*='caption-'] span",
                    "[class*='Captions'] span",
                    "[aria-label*='caption' i]",
                    "[aria-live='polite']",
                    "[aria-live='assertive']",
                ]:
                    loc = page.locator(loc_sel)
                    count = await loc.count()
                    if count > 0:
                        texts = await loc.all_inner_texts()
                        for t in texts:
                            t = t.strip()
                            if t and len(t) > 2 and not any(t in c for c in all_captions[-20:]):
                                all_captions.append(f"[locator:{loc_sel}] {t}")
                                log(f"Locator captured ({loc_sel}): {t[:80]}")
            except Exception:
                pass

            # Periodic logging
            if poll_count % 5 == 0:
                log(f"  ... {poll_count} polls done, {len(all_captions)} caption entries so far, "
                    f"{int(duration_seconds - (asyncio.get_event_loop().time() - start_time))}s remaining")

                # Re-inject observer in case Teams re-rendered the page
                try:
                    await page.evaluate(CAPTION_OBSERVER_JS)
                except Exception:
                    pass

                # Periodic DOM scan
                try:
                    dom_scan = await page.evaluate(SCAN_DOM_FOR_CAPTIONS_JS)
                    if dom_scan:
                        log(f"  DOM scan: {len(dom_scan)} elements")
                        for item in dom_scan[:3]:
                            log(f"    [{item.get('selector')}] {item.get('text', '')[:80]}")
                except Exception:
                    pass

        # Take a final screenshot
        try:
            await page.screenshot(path="/root/.tagent/teams_final.png")
            log("Final meeting screenshot saved.")
        except Exception:
            pass

        # Dump the full page HTML for offline debugging if no captions found
        if not all_captions:
            try:
                html_content = await page.content()
                html_path = "/root/.tagent/teams_meeting_dom.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                log(f"Full meeting DOM saved to {html_path} for debugging.")
            except Exception:
                pass

        log("Meeting duration finished. Leaving...")
        await browser.close()
        
        # ── Build the final transcript ────────────────────────────────────
        if not all_captions:
            no_captions_msg = (
                "Bot successfully joined the meeting.\n"
                "Note: No captions were detected.\n"
                "Recommendations:\n"
                "- Ensure live captions are activated in the meeting to enable transcription or further caption functionality.\n"
                "- The bot user needs to manually turn on captions (Ctrl+Shift+U in Teams) if the 'More menu' approach failed.\n"
                "- Check the debug screenshots at /root/.tagent/ and the DOM dump for clues.\n"
                "- Teams may require a signed-in user for captions to appear in the web client."
            )
            _save_transcript(meeting_url, no_captions_msg)
            return no_captions_msg
        
        # Deduplicate consecutive entries while preserving order
        deduped = []
        last = ""
        for line in all_captions:
            # Strip the timestamp/selector prefix for comparison
            text_only = line.split("] ", 1)[-1] if "] " in line else line
            if text_only != last:
                deduped.append(line)
                last = text_only
        
        final_transcript = "\n".join(deduped)
        saved_path = _save_transcript(meeting_url, final_transcript)
        saved_note = f"\n\nTranscript saved to: {saved_path}" if saved_path else ""
        return f"Transcript successfully captured ({len(deduped)} entries):\n\n{final_transcript}{saved_note}"
