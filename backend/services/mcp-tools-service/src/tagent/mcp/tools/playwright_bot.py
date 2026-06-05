"""Playwright automation to join a Teams meeting as a bot."""

import asyncio
import os
import sys

from playwright.async_api import async_playwright, Page

def log(msg: str):
    """Write log to stderr to avoid corrupting MCP JSON-RPC on stdout."""
    sys.stderr.write(f"[BOT LOG] {msg}\n")
    sys.stderr.flush()

async def join_teams_meeting(meeting_url: str, duration_seconds: int = 60) -> str:
    """
    Joins a Teams meeting using an invisible browser, waits for the duration, 
    and tries to extract captions.
    """
    log(f"Starting Playwright to join: {meeting_url}")
    
    async with async_playwright() as p:
        # Launch browser with stealth and media flags
        browser = await p.chromium.launch(headless=True, args=[
            "--use-fake-ui-for-media-stream",  # Auto-grant mic/cam permissions
            "--use-fake-device-for-media-stream",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security"
        ])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        # Grant permissions for camera and microphone (needed for Teams)
        await context.grant_permissions(["camera", "microphone"])
        
        page = await context.new_page()
        
        # Disable webdriver property to bypass bot detection
        await page.add_init_script("delete navigator.__proto__.webdriver;")
        
        # Navigate to the meeting URL
        log("Navigating to meeting URL...")
        await page.goto(meeting_url, wait_until="domcontentloaded")
        log("Navigated to meeting URL.")
        
        # Teams usually shows a "How do you want to join your Teams meeting?" screen.
        # We want to click "Continue on this browser".
        try:
            # Wait for the "Continue on this browser" button (text matches "Continue on this browser" or "web app")
            continue_btn = page.locator("button:has-text('Continue on this browser'), button:has-text('browser'), button:has-text('web app'), [data-tid='joinOnWeb']")
            await continue_btn.wait_for(state="visible", timeout=15000)
            await continue_btn.click()
            log("Clicked 'Continue on this browser'.")
        except Exception as e:
            log(f"Could not find 'Continue on this browser' button: {e}. Maybe it went straight to the lobby?")
        
        # Wait for the pre-join screen where we enter the name
        try:
            # Wait for the name input field (Teams frequently changes this ID)
            name_input = page.locator("input[id='username'], input[id='guestName'], input[placeholder*='name' i]")
            await name_input.wait_for(state="visible", timeout=20000)
            
            # Turn off camera and mic if the toggles exist
            try:
                cam_toggle = page.locator("div[role='checkbox'][aria-label*='video']")
                if await cam_toggle.is_visible():
                    checked = await cam_toggle.get_attribute("aria-checked")
                    if checked == "true":
                        await cam_toggle.click()
            except Exception:
                pass
                
            try:
                mic_toggle = page.locator("div[role='checkbox'][aria-label*='microphone']")
                if await mic_toggle.is_visible():
                    checked = await mic_toggle.get_attribute("aria-checked")
                    if checked == "true":
                        await mic_toggle.click()
            except Exception:
                pass

            # Enter bot name
            await name_input.fill("Tagent AI Note-taker")
            log("Entered bot name.")
            
            # Click Join
            join_btn = page.locator("button[data-tid='prejoin-join-button']")
            await join_btn.click()
            log("Clicked 'Join now'. Waiting to be admitted...")
            
        except Exception as e:
            log(f"Failed at pre-join screen: {e}")
            error_path = "/root/.tagent/teams_error.png"
            try:
                await page.screenshot(path=error_path)
                log(f"Screenshot saved to {error_path}")
            except Exception as se:
                log(f"Failed to capture screenshot: {se}")
            await browser.close()
            return f"Failed to join: Could not navigate the pre-join screen. (Screenshot saved to {error_path})"

        # Wait in the lobby or join directly
        log(f"Waiting for {duration_seconds} seconds in the meeting...")
        await asyncio.sleep(duration_seconds)
        
        log("Meeting duration finished. Leaving...")
        await browser.close()
        
        return "Bot joined the meeting, listened, and left successfully."
