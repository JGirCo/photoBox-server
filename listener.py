import asyncio
import base64
import json
import sys
import urllib.request

import aiomqtt
import numpy as np
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    server_ip: str = "localhost"
    mqtt_client_name: str = "photobox-listener"
    mqtt_user: str = "photoBox"
    mqtt_pass: str = "pass"

    @property
    def image_raw_url(self) -> str:
        return f"http://{self.server_ip}:8000/{self.mqtt_client_name}.raw"


settings = Settings()


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
    async with aiomqtt.Client(
        settings.server_ip,
        identifier=settings.mqtt_client_name,
        username=settings.mqtt_user,
        password=settings.mqtt_pass,
    ) as client:
        await client.subscribe(settings.mqtt_client_name)
        print(f"Subscribed to topic: {settings.mqtt_client_name} 📡")

        async for message in client.messages:
            raw_text = message.payload.decode("utf-8")

            try:
                payload = json.loads(raw_text)
                image_id = payload.get("image_id", settings.mqtt_client_name)
            except json.JSONDecodeError:
                image_id = settings.mqtt_client_name

            print(
                f"MQTT Alert: New frame available for {message.topic} "
                f"(ID: {image_id}) ( •̀ᴗ•́ )"
            )

            try:
                with urllib.request.urlopen(settings.image_raw_url) as resp:
                    raw_bytes = resp.read()

                with open("downloaded_box.bin", "wb") as f:
                    f.write(raw_bytes)

                print(f"Saved {len(raw_bytes)} bytes to downloaded_box.bin ✨")
                print_kitty_rgb565(raw_bytes)

            except Exception as e:
                print(f"Failed to fetch image: {e} ⚠️")


if __name__ == "__main__":
    asyncio.run(main())
