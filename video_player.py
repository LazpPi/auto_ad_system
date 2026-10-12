import subprocess
import time

VIDEO_PATH = "/home/karakuri/cafe_project/HowToUse_SmartPayment.mp4"

def start_video():
    print(f"動画[{VIDEO_PATH}]の再生をします")
    try:
        process = subprocess.Popen(["mpv", "--fullscreen", "--loop","--no-audio", "--no-terminal", VIDEO_PATH], stdin=subprocess.DEVNULL)
        return process
    except FileNotFoundError:
        print("error : mpvがインストールされていないか、パスが間違っています")
        return None

def stop_video(process):
    if process is not None:
        print("動画の再生停止処理を開始します")
        process.terminate()

        try:
            process.wait(timeout=3)
            print("動画の再生を安全に停止しました")

        except subprocess.TimeoutExpired:
            print("応答がないため強制終了します")
            process.kill()
            process.wait()

# -----テスト-----
if __name__ == "__main__":
    print("動画再生テストをします")
    p = start_video()

    if p is not None:
        try:
            print("10秒間テストします(Ctrl+Cで終了)")
            time.sleep(10)

        except KeyboardInterrupt:
            print("\nCtrl+Cが押されました")
        finally:
            stop_video(p)
            print("テストを終了しました")
