'''필요한 모듈 및 라이브러리'''
# 타입 힌트 지원을 위한 모듈
from typing import Union, Set
# 로그를 어느 수준에서 띄워줄 것인지 모듈
import logging
# 비동기 프로그래밍을 위한 모듈
import asyncio
# 라즈베리파이의 GPIO를 제어하기 위한 모듈
import RPi.GPIO as GPIO
# FAST-API와 관련된 모
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, WebSocket, Cookie, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates # HTML 템플릿
from fastapi.middleware.cors import CORSMiddleware # CORS를 관리하기 위한 모듈
from fastapi.websockets import WebSocketDisconnect # FAST-API와 WebSocket에 관련된 모듈
# WebSocket 모듈
import websockets
# 서버와 클라이언트간의 데이터 전송을 위해 사용하는 JSON 모듈
import json
# 세션 식별자를 만들기 위한 모듈
import uuid

'''Raspberry Pi의 GPIO를 설정'''
# BCM 모드
GPIO.setmode(GPIO.BCM)
# 17번 핀을 입력으로 사용하며, 풀업/풀다운 저항을 설정
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

'''로깅 레벨 설정'''
# 로깅 레벨을 디버그로 설정
logging.basicConfig(level=logging.DEBUG)

'''FastAPI 애플리케이션 설정'''
# FastAPI 애플리케이션을 초기화
app = FastAPI()
# CORS 미들웨어를 추가하여 크로스 오리진 리소스 공유를 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# HTML 템플릿을 처리하기 위해 Jinja2Templates를 설정
templates = Jinja2Templates(directory="templates")

'''전역 변수 설정'''
# PIR 센서 값
pirVal = 1
# WebSocket 클라이언트를 저장하는 websocket_clients
websocket_clients: Set[WebSocket] = set()
# 세션 식별자와 WebSocket 클라이언트를 연결하는 session_websockets를 설정
session_websockets = {}

'''PIR 센서 데이터 가져오기
 백그라운드에서 동작하는 pirCheck 함수'''
# 주기적으로 PIR 센서에서 데이터를 읽어와서 클라이언트에게 전송
async def pirCheck(background_tasks: BackgroundTasks):
    global pirVal
    # 계속해서 PIR 센서 데이터를 가져오기 위해서 무한 반복 실행
    while True:
        # PIR 센서에서 가져온 결과값
        input = GPIO.input(17)
        if input == 1:
            pirVal = 1
        else:
            pirVal = 0
        # 디버깅
        print(f"pirVal-test: {pirVal}")
		# 클라이언트에게 데이터 전송
        await send_pir_value_to_clients()
        # 클라이언트에게 데이터 전송을 한 후 잠시 딜레이
        # 너무 많은 전송을 방지하기 위함
        await asyncio.sleep(0.5)

'''PIR 센서를 백그라운드에서 실행
 FastAPI 애플리케이션이 시작될 때 백그라운드 작업으로 pirCheck 함수를 실행
 애플리케이션이 시작될 때 백그라운드에서 pirCheck 함수를 실행하여 PIR 센서의 데이터를 주기적으로 가져옴
 이후 해당 데이터를 WebSocket 클라이언트들에게 전송하는 작업'''
# FastAPI 애플리케이션이 시작될 때 특정 이벤트를 처리
@app.on_event("startup")
def startup_event():
	# BackgroundTasks: 백그라운드에서 실행될 작업들을 관리하는 객체
    background_tasks = BackgroundTasks()
	# pirCheck 함수를 비동기적으로 실행하는 작업을 생성
	# 애플리케이션의 메인 이벤트 루프가 차단되지 않고 비동기적으로 백그라운드 작업을 수행
    asyncio.create_task(pirCheck(background_tasks))

'''WebSocket 클라이언트에게 PIR 센서 값 전송
 현재 연결된 WebSocket 클라이언트들에게 PIR 센서의 값을 전송하는 역할
 현재 연결된 클라이언트에게 PIR 센서의 값을 전달
 연결이 종료된 경우에는 클라이언트를 적절히 관리하여 안정적인 동작을 제공'''
# WebSocket 클라이언트에게 PIR 센서 값 전송을 담당하는 함수를 정의
async def send_pir_value_to_clients():
	# 디버깅 용
	# 현재 연결된 클라이언트가 얼마나 있는지
	# 없으면 아래의 반복문이 실행되지 않음
    print(f"Number of websockets: {len(session_websockets)}")
    for session_id, websocket in session_websockets.items():
		# 해당 클라이언트의 세션 ID가 뭔지
		# 어떤 클라이언트에게 데이터를 전송하는지 확인
        print(f"Processing session_id: {session_id}")
        try:
			# 해당 클라이언트에게 PIR 센서 값을 JSON 형태로 전달
            message = json.dumps({"anybodyThere": pirVal})
			# send_text 메소드를 사용하여 전송
            await websocket.send_text(message)
            print(f"message sent to session_id {session_id}: {message}")
		# 예외 상황
		# 클라이언트와의 WebSocket 연결이 정상적으로 종료
        except websockets.exceptions.ConnectionClosedOK as e:
            print(f"ConnectionClosedOK: {e}")
			# 해당 클라이언트를 관리하는 데이터 구조에서 제거
            websocket_clients.remove(websocket)
            del session_websockets[session_id]
		# 정상 종료가 아닌 예외 상황
        except Exception as e:
            print(f"Error sending message to {session_id}: {e}")

'''세션 식별자 함수'''
# 고유한 세션 식별자를 생성하는 함수
def generate_unique_session_id():
    return str(uuid.uuid4())

'''세션 식별자를 가져오고 생성하는 함수
 FastAPI 애플리케이션에서 세션 식별자를 가져오거나 생성하는 함수들을 정의
 세션 식별자를 가져오거나 생성하는 함수'''
# session_id는 함수 호출 시에 쿠키에서 제공
async def get_or_create_session_id(session_id: str = Cookie(default=None)):
    if session_id is None:
        # 제공된 세션 식별자가 없으면 새로 만듦
        session_id = generate_unique_session_id()
    return session_id
'''쿠키로부터 세션 식별자를 가져오는 함수
 get_or_create_session_id 함수를 Depends로 지정하여 의존성 주입을 통해 세션 식별자를 가져오는 함수
 클라이언트의 요청이 발생할 때마다 이 함수가 실행되어 세션 식별자를 반환'''
async def get_or_create_session_id_cookie(session_id: str = Depends(get_or_create_session_id)):
    return session_id
'''GET 엔드포인트
 세션 식별자를 가져오거나 생성하는 함수를 사용하여 응답을 반환
 클라이언트가 GET 요청을 보내면, 해당 요청에 대한 응답으로 세션 식별자가 포함된 JSON 형태의 데이터를 반환'''
@app.get("/get_or_create_session_id")
async def get_or_create_session_id_endpoint(session_id: str = Depends(get_or_create_session_id)):
    return {"session_id": session_id}

'''WebSocket 엔드포인트 및 처리 함수
 WebSocket 연결을 처리하는 엔드포인트와 해당 처리 함수를 정의
 클라이언트와 서버 간의 양방향 통신을 지원
 클라이언트에서 서버로 데이터를 보내고 받는 동시에 클라이언트들을 관리
 클라이언트와의 연결이 유지되는 동안 계속해서 데이터를 주고받을 수 있습니다.'''
# 이 함수를 "/ws" 경로에 WebSocket 엔드포인트로 등록
@app.websocket("/ws")
# session_id: 세션 식별자, get_or_create_session_id 함수에 의해서 처리
async def websocket_endpoint(websocket: WebSocket, session_id: str = Depends(get_or_create_session_id)):
    # 클라이언트로부터의 WebSocket 연결을 수락
	# WebSocket 연결은 클라이언트에서 요청
    await websocket.accept()
    # WebSocket 연결에 대한 로그, 클라이언트의 정보가 표시
    logging.debug(f"WebSocket conn: {websocket.client}")
    # CORS 에러 방지
	# WebSocket CORS 헤더가 설정되었음을 클라이언트에게 알림
    await websocket.send_text('{"type": "cors_header", "data": "WebSocket CORS header is set."}')
    # 현재 연결된 WebSocket 클라이언트를 관리
	# 브라우저에서 새로고침을 하게되면 WebSocket 연결이 끊기는 에러가 발생해서 추가
	# 세션 식별자를 사용하여 session_websockets에 저장
    websocket_clients.add(websocket)
    session_websockets[session_id] = websocket  # Store the websocket client with session_id
    try:
        # 무한 루트를 통한 데이터 수신 및 전송
        while True:
            # 클라이언트로부터 텍스트 데이터를 수신
            data = await websocket.receive_text()
            logging.debug(f"received_data: {data}")
            # 다시 클라이언트에게 동일한 데이터를 전송
            await websocket.send_text(f"message received: {data}")
            # 0.5초의 딜레이를 추가하여 지나치게 빠른 전송을 방지
            await asyncio.sleep(0.5)
    # 예외처리
	# WebSocket 연결이 정상적으로 종료
    except websockets.exceptions.ConnectionClosedOK:
        # 연결 종료 시에는 해당 클라이언트를 관리하는 데이터 구조에서 제거
        websocket_clients.remove(websocket)
        del session_websockets[session_id]
    # 클라이언트에서 연결을 끊었을 때
    except WebSocketDisconnect:
        logging.debug("WebSocket disconn")

'''FAST-API 홈페이지 엔드포인트'''
# FAST-API, 첫 페이지
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "./index.html",
        {
            "request": request
        }
    )

'''FAST-API 서버 실행'''
# 스크립트가 직접 실행될 때 FastAPI 서버를 실행
if __name__ == "__main__":
    # 호스트는 0.0.0.0이며 포트는 8000번, 로그는 디버그 레벨
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")