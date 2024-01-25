from typing import Union, Set

# CONTROL PIR SENSOR
import RPi.GPIO as GPIO
# LOG
import logging
# RUN FAST-API SERVER
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, WebSocket, Cookie, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketDisconnect
# TEMPLATES FOR HTML
from fastapi.templating import Jinja2Templates
# SEND DATA FROM FAST-API TO JAVASCRIPT
import json
import websockets
import asyncio
# CREATE SESSION ID
import uuid

# SET PIR SENSOR
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)

# CONFIG LOGGIN LEVEL FOR FASTAPI
logging.basicConfig(level = logging.DEBUG)

# FAST API APP
app = FastAPI()
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# FAST API HTML TEMPLATE
templates = Jinja2Templates(directory="templates")

# SET PIR VALUE
pirVal = 1
# SET WEBSOCKET
websocket_clients: Set[WebSocket] = set()
# DICTIONARY TO STORE SESSION IDENTIFIERS AND CORRESPONDING WEBSOCKET CLIENTS
session_websockets = {}

# GET DATA FROM PIR SENSOR
async def pirCheck(background_tasks: BackgroundTasks):
    global pirVal
    # LOOP FOR GETTING DATA FROM PIR SENSOR
    while True:
        # RESULT FROM PIR SENSOR
        input = GPIO.input(17)
        if input == 1:
            pirVal = 1
        else:
            pirVal = 0
        # PRINT FOR DEBUG
        print(f"pirVal-test: {pirVal}")
        await send_pir_value_to_clients()
        # 1S DELAY AFTER SENDING TO CLIENTS
        # PREVENT TO MUCH TRANSFER
        await asyncio.sleep(0.5)

# PIR SENSOR FUNCTION BACKGROUN RUNNING
@app.on_event("startup")
def startup_event():
    background_tasks = BackgroundTasks()
    asyncio.create_task(pirCheck(background_tasks))

async def send_pir_value_to_clients():
    print(f"Number of websockets: {len(session_websockets)}")
    for session_id, websocket in session_websockets.items():
        print(f"Processing session_id: {session_id}")
        try:
            message = json.dumps({"anybodyThere": pirVal})
            await websocket.send_text(message)
            print(f"message sent to session_id {session_id}: {message}")
        except websockets.exceptions.ConnectionClosedOK as e:
            print(f"ConnectionClosedOK: {e}")
            websocket_clients.remove(websocket)
            del session_websockets[session_id]
        except Exception as e:
            print(f"Error sending message to {session_id}: {e}")

# CREATE SESSION ID
def generate_unique_session_id():
    return str(uuid.uuid4())

# FUNCTION TO GET OR CREATE A SESSION IDENTIFIER
async def get_or_create_session_id(session_id: str = Cookie(default=None)):
    if session_id is None:
        # IF NO SESSION ID IS PROVIDED, GENERATE A NEW ONE
        session_id = generate_unique_session_id()
    return session_id

# FUNCTION TO GET THE SESSION ID FROM THE COOKIE
async def get_or_create_session_id_cookie(session_id: str = Depends(get_or_create_session_id)):
    return session_id

# FUNCTION TO GET THE SESSION ID FROM THE COOKIE
@app.get("/get_or_create_session_id")
async def get_or_create_session_id_endpoint(session_id: str = Depends(get_or_create_session_id)):
    return {"session_id": session_id}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = Depends(get_or_create_session_id)):
    await websocket.accept()
    # LOG WEBSOCKET CONN DETAILS
    logging.debug(f"WebSocket conn: {websocket.client}")
    # CORS ERROR PREVENT
    await websocket.send_text('{"type": "cors_header", "data": "WebSocket CORS header is set."}')
    websocket_clients.add(websocket)
    session_websockets[session_id] = websocket  # Store the websocket client with session_id
    try:
        while True:
            data = await websocket.receive_text()
            logging.debug(f"received_data: {data}")
            await websocket.send_text(f"message received: {data}")
            await asyncio.sleep(0.5)
    except websockets.exceptions.ConnectionClosedOK:
        websocket_clients.remove(websocket)
        del session_websockets[session_id]
    except WebSocketDisconnect:
        logging.debug("WebSocket disconn")

# FAST-API
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "./index.html",
        {
            "request": request
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")