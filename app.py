from fastapi import FastAPI, Request, Response, HTTPException, Depends,WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware
import psycopg2
from datetime import datetime
import hashlib
import json
import uuid
import zlib
from urllib.parse import unquote
import threading

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")
# Mount static files and templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# 数据库配置
class DBConfig:
    POSTGRES = {
        'host': "101.132.80.183",
        'port': "5433",
        'database': "db5661cc1a4f174e81b983a51ce3808a29mydata",
        'user': "hanfu_data",
        'password': "Qq111111"
    }

# 获取数据库连接
def get_db_connection():
    return psycopg2.connect(**DBConfig.POSTGRES)

# 执行查询
def execute_query(query, params=None, commit=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        if commit:
            conn.commit()
            return True
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

# Add this helper function for password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if "user_id" in request.session:
        role = request.session["role"]
        if role == "管理员":
            return RedirectResponse(url="/admin")
        elif role == "财务人员":
            return RedirectResponse(url="/finance")
        elif role == "采购人员":
            return RedirectResponse(url="/purchase")
        else:
            return RedirectResponse(url="/other")
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username = form_data["username"]
    password = hash_password(form_data["password"])
    
    query = "SELECT id, role FROM users WHERE username = %s AND password = %s"
    user = execute_query(query, (username, password))
    
    if user and user[0]:
        request.session["user_id"] = user[0][0]
        request.session["role"] = user[0][1]
        return RedirectResponse(url="/", status_code=303)
    return HTTPException(status_code=401, detail="登录失败")

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(request: Request):
    form_data = await request.form()
    username = form_data["username"]
    password = hash_password(form_data["password"])
    confirm_password = hash_password(form_data["confirm_password"])
    role = form_data["role"]
    
    # 不允许注册管理员角色
    if role == "管理员":
        return HTTPException(status_code=400, detail="不允许注册管理员角色")
    
    # 为财务人员和采购人员添加待审核后缀
    if role in ["财务人员", "采购人员"]:
        role = f"{role}(待审核)"
    
    if password != confirm_password:
        return HTTPException(status_code=400, detail="两次输入的密码不一致")
    
    query = "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)"
    
    try:
        execute_query(query, (username, password, role), commit=True)
        return RedirectResponse(url="/login", status_code=303)
    except:
        return HTTPException(status_code=500, detail="注册失败，用户名可能已存在")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    if "user_id" in request.session and request.session["role"] == "管理员":
        return templates.TemplateResponse("admin.html", {"request": request, "now": datetime.now(), "tables": get_all_tables()})
    return RedirectResponse(url="/login", status_code=303)

@app.get("/finance", response_class=HTMLResponse)
async def finance_page(request: Request):
    if "user_id" in request.session and request.session["role"] == "财务人员":
        return templates.TemplateResponse("finance.html", {"request": request})
    return RedirectResponse(url="/login", status_code=303)

@app.get("/purchase", response_class=HTMLResponse)
async def purchase_page(request: Request):
    if "user_id" in request.session and request.session["role"] == "采购人员":
        return templates.TemplateResponse("purchase.html", {"request": request})
    return RedirectResponse(url="/login", status_code=303)

@app.get("/other", response_class=HTMLResponse)
async def other_page(request: Request):
    if "user_id" in request.session:
        return templates.TemplateResponse("other.html", {"request": request})
    return RedirectResponse(url="/login", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/switch_db/{db_type}")
async def switch_db(db_type: str, request: Request):
    global CURRENT_DB
    if db_type in ["mysql", "sqlite"]:
        CURRENT_DB = db_type
        return HTMLResponse(f"已切换到 {db_type} 数据库")
    return HTMLResponse("无效的数据库类型")

@app.get("/admin/db", response_class=HTMLResponse)
async def admin_db(request: Request):
    if "user_id" not in request.session or request.session["role"] != "管理员":
        return RedirectResponse(url="/login", status_code=303)
    
    query = "SELECT id, username, role FROM users"
    users = execute_query(query)
    return templates.TemplateResponse("admin_db.html", {"request": request, "users": users, "now": datetime.now(), "tables": get_all_tables()})

@app.post("/admin/db/add")
async def admin_db_add(request: Request):
    if "user_id" not in request.session or request.session["role"] != "管理员":
        return RedirectResponse(url="/login", status_code=303)
    
    username = request.form["username"]
    password = hash_password(request.form["password"])
    role = request.form["role"]
    
    query = "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)"
    
    try:
        execute_query(query, (username, password, role), commit=True)
        return RedirectResponse(url="/admin/db", status_code=303)
    except:
        return HTTPException(status_code=500, detail="添加用户失败，用户名可能已存在")

@app.post("/admin/db/delete")
async def admin_db_delete(request: Request):
    if "user_id" not in request.session or request.session["role"] != "管理员":
        return RedirectResponse(url="/login", status_code=303)
    
    user_id = request.form["user_id"]
    query = "DELETE FROM users WHERE id = ?"
    
    try:
        execute_query(query, (user_id,), commit=True)
        return RedirectResponse(url="/admin/db", status_code=303)
    except:
        return HTTPException(status_code=500, detail="删除用户失败")

@app.post("/admin/db/edit")
async def admin_db_edit(request: Request):
    if "user_id" not in request.session or request.session["role"] != "管理员":
        return RedirectResponse(url="/login", status_code=303)
    
    form_data = await request.form()
    user_id = form_data["user_id"]
    username = form_data["username"]
    role = form_data["role"]
    password = form_data.get("password")
    
    if password:
        password = hash_password(password)
        query = "UPDATE users SET username = %s, role = %s, password = %s WHERE id = %s"
        params = (username, role, password, user_id)
    else:
        query = "UPDATE users SET username = %s, role = %s WHERE id = %s"
        params = (username, role, user_id)
    
    try:
        execute_query(query, params, commit=True)
        return RedirectResponse(url="/admin/db", status_code=303)
    except:
        return HTTPException(status_code=500, detail="修改用户失败")
    

def get_table_columns(table_name):
    query = """
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = %s
    """
    columns = execute_query(query, (table_name,))
    return [col[0] for col in columns]

@app.get("/sheet", response_class=HTMLResponse, name="sheet_view")
async def sheet_view(request: Request):
    if "user_id" not in request.session or request.session["role"] != "管理员":
        return RedirectResponse(url="/login", status_code=303)
    
    table_name = request.query_params.get("table")
    if not table_name:
        return RedirectResponse(url="/admin/sheet", status_code=303)
    
    columns = []
    # Get column names and convert them to a list of dictionaries with column info
    raw_columns = get_table_columns(table_name)
    columns = [{"title": col, "key": col} for col in raw_columns]
    
    return templates.TemplateResponse("sheet.html", {
        "request": request, 
        "columns": columns,
        "table_name": table_name  # Pass table_name to template
    })

def get_all_tables():
    query = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    """
    return [table[0] for table in execute_query(query)]

@app.get("/admin/sheet", response_class=HTMLResponse, name="admin_sheet")
async def admin_sheet(request: Request):
    if "user_id" not in request.session or request.session["role"] != "管理员":
        return RedirectResponse(url="/login", status_code=303)
    
    tables = get_all_tables()
    selected_table = request.query_params.get("table")
    
    return templates.TemplateResponse("admin_sheet.html", {"request": request, "tables": tables, "selected_table": selected_table})

# 复用原有的 Pool 类来管理 WebSocket 连接
class Pool:
    lock = threading.Lock()
    pools = {}

    @classmethod
    def add(cls, table_name, uid, ws):
        with cls.lock:
            if table_name not in cls.pools:
                cls.pools[table_name] = {}
            cls.pools[table_name][uid] = ws

    @classmethod
    def delete(cls, table_name, uid):
        with cls.lock:
            if table_name in cls.pools:
                cls.pools[table_name].pop(uid, None)

    @classmethod
    async def notify(cls, table_name, data, by):
        #print(f"Notifying table: {table_name}, data: {data}, by: {by}")
        with cls.lock:
            if table_name in cls.pools:
                for uid, ws in cls.pools[table_name].items():
                    if uid == by:
                        continue
                    try:
                        await ws.send_text(data)
                    except Exception:
                        pass


@app.post("/luckysheet/api/loadUrl")
async def load(request: Request):
    # 从查询参数中获取 table_name
    table_name = request.query_params.get("table")
    #print(f"Received table_name: {table_name}")  # 调试输出
    
    if not table_name:
        return json.dumps([{
            "name": "Sheet1",
            "index": "sheet_01",
            "order": 0,
            "status": 1,
            "celldata": [],
            "column": 26,
            "row": 100,
            "total": 1
        }])

    # Get columns from the table
    columns = get_table_columns(table_name)
    
    # Get data from the table
    query = f"SELECT * FROM {table_name}"
    rows = execute_query(query)
    
    # Convert database data to celldata format
    celldata = []
    # Add headers
    for col_idx, col_name in enumerate(columns):
        celldata.append({
            "r": 0,
            "c": col_idx,
            "v": {"v": col_name, "m": col_name}
        })
    
    for row_idx, row in enumerate(rows, start=1):
        for col_idx, value in enumerate(row):
            if value is not None:
                celldata.append({
                    "r": row_idx,
                    "c": col_idx,
                    "v": {"v": str(value), "m": str(value)}
                })

    # 返回完整的数据结构

    return json.dumps([{
        "name": table_name,
        "index": "sheet_01",
        "order": 0,
        "status": 1,
        "celldata": celldata,
        "column": len(columns),
        "row": max(len(rows) + 20, 100),
        "total": 1,
        "config": {
            "columnlen": {},
            "rowlen": {},
            "column": {"len": len(columns)},
            "row": {"len": max(len(rows) + 20, 100)},
            "freeze": {"row": 1},  # Freeze the first row
            "filter": {"row": 1},  # Enable filter on the first row
            "authority": {
                "sheet": 1,
                "hintText": "该表格已启用保护，第一行不可编辑",
                "protectionMode": 1,  # 启用自定义保护模式
                "allowRangeList": [   # 允许编辑的范围
                    {
                        "name": "allow_range",
                        "sqref": "A2:XFD1048576"  # 从第二行开始到最后一行都可以编辑
                    }
                ]
            }
        },
        "index": 0
    }])

@app.websocket("/luckysheet/api/updateUrl")
async def update(websocket: WebSocket):
    await websocket.accept()
    uid = str(uuid.uuid4())
    table_name = websocket.query_params.get("g")
    role = websocket.session["role"]
    try:
        Pool.add(table_name, uid, websocket)
        
        while True:
            try:
                message = await websocket.receive_text()
                if message == "rub":  # Changed back to "rub"
                    #await websocket.send_text("rub")  # Changed back to "rub"
                    continue
                
                data_raw = message.encode('iso-8859-1')
                data_unzip = unquote(zlib.decompress(data_raw, 16).decode())
                json_data = json.loads(data_unzip)
                
                if json_data.get("t") != "cg":
                    resp_data = {
                        "data": data_unzip,
                        "id": uid,
                        "returnMessage": "success",
                        "status": 0,
                        "type": 3 if json_data.get("t") == "mv" else 2,
                        "username": role,
                    }
                    await Pool.notify(table_name, json.dumps(resp_data), uid)
                
            except Exception:
                # If a disconnect message is received, exit the loop
                break
                
    finally:
        Pool.delete(table_name, uid)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)