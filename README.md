# sqlpulse

> **Drop-in N+1 SQL detector for any Python SQL library**

[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org)
[![PyPI](https://img.shields.io/pypi/v/sqlpulse)](https://pypi.org/project/sqlpulse)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Install

```bash
pip install sqlpulse
```

## The problem

N+1 SQL queries happen when you loop over results and fire a new query for each row. They're invisible in development and brutal in production. Most N+1 detectors are ORM-specific. `sqlpulse` works with anything.

## Usage

```python
from sqlpulse import sqlpulse

with sqlpulse() as report:
    users = db.execute("SELECT * FROM users").fetchall()
    for user in users:
        db.execute(f"SELECT * FROM posts WHERE user_id = {user['id']}")

# sqlpulse: 101 queries in 340ms
# ⚠ N+1 detected: 'SELECT * FROM POSTS WHERE USER_ID = ?' ran 100x
```

### FastAPI middleware

```python
from fastapi import FastAPI
from sqlpulse import SQLPulseMiddleware

app = FastAPI()
app.add_middleware(SQLPulseMiddleware, slow_ms=100)
# Logs N+1 and slow queries for every request automatically
```

### SQLAlchemy

```python
from sqlpulse import patch_sqlalchemy
patch_sqlalchemy()   # one line — patches all SQLAlchemy engines globally
```

## Features

- ✅ Works with **any** SQL library (SQLAlchemy, raw psycopg2, sqlite3, etc.)
- ✅ ASGI/WSGI middleware for per-request monitoring
- ✅ Configurable slow query threshold
- ✅ `raise_on_n_plus_one=True` for CI enforcement
- ✅ Thread-safe — uses thread-local storage

## Architecture

```
sqlpulse/
├── sqlpulse/
│   ├── __init__.py   # public API
│   └── *.py          # core implementation
└── tests/
    └── test_*.py     # 3 passed — no API key needed
```

## License

MIT © [bhupendra05](https://github.com/bhupendra05)

---

*Part of the [bhupendra05 developer tools collection](https://github.com/bhupendra05)*
