"""开发启动器：同时启动独立前后端，Ctrl+C 关闭本轮进程组。"""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    for port in (8000,5173):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:
                raise SystemExit(f'端口 {port} 已被占用。请先关闭已有开发服务，再运行启动器。')
    if not (ROOT/'frontend/node_modules').is_dir():
        raise SystemExit('请先执行 npm --prefix frontend ci 安装前端依赖。')
    processes=[]
    try:
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','security_rag.api:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,start_new_session=True))
        processes.append(subprocess.Popen(['npm','--prefix',str(ROOT/'frontend'),'run','dev'],cwd=ROOT,start_new_session=True))
        print('\n前端 http://127.0.0.1:5173/   后端文档 http://127.0.0.1:8000/docs\nCtrl+C 同时停止前后端。\n',flush=True)
        while all(p.poll() is None for p in processes):time.sleep(.3)
        raise SystemExit('一个开发服务已退出，正在停止另一个服务。')
    except KeyboardInterrupt:
        print('\n正在停止开发服务…',flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
        for process in processes:
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()


if __name__=='__main__':main()
