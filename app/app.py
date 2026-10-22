import os
import time
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'local-demo-only-change-me')
logging.basicConfig(level=logging.INFO)

@contextmanager
def database():
    connection = psycopg2.connect(
        host=os.getenv('DB_HOST', 'db'),
        port=int(os.getenv('DB_PORT', '5432')),
        user=os.getenv('DB_USER', 'admin'),
        password=os.getenv('DB_PASSWORD', ''),
        dbname=os.getenv('DB_NAME', 'expensetracker'),
        connect_timeout=5,
    )
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

SCHEMA = '''
CREATE TABLE IF NOT EXISTS expense_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    kind VARCHAR(10) NOT NULL CHECK (kind IN ('income','expense')),
    UNIQUE (name, kind)
);
CREATE TABLE IF NOT EXISTS expense_transactions (
    id BIGSERIAL PRIMARY KEY,
    kind VARCHAR(10) NOT NULL CHECK (kind IN ('income','expense')),
    category_id INTEGER NOT NULL REFERENCES expense_categories(id),
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    note VARCHAR(250) NOT NULL DEFAULT '',
    occurred_on DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_expense_transactions_occurred_on
ON expense_transactions (occurred_on DESC);
'''
SEED = [
 ('Lương', 'income'), ('Thưởng', 'income'), ('Thu khác', 'income'),
 ('Ăn uống', 'expense'), ('Đi lại', 'expense'), ('Nhà ở', 'expense'),
 ('Mua sắm', 'expense'), ('Học tập', 'expense'), ('Y tế', 'expense'), ('Chi khác', 'expense')
]

def initialize():
    for attempt in range(20):
        try:
            with database() as cur:
                cur.execute(SCHEMA)
                for name, kind in SEED:
                    cur.execute('INSERT INTO expense_categories(name, kind) VALUES (%s,%s) ON CONFLICT DO NOTHING', (name,kind))
            app.logger.info('database ready')
            return
        except psycopg2.OperationalError as exc:
            if attempt == 19:
                raise
            app.logger.warning('waiting for database (%s)', type(exc).__name__)
            time.sleep(2)

initialize()

def valid_month(raw):
    if raw:
        try:
            return datetime.strptime(raw, '%Y-%m').strftime('%Y-%m')
        except ValueError:
            pass
    return date.today().strftime('%Y-%m')

def money(raw):
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise ValueError('Số tiền không hợp lệ.')
    if not value.is_finite() or value <= 0 or value > Decimal('9999999999999'):
        raise ValueError('Số tiền phải lớn hơn 0 và trong giới hạn cho phép.')
    return value

def parse_day(raw):
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        raise ValueError('Ngày giao dịch không hợp lệ.')

def transaction_form():
    kind = request.form.get('kind', '')
    if kind not in ('income', 'expense'):
        raise ValueError('Loại giao dịch không hợp lệ.')
    amount = money(request.form.get('amount', ''))
    note = request.form.get('note', '').strip()
    if len(note) > 250:
        raise ValueError('Ghi chú không được vượt quá 250 ký tự.')
    day = parse_day(request.form.get('occurred_on', ''))
    try:
        category_id = int(request.form.get('category_id', ''))
    except (TypeError, ValueError):
        raise ValueError('Vui lòng chọn danh mục.')
    with database() as cur:
        cur.execute('SELECT id FROM expense_categories WHERE id=%s AND kind=%s', (category_id, kind))
        if not cur.fetchone():
            raise ValueError('Danh mục không thuộc loại giao dịch đã chọn.')
    return kind, category_id, amount, note, day

@app.get('/health')
def health():
    try:
        with database() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        return jsonify(status='ok', database='connected')
    except psycopg2.Error:
        return jsonify(status='error', database='unavailable'), 503

@app.get('/')
def index():
    month = valid_month(request.args.get('month'))
    selected_kind = request.args.get('kind', 'all')
    if selected_kind not in ('all', 'income', 'expense'):
        selected_kind = 'all'
    with database() as cur:
        cur.execute('SELECT id, name, kind FROM expense_categories ORDER BY kind, name')
        categories = cur.fetchall()
        cur.execute('''SELECT kind, COALESCE(SUM(amount),0) AS total
                       FROM expense_transactions
                       WHERE to_char(occurred_on, 'YYYY-MM')=%s GROUP BY kind''', (month,))
        totals = {r['kind']: r['total'] for r in cur.fetchall()}
        params = [month]
        kind_filter = ''
        if selected_kind != 'all':
            kind_filter = 'AND t.kind = %s'
            params.append(selected_kind)
        cur.execute(f'''SELECT t.id,t.kind,t.amount,t.note,t.occurred_on,c.name AS category_name,c.id AS category_id
                        FROM expense_transactions t JOIN expense_categories c ON c.id=t.category_id
                        WHERE to_char(t.occurred_on,'YYYY-MM')=%s {kind_filter}
                        ORDER BY t.occurred_on DESC,t.id DESC LIMIT 200''', tuple(params))
        transactions = cur.fetchall()
        cur.execute('''SELECT c.name, t.kind, SUM(t.amount) AS total
                       FROM expense_transactions t JOIN expense_categories c ON c.id=t.category_id
                       WHERE to_char(t.occurred_on,'YYYY-MM')=%s
                       GROUP BY c.name,t.kind ORDER BY total DESC LIMIT 10''', (month,))
        breakdown = cur.fetchall()
        cur.execute('SELECT COUNT(*) AS total FROM expense_transactions WHERE to_char(occurred_on,\'YYYY-MM\')=%s', (month,))
        count = cur.fetchone()['total']
    income = totals.get('income', Decimal('0'))
    expense = totals.get('expense', Decimal('0'))
    max_breakdown = max((float(item['total']) for item in breakdown), default=1.0)
    return render_template('index.html', categories=categories, transactions=transactions,
                           breakdown=breakdown, max_breakdown=max_breakdown, month=month,
                           selected_kind=selected_kind, income=income, expense=expense,
                           balance=income-expense, count=count, today=date.today().isoformat())

@app.post('/transactions')
def add_transaction():
    try:
        kind, category_id, amount, note, day = transaction_form()
        with database() as cur:
            cur.execute('''INSERT INTO expense_transactions(kind,category_id,amount,note,occurred_on)
                           VALUES (%s,%s,%s,%s,%s)''', (kind,category_id,amount,note,day))
        flash('Đã thêm giao dịch thành công.', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('index', month=valid_month(request.form.get('month'))))

@app.post('/transactions/<int:transaction_id>/edit')
def edit_transaction(transaction_id):
    try:
        kind, category_id, amount, note, day = transaction_form()
        with database() as cur:
            cur.execute('''UPDATE expense_transactions SET kind=%s,category_id=%s,amount=%s,note=%s,occurred_on=%s
                           WHERE id=%s RETURNING id''', (kind,category_id,amount,note,day,transaction_id))
            if not cur.fetchone():
                abort(404)
        flash('Đã cập nhật giao dịch.', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('index', month=valid_month(request.form.get('month'))))

@app.post('/transactions/<int:transaction_id>/delete')
def delete_transaction(transaction_id):
    with database() as cur:
        cur.execute('DELETE FROM expense_transactions WHERE id=%s RETURNING id', (transaction_id,))
        if not cur.fetchone():
            abort(404)
    flash('Đã xóa giao dịch.', 'success')
    return redirect(url_for('index', month=valid_month(request.form.get('month'))))

@app.post('/categories')
def add_category():
    name = request.form.get('name', '').strip()
    kind = request.form.get('kind', '')
    if not name or len(name) > 80 or kind not in ('income', 'expense'):
        flash('Tên hoặc loại danh mục không hợp lệ.', 'error')
    else:
        with database() as cur:
            cur.execute('INSERT INTO expense_categories(name,kind) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING id',(name,kind))
            created = cur.fetchone()
        flash('Đã thêm danh mục.' if created else 'Danh mục đã tồn tại.', 'success' if created else 'error')
    return redirect(url_for('index', month=valid_month(request.form.get('month'))))

@app.template_filter('vnd')
def vnd(value):
    value = Decimal(str(value or 0))
    return f'{value:,.0f}'.replace(',', '.') + ' ₫'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
