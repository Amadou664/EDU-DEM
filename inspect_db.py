from config import Config
import sqlite3
import os

uri = Config.SQLALCHEMY_DATABASE_URI
print('DB URI:', uri)
if uri.startswith('sqlite:///'):
    path = uri.replace('sqlite:///','')
    print('path:', path)
    print('exists:', os.path.exists(path))
    if os.path.exists(path):
        con = sqlite3.connect(path)
        cur = con.cursor()
        tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print('tables:', tables)
        try:
            rows = cur.execute('SELECT email, mot_de_passe, nom, role FROM utilisateurs').fetchall()
            print('users:', rows)
        except Exception as e:
            print('query error:', e)
        con.close()
else:
    print('Unsupported URI')
