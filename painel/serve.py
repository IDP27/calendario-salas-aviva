"""Local/pilot entrypoint using Waitress, with no Node.js runtime."""
import os
from waitress import serve
from calendar_app import create_app

if __name__=='__main__':
    app=create_app()
    port=int(os.environ.get('CALENDAR_PORT','4174'))
    print(f'Calendário de salas: http://127.0.0.1:{port}',flush=True)
    serve(app,host='127.0.0.1',port=port,threads=6)
