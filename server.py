"""
多人德州扑克游戏 - FastAPI 后端服务器
支持 HTTP API + WebSocket 实时通信
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import asyncio
import logging
import uuid

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 数据模型 ====================

class Player(BaseModel):
    id: str
    name: str
    chips: int = 1000
    is_host: bool = False

class CreateRoomRequest(BaseModel):
    player_name: str

class JoinRoomRequest(BaseModel):
    player_name: str
    room_id: str

class GameAction(BaseModel):
    action: str  # fold, call, raise, check, allin
    amount: Optional[int] = None

class Room:
    def __init__(self, room_id: str, host_name: str, host_id: str):
        self.room_id = room_id
        self.players: List[Dict[str, Any]] = [{
            "id": host_id,
            "name": host_name,
            "chips": 1000,
            "is_host": True
        }]
        self.host_id = host_id
        self.created_at = datetime.now()
        self.game_started = False
        self.game_state = {}

    def add_player(self, player_id: str, player_name: str):
        self.players.append({
            "id": player_id,
            "name": player_name,
            "chips": 1000,
            "is_host": False
        })

    def remove_player(self, player_id: str):
        self.players = [p for p in self.players if p["id"] != player_id]

    def get_player(self, player_id: str) -> Optional[Dict[str, Any]]:
        return next((p for p in self.players if p["id"] == player_id), None)

# ==================== 应用初始化 ====================

app = FastAPI(title="德州扑克游戏API", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存存储
rooms: Dict[str, Room] = {}
room_players: Dict[str, Dict[str, WebSocket]] = {}  # room_id -> {player_id: websocket}
player_rooms: Dict[str, str] = {}  # player_id -> room_id

# ==================== HTTP API ====================

@app.get("/")
async def root():
    """返回API信息"""
    return {
        "app": "德州扑克游戏 API",
        "version": "1.0.0",
        "endpoints": {
            "rooms": "GET /api/rooms - 获取所有房间",
            "create_room": "POST /api/rooms/create - 创建房间",
            "join_room": "POST /api/rooms/join - 加入房间",
            "room_info": "GET /api/rooms/{room_id} - 获取房间信息",
            "ws_connect": "WS /ws/{room_id}/{player_id} - WebSocket连接"
        }
    }

@app.get("/api/rooms")
async def get_rooms():
    """获取所有活跃房间"""
    logger.info("📡 GET /api/rooms - 获取房间列表")
    result = []
    for room_id, room in rooms.items():
        result.append({
            "room_id": room_id,
            "player_count": len(room.players),
            "host_name": room.players[0]["name"] if room.players else "Unknown",
            "created_at": room.created_at.isoformat(),
            "game_started": room.game_started
        })
    logger.info(f"✅ 返回 {len(result)} 个房间")
    return {"rooms": result}

@app.post("/api/rooms/create")
async def create_room(request: CreateRoomRequest):
    """创建新房间"""
    logger.info(f"📡 POST /api/rooms/create - 创建房间: {request.player_name}")

    # 生成房间ID
    room_id = str(uuid.uuid4())[:8]
    player_id = str(uuid.uuid4())

    # 创建房间
    room = Room(room_id, request.player_name, player_id)
    rooms[room_id] = room
    room_players[room_id] = {}

    logger.info(f"✅ 房间创建成功: room_id={room_id}, player_id={player_id}")
    return {
        "room_id": room_id,
        "player_id": player_id,
        "player_name": request.player_name,
        "is_host": True,
        "invite_url": f"http://localhost:8000/api/rooms/{room_id}"
    }

@app.post("/api/rooms/join")
async def join_room(request: JoinRoomRequest):
    """加入房间"""
    logger.info(f"📡 POST /api/rooms/join - 加入房间: room={request.room_id}, player={request.player_name}")

    # 检查房间是否存在
    if request.room_id not in rooms:
        logger.warning(f"❌ 房间不存在: {request.room_id}")
        raise HTTPException(status_code=404, detail="房间不存在")

    room = rooms[request.room_id]

    # 检查游戏是否已开始
    if room.game_started:
        logger.warning(f"❌ 游戏已开始，无法加入: {request.room_id}")
        raise HTTPException(status_code=400, detail="游戏已开始，无法加入")

    # 生成玩家ID
    player_id = str(uuid.uuid4())

    # 添加玩家到房间
    room.add_player(player_id, request.player_name)

    logger.info(f"✅ 玩家加入成功: player_id={player_id}")
    return {
        "room_id": request.room_id,
        "player_id": player_id,
        "player_name": request.player_name,
        "is_host": False,
        "players": room.players
    }

@app.get("/api/rooms/{room_id}")
async def get_room_info(room_id: str):
    """获取房间信息"""
    logger.info(f"📡 GET /api/rooms/{room_id} - 获取房间信息")

    if room_id not in rooms:
        logger.warning(f"❌ 房间不存在: {room_id}")
        raise HTTPException(status_code=404, detail="房间不存在")

    room = rooms[room_id]
    logger.info(f"✅ 返回房间信息: {len(room.players)} 名玩家")
    return {
        "room_id": room_id,
        "players": room.players,
        "host_id": room.host_id,
        "game_started": room.game_started
    }

# ==================== WebSocket ====================

@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    """
    WebSocket 连接端点
    用于实时游戏通信
    """
    logger.info(f"🔌 WebSocket 连接请求: room={room_id}, player={player_id}")

    # 检查房间是否存在
    if room_id not in rooms:
        logger.warning(f"❌ 房间不存在: {room_id}")
        await websocket.close(code=1008, reason="房间不存在")
        return

    room = rooms[room_id]

    # 检查玩家是否在房间中
    player = room.get_player(player_id)
    if not player:
        logger.warning(f"❌ 玩家不在房间中: {player_id}")
        await websocket.close(code=1008, reason="玩家不在房间中")
        return

    # 接受WebSocket连接
    await websocket.accept()
    logger.info(f"✅ WebSocket 连接建立: {player['name']}")

    # 保存连接
    if room_id not in room_players:
        room_players[room_id] = {}
    room_players[room_id][player_id] = websocket
    player_rooms[player_id] = room_id

    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "message": f"欢迎加入房间 {room_id}!",
            "player_id": player_id,
            "players": room.players
        })
        logger.info(f"📤 发送欢迎消息给 {player['name']}")

        # 广播新玩家加入
        await broadcast_to_room(room_id, {
            "type": "player_joined",
            "player": player,
            "message": f"{player['name']} 加入了房间"
        }, exclude=player_id)

        # 持续接收消息
        while True:
            data = await websocket.receive_json()
            logger.info(f"📥 收到消息: {data.get('type', 'unknown')}")

            # 处理不同类型的消息
            await handle_websocket_message(room_id, player_id, data)

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket 断开: {player['name']}")
        # 移除连接
        if room_id in room_players and player_id in room_players[room_id]:
            del room_players[room_id][player_id]

        # 移除玩家（如果游戏未开始）
        if not room.game_started:
            room.remove_player(player_id)
            await broadcast_to_room(room_id, {
                "type": "player_left",
                "player_id": player_id,
                "message": f"{player['name']} 离开了房间"
            })

        # 清理空房间
        if len(room.players) == 0:
            logger.info(f"🗑️ 删除空房间: {room_id}")
            del rooms[room_id]
            if room_id in room_players:
                del room_players[room_id]

    except Exception as e:
        logger.error(f"❌ WebSocket 错误: {e}")
        await websocket.close(code=1011, reason=str(e))

async def handle_websocket_message(room_id: str, player_id: str, data: dict):
    """处理WebSocket消息"""
    message_type = data.get("type")

    if message_type == "chat":
        # 聊天消息
        await broadcast_to_room(room_id, {
            "type": "chat",
            "player_id": player_id,
            "message": data.get("message", "")
        })

    elif message_type == "game_action":
        # 游戏动作
        logger.info(f"🎮 游戏动作: player={player_id}, action={data.get('action')}")
        await broadcast_to_room(room_id, {
            "type": "game_action",
            "player_id": player_id,
            "action": data.get("action"),
            "data": data.get("data", {})
        })

    elif message_type == "game_start":
        # 开始游戏
        room = rooms[room_id]
        if room and room.players[0]["id"] == player_id:  # 只有房主可以开始
            room.game_started = True
            await broadcast_to_room(room_id, {
                "type": "game_start",
                "message": "游戏开始！"
            })

    elif message_type == "state_update":
        # 状态更新（仅房主发送）
        await broadcast_to_room(room_id, {
            "type": "state_update",
            "state": data.get("state")
        }, exclude=player_id)

async def broadcast_to_room(room_id: str, message: dict, exclude: Optional[str] = None):
    """向房间内所有玩家广播消息"""
    if room_id not in room_players:
        return

    logger.info(f"📡 广播到房间 {room_id}: {message.get('type')}")

    for pid, websocket in room_players[room_id].items():
        if exclude and pid == exclude:
            continue

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送消息失败给玩家 {pid}: {e}")

# ==================== 启动服务器 ====================

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 启动德州扑克游戏服务器...")
    logger.info("📡 API文档: http://localhost:8000/docs")
    logger.info("🎮 WebSocket: ws://localhost:8000/ws/{room_id}/{player_id}")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
