
import os, secrets, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
DB = os.environ.get("DATABASE_PATH", "association.db")
MONTHLY_AMOUNT = 3000
ADMIN_NAME = "Advent Sumari"
MPESA_NUMBER = "0763805070"
MPESA_NAME = "ADVENT WANGAEL SUMARI"

TEMPLATES = {'admin.html': '{% extends \'base.html\' %}{% block content %}<section class="topline"><div><span class="pill">ADMIN DASHBOARD</span><h1>Payment verification</h1></div><a href="{{url_for(\'admin_logout\')}}">Logout</a></section><section class="grid"><div class="stat"><b>{{pending}}</b><span>Pending</span></div><div class="stat"><b>TSh {{verified|format_currency}}</b><span>Verified total</span></div><div class="stat"><b>{{members}}</b><span>Members</span></div></section><section class="card wide"><form class="filters"><input name="q" value="{{q}}" placeholder="Search name, phone or reference"><select name="status"><option value="pending" {% if status==\'pending\' %}selected{% endif %}>Pending</option><option value="verified" {% if status==\'verified\' %}selected{% endif %}>Verified</option><option value="rejected" {% if status==\'rejected\' %}selected{% endif %}>Rejected</option></select><button class="btn">Filter</button></form></section><section class="card wide"><div class="tablewrap"><table><tr><th>Member</th><th>Month</th><th>Amount</th><th>Reference</th><th>Status / Action</th></tr>{% for p in payments %}<tr><td>{{p.full_name}}<small>{{p.phone}}</small></td><td>{{p.month}}</td><td>TSh {{p.amount|format_currency}}</td><td><b>{{p.reference}}</b></td><td><span class="status {{p.status}}">{{p.status}}</span>{% if p.status==\'pending\' %}<form method="post" action="{{url_for(\'review_payment\',pid=p.id,action=\'verify\')}}" class="inline"><input name="note" placeholder="Optional note"><button class="approve">Verify</button></form><form method="post" action="{{url_for(\'review_payment\',pid=p.id,action=\'reject\')}}" class="inline"><input name="note" placeholder="Reason"><button class="reject">Reject</button></form>{% elif p.review_note %}<small>{{p.review_note}}</small>{% endif %}</td></tr>{% else %}<tr><td colspan="5">No records found.</td></tr>{% endfor %}</table></div></section>{% endblock %}', 'admin_login.html': '{% extends \'base.html\' %}{% block content %}<div class="formcard"><h1>Admin Login</h1><form method="post"><label>Password<input type="password" name="password" required></label><button class="btn">Login</button></form></div>{% endblock %}', 'base.html': '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title or \'OUR SMALL CAN RISE\' }}</title><style>{{ style_css|safe }}</style></head><body><nav><a class="brand" href="{{ url_for(\'home\') }}">OUR SMALL CAN RISE</a><div><a href="{{ url_for(\'home\') }}">Home</a><a href="{{ url_for(\'register\') }}">Join</a><a href="{{ url_for(\'login\') }}">Member Login</a><a href="{{ url_for(\'admin_login\') }}">Admin</a></div></nav><main>{% with messages=get_flashed_messages(with_categories=true) %}{% for cat,msg in messages %}<div class="flash {{cat}}">{{msg}}</div>{% endfor %}{% endwith %}{% block content %}{% endblock %}</main><a class="wa" href="https://wa.me/255763805070" target="_blank">WhatsApp</a><footer>© 2026 OUR SMALL CAN RISE</footer></body></html>', 'dashboard.html': '{% extends \'base.html\' %}{% block content %}<section class="topline"><div><span class="pill">MEMBER AREA</span><h1>Hello, {{member.full_name}}</h1></div><a href="{{url_for(\'logout\')}}">Logout</a></section><section class="card wide"><h2>Make a monthly contribution</h2><p>Pay <b>TSh {{monthly|format_currency}}</b> to <b>{{mpesa}}</b> — {{mpesa_name}}.</p><form method="post" action="{{url_for(\'payment\')}}" class="payform"><label>Month<input type="month" name="month" required></label><label>Amount (TSh)<input type="number" name="amount" value="{{monthly}}" min="1" required></label><label>Transaction / Reference number<input name="reference" required></label><button class="btn">Submit for verification</button></form></section><section class="card wide"><h2>My payment history</h2><div class="tablewrap"><table><tr><th>Month</th><th>Amount</th><th>Reference</th><th>Status</th></tr>{% for p in payments %}<tr><td>{{p.month}}</td><td>TSh {{p.amount|format_currency}}</td><td>{{p.reference}}</td><td><span class="status {{p.status}}">{{p.status}}</span>{% if p.review_note %}<small class="note">{{p.review_note}}</small>{% endif %}</td></tr>{% else %}<tr><td colspan="4">No payments submitted.</td></tr>{% endfor %}</table></div></section>{% endblock %}', 'home.html': '{% extends \'base.html\' %}{% block content %}<section class="hero"><div><span class="pill">COMMUNITY • UNITY • PROGRESS</span><h1>Small contributions.<br><em>Big impact.</em></h1><p>Jenga jamii yetu kwa mchango wa TSh {{monthly|format_currency}} kwa mwezi.</p><a class="btn" href="{{url_for(\'register\')}}">Become a Member</a></div><div class="card"><small>VERIFIED CONTRIBUTIONS</small><strong>TSh {{verified|format_currency}}</strong><span>{{paid}} contributors verified</span></div></section><section class="grid"><div class="stat"><b>{{members}}</b><span>Members</span></div><div class="stat"><b>TSh {{monthly|format_currency}}</b><span>Monthly target</span></div><div class="stat"><b>{{paid}}</b><span>Verified payers</span></div></section><section class="card wide"><h2>How payment works</h2><p>1. Tuma TSh {{monthly|format_currency}} kupitia Vodacom M-Pesa.</p><p><b>{{mpesa}}</b> — {{mpesa_name}}</p><p>2. Ingia kwenye account yako na submit transaction/reference number.</p><p>3. Admin atakagua malipo na kuyaweka <b>Verified</b> au <b>Rejected</b>.</p></section><section class="card wide"><h2>Verified contributors</h2>{% if recent %}<div class="tablewrap"><table><tr><th>Name</th><th>Month</th><th>Amount</th></tr>{% for r in recent %}<tr><td>{{r.full_name}}</td><td>{{r.month}}</td><td>TSh {{r.amount|format_currency}}</td></tr>{% endfor %}</table></div>{% else %}<p>No verified contributions yet.</p>{% endif %}</section>{% endblock %}', 'login.html': '{% extends \'base.html\' %}{% block content %}<div class="formcard"><h1>Member Login</h1><form method="post"><label>Phone number<input name="phone" required></label><button class="btn">Login</button></form></div>{% endblock %}', 'register.html': '{% extends \'base.html\' %}{% block content %}<div class="formcard"><h1>Join the Association</h1><form method="post"><label>Full name<input name="full_name" required></label><label>Phone number<input name="phone" required placeholder="07XXXXXXXX"></label><label>Email (optional)<input type="email" name="email"></label><button class="btn">Register</button></form></div>{% endblock %}', 'setup.html': '{% extends \'base.html\' %}{% block content %}<div class="formcard"><h1>First-time Admin Setup</h1><p>Create your admin password. Never share it in chat or with members.</p><form method="post"><label>New password<input type="password" name="password" minlength="10" required></label><label>Confirm password<input type="password" name="confirm" minlength="10" required></label><button class="btn">Create Admin</button></form></div>{% endblock %}'}
app.jinja_loader = DictLoader(TEMPLATES)

@app.context_processor
def inject_style():
    return {"style_css": '\n*{box-sizing:border-box}body{margin:0;background:#08110f;color:#eaf4ef;font-family:Inter,system-ui,sans-serif}nav{display:flex;justify-content:space-between;align-items:center;padding:20px 7%;border-bottom:1px solid #183029;position:sticky;top:0;background:#08110fee;backdrop-filter:blur(12px);z-index:5}nav a{color:#bcd1c8;text-decoration:none;margin-left:18px}.brand{font-weight:900;color:#fff!important;letter-spacing:.5px}main{max-width:1100px;margin:auto;padding:55px 22px}.hero{display:grid;grid-template-columns:1.5fr .8fr;gap:35px;align-items:center;min-height:430px}.pill{font-size:12px;letter-spacing:2px;color:#7ee2b0}.hero h1{font-size:clamp(45px,7vw,82px);line-height:.95;margin:18px 0}.hero em{font-style:normal;color:#67d79f}.hero p{font-size:18px;color:#a8bdb4;max-width:600px}.card,.formcard,.stat{background:#0d1b17;border:1px solid #1b332b;border-radius:22px;padding:28px;box-shadow:0 15px 50px #0003}.hero .card{text-align:center}.card strong{display:block;font-size:36px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:20px 0}.stat b{font-size:25px;display:block}.stat span,small{color:#8da69b}.wide{margin-top:20px}.btn{display:inline-block;border:0;background:#67d79f;color:#07120e;padding:13px 20px;border-radius:12px;font-weight:800;text-decoration:none;cursor:pointer}.formcard{max-width:560px;margin:30px auto}.formcard h1{font-size:34px}label{display:block;color:#bcd1c8;font-size:14px;margin:15px 0}input,select{width:100%;padding:13px;border-radius:10px;border:1px solid #29463b;background:#07120f;color:#fff;margin-top:7px}button{font:inherit}.formcard .btn{width:100%;margin-top:10px}.flash{padding:13px 16px;border-radius:10px;margin-bottom:15px}.flash.success{background:#113c2b}.flash.error{background:#45201e}.topline{display:flex;justify-content:space-between;align-items:center}.topline a{color:#8fe3b8}.payform{display:grid;grid-template-columns:1fr 1fr;gap:10px}.payform label:last-of-type{grid-column:1/-1}.payform .btn{grid-column:1/-1}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:14px 10px;border-bottom:1px solid #1b332b}th{color:#7ee2b0;font-size:12px;text-transform:uppercase}td small{display:block}.status{display:inline-block;padding:5px 9px;border-radius:20px;font-size:12px}.status.pending{background:#5b4820;color:#ffd77a}.status.verified{background:#123d2c;color:#80e4b2}.status.rejected{background:#4a2423;color:#ff9d96}.inline{display:inline-flex;gap:5px;margin-top:8px}.inline input{width:130px;margin:0;padding:8px}.approve,.reject{border:0;border-radius:8px;padding:8px 10px;cursor:pointer}.approve{background:#67d79f}.reject{background:#e87870;color:#fff}.filters{display:grid;grid-template-columns:1fr 150px auto;gap:10px}.filters input,.filters select{margin:0}.wa{position:fixed;right:20px;bottom:20px;background:#67d79f;color:#07120e;padding:13px 18px;border-radius:30px;font-weight:800;text-decoration:none;z-index:9}footer{text-align:center;padding:30px;color:#718a80}@media(max-width:750px){nav{align-items:flex-start;gap:10px;flex-direction:column}nav a{margin:0 12px 0 0}.hero{grid-template-columns:1fr}.grid{grid-template-columns:1fr}.payform,.filters{grid-template-columns:1fr}.tablewrap{overflow:auto}table{min-width:700px}}\n'}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        email TEXT,
        joined_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        amount INTEGER NOT NULL,
        reference TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TEXT,
        review_note TEXT,
        FOREIGN KEY(member_id) REFERENCES members(id)
    );
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER,
        action TEXT NOT NULL,
        note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; form-action 'self'"
    return resp

@app.route("/")
def home():
    conn=db()
    verified = conn.execute("SELECT COALESCE(SUM(amount),0) total FROM payments WHERE status='verified'").fetchone()["total"]
    members = conn.execute("SELECT COUNT(*) n FROM members").fetchone()["n"]
    paid = conn.execute("SELECT COUNT(DISTINCT member_id) n FROM payments WHERE status='verified'").fetchone()["n"]
    recent = conn.execute("""
      SELECT m.full_name, p.month, p.amount, p.status
      FROM payments p JOIN members m ON m.id=p.member_id
      WHERE p.status='verified' ORDER BY p.reviewed_at DESC LIMIT 10
    """).fetchall()
    return render_template("home.html", verified=verified, members=members, paid=paid,
                           recent=recent, monthly=MONTHLY_AMOUNT,
                           mpesa=MPESA_NUMBER, mpesa_name=MPESA_NAME)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("full_name","").strip()
        phone=request.form.get("phone","").strip()
        email=request.form.get("email","").strip()
        if not name or not phone:
            flash("Jaza jina na namba ya simu.", "error")
            return redirect(url_for("register"))
        try:
            db().execute("INSERT INTO members(full_name,phone,email) VALUES(?,?,?)",
                         (name,phone,email))
            db().commit()
            flash("Usajili umefanikiwa. Sasa unaweza kuingia.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Namba hii tayari imesajiliwa.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        phone=request.form.get("phone","").strip()
        member=db().execute("SELECT * FROM members WHERE phone=?", (phone,)).fetchone()
        if member:
            session.clear()
            session["member_id"]=member["id"]
            return redirect(url_for("dashboard"))
        flash("Namba haijapatikana. Tafadhali jisajili kwanza.", "error")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("member_id"):
        return redirect(url_for("login"))
    member=db().execute("SELECT * FROM members WHERE id=?", (session["member_id"],)).fetchone()
    payments=db().execute("SELECT * FROM payments WHERE member_id=? ORDER BY submitted_at DESC",
                          (member["id"],)).fetchall()
    return render_template("dashboard.html", member=member, payments=payments,
                           monthly=MONTHLY_AMOUNT, mpesa=MPESA_NUMBER, mpesa_name=MPESA_NAME)

@app.route("/payment", methods=["POST"])
def payment():
    if not session.get("member_id"):
        return redirect(url_for("login"))
    month=request.form.get("month","").strip()
    reference=request.form.get("reference","").strip()
    try:
        amount=int(request.form.get("amount","0"))
    except ValueError:
        amount=0
    if not month or not reference or amount <= 0:
        flash("Jaza mwezi, kiasi na transaction/reference number.", "error")
        return redirect(url_for("dashboard"))
    db().execute("""INSERT INTO payments(member_id,month,amount,reference)
                    VALUES(?,?,?,?)""",
                 (session["member_id"],month,amount,reference))
    db().commit()
    flash("Malipo yametumwa kwa admin kwa ajili ya verification.", "success")
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        password=request.form.get("password","")
        admin=db().execute("SELECT * FROM admins LIMIT 1").fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"]=admin["id"]
            return redirect(url_for("admin"))
        flash("Admin password si sahihi.", "error")
    return render_template("admin_login.html")

@app.route("/setup", methods=["GET","POST"])
def setup():
    if db().execute("SELECT id FROM admins LIMIT 1").fetchone():
        return "Admin tayari amewekwa. Fungua /admin/login."
    if request.method=="POST":
        password=request.form.get("password","")
        confirm=request.form.get("confirm","")
        if len(password)<10 or password!=confirm:
            flash("Password iwe angalau characters 10 na ziwe zinafanana.", "error")
        else:
            db().execute("INSERT INTO admins(name,password_hash) VALUES(?,?)",
                         (ADMIN_NAME,generate_password_hash(password)))
            db().commit()
            flash("Admin account imeundwa. Ingia sasa.", "success")
            return redirect(url_for("admin_login"))
    return render_template("setup.html")

@app.route("/admin")
@admin_required
def admin():
    conn=db()
    q=request.args.get("q","").strip()
    status=request.args.get("status","pending")
    where=[]; params=[]
    if status in ("pending","verified","rejected"):
        where.append("p.status=?"); params.append(status)
    if q:
        where.append("(m.full_name LIKE ? OR m.phone LIKE ? OR p.reference LIKE ?)")
        like=f"%{q}%"; params += [like,like,like]
    clause=(" WHERE "+" AND ".join(where)) if where else ""
    payments=conn.execute(f"""
      SELECT p.*,m.full_name,m.phone,m.email
      FROM payments p JOIN members m ON m.id=p.member_id
      {clause} ORDER BY p.submitted_at DESC
    """,params).fetchall()
    pending=conn.execute("SELECT COUNT(*) n FROM payments WHERE status='pending'").fetchone()["n"]
    verified=conn.execute("SELECT COALESCE(SUM(amount),0) n FROM payments WHERE status='verified'").fetchone()["n"]
    members=conn.execute("SELECT COUNT(*) n FROM members").fetchone()["n"]
    return render_template("admin.html", payments=payments, pending=pending,
                           verified=verified, members=members, q=q, status=status)

@app.route("/admin/payment/<int:pid>/<action>", methods=["POST"])
@admin_required
def review_payment(pid, action):
    if action not in ("verify","reject"):
        return "Invalid action", 400
    note=request.form.get("note","").strip()
    status="verified" if action=="verify" else "rejected"
    conn=db()
    row=conn.execute("SELECT id FROM payments WHERE id=?", (pid,)).fetchone()
    if not row:
        return "Payment not found",404
    conn.execute("""UPDATE payments SET status=?,reviewed_at=CURRENT_TIMESTAMP,
                    review_note=? WHERE id=?""",(status,note,pid))
    conn.execute("INSERT INTO audit_log(payment_id,action,note) VALUES(?,?,?)",
                 (pid,action,note))
    conn.commit()
    flash("Payment ime-"+("verified." if status=="verified" else "rejected."), "success")
    return redirect(url_for("admin",status="pending"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))

if __name__=="__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

@app.template_filter('format_currency')
def format_currency(v):
    return f'{int(v):,}'
