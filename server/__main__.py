import os
import uvicorn

if __name__ == '__main__':
    local=os.getenv('APP_ENV')=='local'
    uvicorn.run('server.app:app',host='127.0.0.1' if local else '0.0.0.0',port=int(os.getenv('PORT','8000')),workers=1)
