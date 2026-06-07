import sqlite3
import os
path = 'instance/edupage.db'
print('exists', os.path.exists(path))
if os.path.exists(path):
    con = sqlite3.connect(path)
    cur = con.cursor()
    print('tables:', cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())
    try:
        print('users:', cur.execute("SELECT email, mot_de_passe, nom, role FROM utilisateurs").fetchall())
    except Exception as e:
        print('query error:', e)
    con.close()
