import asyncio
import json
import subprocess
import time
import urllib.request
import websockets
import base64
import os

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ARTIFACTS_DIR = "/Users/vuongdoan/.gemini/antigravity/brain/57e28bef-12b9-4e40-af96-ee34fddc4213"
CDP_PORT = 9333

async def run_cdp():
    user_data = f"/tmp/chrome_cdp_profile_{int(time.time())}"
    chrome_proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data}",
        "--disable-gpu",
        "--window-size=1440,900",
        "http://127.0.0.1:7860"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        ws_url = None
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json") as r:
                    tabs = json.loads(r.read())
                    for t in tabs:
                        if "7860" in t.get("url", ""):
                            ws_url = t["webSocketDebuggerUrl"]
                            break
                    if ws_url:
                        break
            except Exception:
                await asyncio.sleep(0.3)

        if not ws_url:
            print("Failed to find tab with 7860")
            return

        print("Connected to CDP tab:", ws_url)
        async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
            msg_id = 0
            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                req = {"id": msg_id, "method": method, "params": params or {}}
                await ws.send(json.dumps(req))
                while True:
                    res = json.loads(await ws.recv())
                    if res.get("id") == msg_id:
                        return res.get("result", {})

            await send("Page.enable")
            await send("Runtime.enable")
            await send("Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False
            })

            # Wait for Gradio components to mount
            print("Waiting for components...")
            for i in range(50):
                res = await send("Runtime.evaluate", {
                    "expression": "document.querySelector('.editor textarea') !== null && document.getElementById('voice-preview-card') !== null"
                })
                ready = res.get("result", {}).get("value", False)
                if ready:
                    print(f"Components mounted after {i*0.3:.1f}s")
                    break
                await asyncio.sleep(0.3)

            await asyncio.sleep(1.2)

            # Capture 1: TTS Page with Voice Preview Card in Settings (Requirement 1 & Image 1)
            res = await send("Page.captureScreenshot", {"format": "png"})
            data1 = base64.b64decode(res["data"])
            p1 = os.path.join(ARTIFACTS_DIR, "step1_tts_voice_card.png")
            with open(p1, "wb") as f:
                f.write(data1)
            print("Saved:", p1)

            # Open Voice Selection Modal (Requirement 1 & Image 2)
            print("Opening Voice Selection Modal...")
            await send("Runtime.evaluate", {"expression": "window.openVoiceModal()"})
            await asyncio.sleep(0.8)

            res = await send("Page.captureScreenshot", {"format": "png"})
            data2 = base64.b64decode(res["data"])
            p2 = os.path.join(ARTIFACTS_DIR, "step2_voice_modal_open.png")
            with open(p2, "wb") as f:
                f.write(data2)
            print("Saved:", p2)

            # Close Modal
            await send("Runtime.evaluate", {"expression": "window.closeVoiceModal()"})
            await asyncio.sleep(0.4)

            # Switch to Dedicated Voice Creator Page (Requirement 3 & Image 4)
            print("Switching to Voice Creator Page...")
            await send("Runtime.evaluate", {"expression": "window.switchOmniVoicePage('creator')"})
            await asyncio.sleep(0.8)

            res = await send("Page.captureScreenshot", {"format": "png"})
            data3 = base64.b64decode(res["data"])
            p3 = os.path.join(ARTIFACTS_DIR, "step3_voice_creator_page.png")
            with open(p3, "wb") as f:
                f.write(data3)
            print("Saved:", p3)

            # Switch back to TTS
            await send("Runtime.evaluate", {"expression": "window.switchOmniVoicePage('tts')"})
            await asyncio.sleep(0.5)

            # Test Bottom Player Bar & History Tab display (Requirement 2 & Image 3)
            print("Triggering Bottom Player and History tab...")
            await send("Runtime.evaluate", {
                "expression": """
                window.loadBottomPlayer({
                    file_url: '/gradio_api/file=/Users/vuongdoan/.gemini/antigravity/scratch/omnivoice/presets/elon_musk_7s.wav',
                    voice_name: 'PEAKTV',
                    text: 'Chào mừng các bạn đã quay trở lại. Hôm nay, chúng ta sẽ cùng khám phá câu chuyện phía sau sự thành công của một trong những công nghệ bí ẩn nhất thế giới.',
                    avatar: '🚀',
                    duration: 7.7,
                    time_str: '01:16 · 15/10'
                }, false);
                window.switchSettingsTab('history');
                """
            })
            await asyncio.sleep(0.8)

            res = await send("Page.captureScreenshot", {"format": "png"})
            data4 = base64.b64decode(res["data"])
            p4 = os.path.join(ARTIFACTS_DIR, "step4_bottom_player_and_history.png")
            with open(p4, "wb") as f:
                f.write(data4)
            print("Saved:", p4)

    finally:
        chrome_proc.terminate()
        chrome_proc.wait()

if __name__ == "__main__":
    asyncio.run(run_cdp())
