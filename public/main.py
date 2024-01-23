from typing import Union

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json

# 여기에 초음파 센서에서 얻은 값을 저장
pirCheck = "1"

app = FastAPI()

templates = Jinja2Templates(directory = "templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    anybodyThere = {"anybodyThere" : pirCheck}
    anybodyThere_str = json.dumps(anybodyThere, ensure_ascii=False)
    return templates.TemplateResponse(
        "./index.html",
        {
            "request": request,
            "anybodyThere": anybodyThere_str
        }
    )