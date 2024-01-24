from typing import Union

# MULTI-THREAD
import threading
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
# TEST
import random


# FAST API APP
app = FastAPI()
# FAST API HTML TEMPLATE
templates = Jinja2Templates(directory = "templates")

# SET PIR VALUE
pirVal = 1
# SET WEBSOCKET
websocket_clients = set()

# GET DATA FROM PIR SENSOR
def pirCheck():
    global pirVal
    # TEST CODE
    while True:
        pirVal = random.randint(0, 1)
        # PRINT FOR DEBUG
        print(f"pirVal-test: {pirVal}")
        asyncio.run()
        time.sleep(2)

async def send_pir_value_to_client():
    if websocket_clients:
        message = json.dumps({"anybodyThere": pirVal})
        await asyncio.gather(
            client.send(message) for client in websocket_clients
        )

# PIR SENSOR FUNCTION BACKGROUN RUNNING
@app.on_event("startup")
def startup_event():
    threading.Thread(target = pirCheck, daemon = True).start()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # PRINT MESSAGE FOR DEBUG
    print(f"pirVal-index: {pirVal}")
    return templates.TemplateResponse(
        "./index.html",
        {
            "request": request,
        }
    )

if __name__ == "__main__":
    startup_event()
    uvicorn.run(app, host="0.0.0.0", port=8000)


