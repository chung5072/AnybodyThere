from typing import Union

# CONTROL PIR SENSOR
import RPi.GPIO as GPIO
# GET DATA FROM PIR SENSOR AT SPECIFIC TIME
import time
# RUN FAST-API SERVER
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, WebSocket
from fastapi.responses import HTMLResponse
# TEMPLATES FOR HTML
from fastapi.templating import Jinja2Templates
# SEND DATA FROM FAST-API TO JAVASCRIPT
import json
import websockets
import asyncio

# SET PIR SENSOR
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)

# FAST API APP
app = FastAPI()
# FAST API HTML TEMPLATE
templates = Jinja2Templates(directory="templates")

# SET PIR VALUE
pirVal = 1
# SET WEBSOCKET
websocket_clients = set()

# GET DATA FROM PIR SENSOR
async def pirCheck(background_tasks: BackgroundTasks):
    global pirVal
    # LOOP FOR GETTING DATA FROM PIR SENSOR
    while True:
        # PIR SENSOR NUM
        input = GPIO.input(17)
        # THERE IS SOMEONE
        if input == 1:
             pirVal = 1
        # NOONE
        else:
            pirVal = 0
        # PRINT FOR DEBUG
        print(f"pirVal-test: {pirVal}")
        await send_pir_value_to_clients()
        await asyncio.sleep(2)

async def send_pir_value_to_clients():
    if websocket_clients:
        message = json.dumps({"anybodyThere": pirVal})
        for client in websocket_clients:
            await client.send_text(message)
        print("message send to clients:", message)

# PIR SENSOR FUNCTION BACKGROUN RUNNING
@app.on_event("startup")
def startup_event():
    background_tasks = BackgroundTasks()
    asyncio.create_task(pirCheck(background_tasks))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except websockets.exceptions.ConnectionClosedOK:
        websocket_clients.remove(websocket)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "./index.html",
        {
            "request": request
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)