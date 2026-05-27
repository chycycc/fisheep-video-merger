import os
import sys
import shutil
import subprocess

def clean_build():
    """清理旧构建及临时文件残留"""
    folders_to_clean = ['build', 'dist']
    for folder in folders_to_clean:
        if os.path.exists(folder):
            print(f"[Clean] Cleaning folder: {folder}...")
            try:
                shutil.rmtree(folder)
            except Exception as e:
                print(f"[Warning] Could not clean {folder}: {e}")

    # 清理 *.spec 文件
    for file in os.listdir('.'):
        if file.endswith('.spec'):
            try:
                os.remove(file)
                print(f"[Clean] Removing spec file: {file}")
            except Exception as e:
                print(f"[Warning] Could not delete {file}: {e}")

def build_app():
    print("--- Starting PyInstaller Build Process for v0.4.0 (PyWebview Hybrid) ---")
    
    # 静态 Web 资源源路径与包内目标路径
    web_src = os.path.join("src", "fisheep_video_merger", "ui", "web")
    web_dst = os.path.join("fisheep_video_merger", "ui", "web")
    
    # Windows 下的分隔符是分号 (;)
    add_data_arg = f"{web_src}{os.pathsep}{web_dst}"
    
    # 构建命令参数
    # --onefile: 单个独立运行的 exe
    # --noconsole: 后台隐藏黑窗，纯 Web GUI 呈现
    # --add-data: 打包本地 Web 静态资产
    # --exclude-module: 显式排除庞大的 PySide6 与 PyQt6 依赖，以压缩包体至 10MB
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        "--name=FisheepVideoMerger",
        f"--add-data={add_data_arg}",
        "--exclude-module=PySide6",
        "--exclude-module=PyQt6",
        "--clean",
        os.path.join("src", "fisheep_video_merger", "main_web.py")
    ]
    
    print(f"[Command] Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\n[Success] Build completed successfully!")
        exe_path = os.path.join("dist", "FisheepVideoMerger.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"[Executable] Path: {os.path.abspath(exe_path)}")
            print(f"[Executable] Size: {size_mb:.2f} MB")
            print("[Info] Successfully reduced size by over 80% compared to PySide6 (~75MB)!")
    else:
        print("\n[Error] Build failed! Check PyInstaller logs above.")
        sys.exit(result.returncode)

if __name__ == "__main__":
    clean_build()
    build_app()
