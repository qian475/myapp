from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from datetime import datetime
import hashlib

app = Flask(__name__, 
    template_folder='templates',  # 设置模板目录
    static_folder='static'        # 设置静态文件目录
)
app.secret_key = 'your_secret_key'

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

@app.route('/')
def index():
    if 'user_id' in session:
        role = session['role']
        if role == '管理员':
            return redirect(url_for('admin_page'))
        elif role == '财务人员':
            return redirect(url_for('finance_page'))
        elif role == '采购人员':
            return redirect(url_for('purchase_page'))
        else:
            return redirect(url_for('other_page'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])  # Hash the password
        
        query = "SELECT id, role FROM users WHERE username = %s AND password = %s"  # Changed ? to %s for PostgreSQL
        
        user = execute_query(query, (username, password))
        
        if user and user[0]:
            session['user_id'] = user[0][0]
            session['role'] = user[0][1]
            return redirect(url_for('index'))
        return '登录失败'
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])  # Hash the password
        confirm_password = hash_password(request.form['confirm_password'])  # Hash confirmation password
        role = request.form['role']
        
        # 不允许注册管理员角色
        if role == '管理员':
            return '不允许注册管理员角色'
            
        # 为财务人员和采购人员添加待审核后缀
        if role in ['财务人员', '采购人员']:
            role = f"{role}(待审核)"
        
        if password != confirm_password:
            return '两次输入的密码不一致'
        
        query = "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)"
        
        try:
            execute_query(query, (username, password, role), commit=True)
            return redirect(url_for('login'))
        except:
            return '注册失败，用户名可能已存在'
    return render_template('register.html')

@app.route('/admin')
def admin_page():
    if 'user_id' in session and session['role'] == '管理员':
        return render_template('admin.html', now=datetime.now())
    return redirect(url_for('login'))

@app.route('/finance')
def finance_page():
    if 'user_id' in session and session['role'] == '财务人员':
        return render_template('finance.html')
    return redirect(url_for('login'))

@app.route('/purchase')
def purchase_page():
    if 'user_id' in session and session['role'] == '采购人员':
        return render_template('purchase.html')
    return redirect(url_for('login'))

@app.route('/other')
def other_page():
    if 'user_id' in session:
        return render_template('other.html')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/switch_db/<db_type>')
def switch_db(db_type):
    global CURRENT_DB
    if db_type in ['mysql', 'sqlite']:
        CURRENT_DB = db_type
        return f'已切换到 {db_type} 数据库'
    return '无效的数据库类型'

@app.route('/admin/db')
def admin_db():
    if 'user_id' not in session or session['role'] != '管理员':
        return redirect(url_for('login'))
    
    query = "SELECT id, username, role FROM users"
    users = execute_query(query)
    return render_template('admin_db.html', users=users, now=datetime.now())

@app.route('/admin/db/add', methods=['POST'])
def admin_db_add():
    if 'user_id' not in session or session['role'] != '管理员':
        return redirect(url_for('login'))
    
    username = request.form['username']
    password = hash_password(request.form['password'])  # Hash the password
    role = request.form['role']
    
    query = "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)"  # Changed ? to %s for PostgreSQL
    
    try:
        execute_query(query, (username, password, role), commit=True)
        return redirect(url_for('admin_db'))
    except:
        return '添加用户失败，用户名可能已存在'

@app.route('/admin/db/delete', methods=['POST'])
def admin_db_delete():
    if 'user_id' not in session or session['role'] != '管理员':
        return redirect(url_for('login'))
    
    user_id = request.form['user_id']
    query = "DELETE FROM users WHERE id = ?"
    
    try:
        execute_query(query, (user_id,), commit=True)
        return redirect(url_for('admin_db'))
    except:
        return '删除用户失败'

@app.route('/admin/db/edit', methods=['POST'])
def admin_db_edit():
    if 'user_id' not in session or session['role'] != '管理员':
        return redirect(url_for('login'))
    
    user_id = request.form['user_id']
    username = request.form['username']
    role = request.form['role']
    password = request.form.get('password')  # 密码是可选的
    
    if password:  # 如果提供了新密码
        password = hash_password(password)  # Hash the new password
        query = "UPDATE users SET username = %s, role = %s, password = %s WHERE id = %s"  # Changed ? to %s for PostgreSQL
        params = (username, role, password, user_id)
    else:
        query = "UPDATE users SET username = %s, role = %s WHERE id = %s"  # Changed ? to %s for PostgreSQL
        params = (username, role, user_id)
    
    try:
        execute_query(query, params, commit=True)
        return redirect(url_for('admin_db'))
    except:
        return '修改用户失败'

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)