import asyncio
import json
import websockets

online_users = {}
draw_rooms = {}

async def handler(websocket):
    username = None
    current_room = None
    
    try:
        msg = await websocket.recv()
        data = json.loads(msg)
        
        if data.get('type') == 'join':
            username = data.get('username', '').strip()
            if not username:
                await websocket.send(json.dumps({'type': 'error', 'message': 'Введите имя!'}))
                return
            
            if username in online_users:
                await websocket.send(json.dumps({'type': 'error', 'message': 'Имя уже занято!'}))
                return
            
            online_users[username] = websocket
            print(f'[+] {username} вошел (онлайн: {len(online_users)})')
            
            await websocket.send(json.dumps({'type': 'connected', 'username': username}))
            await websocket.send(json.dumps({'type': 'room_list', 'rooms': list(draw_rooms.keys())}))
        
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'create_room':
                    room_id = data.get('room_id', '').strip().upper()
                    if not room_id:
                        await websocket.send(json.dumps({'type': 'error', 'message': 'Введите ID комнаты!'}))
                        continue
                    
                    if room_id in draw_rooms:
                        await websocket.send(json.dumps({'type': 'error', 'message': f'Комната "{room_id}" уже существует!'}))
                        continue
                    
                    draw_rooms[room_id] = set([username])
                    current_room = room_id
                    
                    await websocket.send(json.dumps({
                        'type': 'room_created',
                        'room_id': room_id,
                        'users': list(draw_rooms[room_id])
                    }))
                    
                    for name, ws in online_users.items():
                        if name != username:
                            try:
                                await ws.send(json.dumps({'type': 'room_list', 'rooms': list(draw_rooms.keys())}))
                            except:
                                pass
                    
                    print(f'[🏠] {username} создал комнату {room_id}')
                
                elif msg_type == 'join_room':
                    room_id = data.get('room_id', '').strip().upper()
                    if not room_id:
                        await websocket.send(json.dumps({'type': 'error', 'message': 'Введите ID комнаты!'}))
                        continue
                    
                    if room_id not in draw_rooms:
                        await websocket.send(json.dumps({'type': 'error', 'message': f'Комната "{room_id}" не найдена!'}))
                        continue
                    
                    draw_rooms[room_id].add(username)
                    current_room = room_id
                    
                    await websocket.send(json.dumps({
                        'type': 'room_joined',
                        'room_id': room_id,
                        'users': list(draw_rooms[room_id])
                    }))
                    
                    for user in draw_rooms[room_id]:
                        if user in online_users and user != username:
                            try:
                                await online_users[user].send(json.dumps({
                                    'type': 'user_joined',
                                    'username': username,
                                    'users': list(draw_rooms[room_id])
                                }))
                            except:
                                pass
                    
                    print(f'[🔗] {username} присоединился к {room_id}')
                
                elif msg_type == 'leave_room':
                    if current_room and current_room in draw_rooms:
                        draw_rooms[current_room].discard(username)
                        
                        for user in draw_rooms[current_room]:
                            if user in online_users:
                                try:
                                    await online_users[user].send(json.dumps({
                                        'type': 'user_left',
                                        'username': username,
                                        'users': list(draw_rooms[current_room])
                                    }))
                                except:
                                    pass
                        
                        if len(draw_rooms[current_room]) == 0:
                            del draw_rooms[current_room]
                            for name, ws in online_users.items():
                                try:
                                    await ws.send(json.dumps({'type': 'room_list', 'rooms': list(draw_rooms.keys())}))
                                except:
                                    pass
                        
                        current_room = None
                        await websocket.send(json.dumps({'type': 'room_left'}))
                        print(f'[🚪] {username} вышел из комнаты')
                
                elif msg_type == 'draw':
                    room = data.get('room')
                    if room and room in draw_rooms:
                        for user in draw_rooms[room]:
                            if user != username and user in online_users:
                                try:
                                    await online_users[user].send(json.dumps({
                                        'type': 'draw',
                                        'x1': data.get('x1'),
                                        'y1': data.get('y1'),
                                        'x2': data.get('x2'),
                                        'y2': data.get('y2'),
                                        'color': data.get('color'),
                                        'size': data.get('size'),
                                        'from': username
                                    }))
                                except:
                                    pass
                
                elif msg_type == 'clear':
                    room = data.get('room')
                    if room and room in draw_rooms:
                        for user in draw_rooms[room]:
                            if user != username:  # 👈 НЕ отправляем тому, кто очистил
                                if user in online_users:
                                    try:
                                        await online_users[user].send(json.dumps({
                                            'type': 'clear',
                                            'from': username
                                        }))
                                    except:
                                        pass
                
                elif msg_type == 'chat':
                    room = data.get('room')
                    text = data.get('text', '')
                    if room and room in draw_rooms:
                        for user in draw_rooms[room]:
                            if user != username and user in online_users:
                                try:
                                    await online_users[user].send(json.dumps({
                                        'type': 'chat',
                                        'from': username,
                                        'text': text
                                    }))
                                except:
                                    pass
                
                elif msg_type == 'get_rooms':
                    await websocket.send(json.dumps({'type': 'room_list', 'rooms': list(draw_rooms.keys())}))
                
                elif msg_type == 'ping':
                    # Отвечаем на пинг
                    await websocket.send(json.dumps({'type': 'pong'}))
                
            except json.JSONDecodeError:
                pass
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f'[!] {e}')
    finally:
        if username:
            if username in online_users:
                del online_users[username]
                print(f'[-] {username} вышел (онлайн: {len(online_users)})')
            
            for room_id, users in list(draw_rooms.items()):
                if username in users:
                    users.discard(username)
                    if len(users) == 0:
                        del draw_rooms[room_id]
                        for name, ws in online_users.items():
                            try:
                                await ws.send(json.dumps({'type': 'room_list', 'rooms': list(draw_rooms.keys())}))
                            except:
                                pass
                    else:
                        for user in users:
                            if user in online_users:
                                try:
                                    await online_users[user].send(json.dumps({
                                        'type': 'user_left',
                                        'username': username,
                                        'users': list(users)
                                    }))
                                except:
                                    pass

async def main():
    print("========================================")
    print("      🎨 РИСОВАЛКА (исправленная)")
    print("========================================")
    async with websockets.serve(handler, "0.0.0.0", 8080):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
