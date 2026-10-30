import asyncio
import base64
import json
import sys
import urllib.request
import aiomqtt
import numpy as np

MQTT_BROKER = "localhost"
MQTT_TOPIC = "photobox/alerts"
IMAGE_RAW_URL = "http://localhost:8000/image.raw"


def print_kitty_rgb565(raw_bytes: bytes):
    """Unpack 320x240 big-endian RGB565 into RGB24 and render via Kitty graphics protocol."""
    # 16-bit big-endian array -> (240, 320)
    pixels = np.frombuffer(raw_bytes, dtype=">u2").reshape((240, 320))

    # Bit-shift unpack: 5 bits red, 6 bits green, 5 bits blue
    r = ((pixels >> 11) & 0x1F) << 3
    g = ((pixels >> 5) & 0x3F) << 2
    b = (pixels & 0x1F) << 3

    # Interleave into 24-bit RGB array
    rgb24 = np.stack([r, g, b], axis=-1).astype(np.uint8)
    encoded_data = base64.b64encode(rgb24.tobytes()).decode("ascii")

    # Kitty graphics protocol: f=24 (24-bit RGB), s=320 (width), v=240 (height)
    sys.stdout.write(f"\033_Ga=T,f=24,s=320,v=240;{encoded_data}\033\\\n")
    sys.stdout.flush()


async def main():
    print("Starting MQTT listener... 🎧")
    async with aiomqtt.Client(MQTT_BROKER) as client:
        await client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC} 📡")

        async for message in client.messages:
            payload = json.loads(message.payload.decode())
            image_id = payload.get("image_id")
            print(f"MQTT Alert: New frame available (ID: {image_id}) 📥")

            try:
                with urllib.request.urlopen(IMAGE_RAW_URL) as resp:
                    raw_bytes = resp.read()

                with open("downloaded_box.bin", "wb") as f:
                    f.write(raw_bytes)

                print(f"Saved {len(raw_bytes)} bytes to downloaded_box.bin ✨")
                print_kitty_rgb565(raw_bytes)

            except Exception as e:
                print(f"Failed to fetch image: {e} ⚠️")


if __name__ == "__main__":
    asyncio.run(main())
