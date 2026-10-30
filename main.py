import io
import os
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

import aiofiles
import aiomqtt
import aiomqtt.client
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class BoxID(str, Enum):
    MARCOS = "MARCOS"
    JUANMA = "JUANMA"


class Settings(BaseSettings):
    mqtt_broker: str = "localhost"
    mqtt_user: str = "photoBox"
    mqtt_pass: str = "pass"
    display_width: int = Field(default=320, gt=0)
    display_height: int = Field(default=240, gt=0)
    padding_color: str = "#000000"


class UploadResponse(BaseModel):
    message: str = Field(
        description="Confirmation message", examples=["Enviado a MARCOS!"]
    )
    box_id: BoxID = Field(description="Target photoBox destination")
    file_path: str = Field(description="Path where the .raw file was saved")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the upload"
    )


settings = Settings()

mqtt_client: aiomqtt.Client | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global mqtt_client
    try:
        async with aiomqtt.Client(
            settings.mqtt_broker,
            username=settings.mqtt_user,
            password=settings.mqtt_pass,
        ) as client:
            mqtt_client = client
            yield
    except (aiomqtt.MqttError, OSError) as e:
        print(f"Warning: Could not connect to MQTT broker ({e}).")
        yield


app = FastAPI(lifespan=lifespan)


def convert_to_rgb565_be(img: Image.Image) -> bytes:
    arr = np.array(img, dtype=np.uint16)

    # Arranged for BGR display panels
    r = (arr[:, :, 2] >> 3) << 11
    g = (arr[:, :, 1] >> 2) << 5
    b = arr[:, :, 0] >> 3

    rgb565 = (r | g | b).astype(">u2")
    return rgb565.tobytes()


@app.get("/", response_class=HTMLResponse)
async def upload_page():
    return Path("index.html").read_text()


@app.post("/upload", response_model=UploadResponse)
async def handle_upload(
    box_id: Annotated[BoxID, Form()],
    file: Annotated[UploadFile, File()],
):

    contents = await file.read()
    img = Image.open(io.BytesIO(contents))
    img = ImageOps.exif_transpose(img)

    img = ImageOps.pad(
        img,
        (settings.display_width, settings.display_height),
        color=settings.padding_color,
    ).convert("RGB")
    raw_bytes = convert_to_rgb565_be(img)

    file_path = f"{box_id}.raw"
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(raw_bytes)

    if mqtt_client:
        await mqtt_client.publish(box_id, payload=b"update", qos=1)

    return UploadResponse(
        message=f"Enviado a {box_id.value}! ヽ(•‿•)ノ",
        box_id=box_id,
        file_path=file_path,
    )


@app.get("/{box_id}.raw")
async def get_image(box_id: BoxID):

    file_path = f"{box_id}.raw"
    if not os.path.exists(file_path):
        return Response(status_code=404)

    return FileResponse(file_path, media_type="application/octet-stream")
