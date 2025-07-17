import sqlite3
cur =sqlite3.connect("./maindb.db").cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cur.fetchall())