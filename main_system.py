import time
import datetime
import pigpio
import subprocess
import video_player # 動画関数

SENSER_PIN = 5
TIMEOUT_SECONDS = 60 * 30 # 人を検知したら何秒動画を再生するか
MAX_SECONDS = 60 * 150 # プロジェクターの最大連続稼働秒数
REST_SECONDS = 60 * 30 # プロジェクターの休憩時間

projector_power = True

def control_HDMI(is_on):
    if is_on:
        print("HDMI Output ONF(画面を起します)")
        subprocess.run("xset -display :0 dpms force on", shell=True)
    else:
        print("HDMI Output OFF(画面をスリープします)")
        subprocess.run("xset -display :0 dpms force off", shell=True)

def check_projector():
    try:
        res = subprocess.run('echo "pow 0" | cec-client -s -d 1', shell=True, capture_output=True, text=True, timeout=10)
        return "power status: on" in res.stdout
    except Exception as e:
        print(f"CEC状態確認エラー: {e}")
        return False

def projector_on():
    global projector_power
    
    print("プロジェクターON信号送信中...")
    subprocess.run(["cgir", "send", "-g", "17"] + ["power"] * 5)
    
    print("プロジェクターの起動を30秒待ちます...")
    time.sleep(30)
    
    print("プロジェクターの起動完了（再生準備OK）")

    projector_power = True
    return True

def projector_off():
    global projector_power

    print("プロジェクターOFF信号送信中...")
    command_1 = ["cgir", "send", "-g", "17"] + ["ok"] * 5
    command_2 = ["cgir", "send", "-g", "17"] + ["power"] * 5
    
    subprocess.run(command_1)
    time.sleep(1)
    subprocess.run(command_2)
    time.sleep(1)
    subprocess.run(command_1)

    print("シャットダウン処理のため10秒待機します...")
    time.sleep(10)
    
    print("プロジェクターの終了完了")

    projector_power = False
    return True

def work_time():
    now = datetime.datetime.now()
    hour = now.hour

    if hour >= 18 or hour < 8:
        return False
    return True

def run_system():
    pi = pigpio.pi()
    if not pi.connected:
        print("pigpiodが起動していません")
        return

    pi.set_mode(SENSER_PIN, pigpio.INPUT)

    # システムの状態を記憶する変数
    is_playing = False # 動画を再生中か否か
    last_time = 0 # 最後に人を検知した時間
    video_process = None
    first_on = True # プロジェクターの初回起動フラグ

    total_run_time = 0 # 累積で何秒動いたか
    session_start_time = 0 # 今回電源がONになった時刻
    last_off_time = 0 # 最後にプロジェクターの電源がOFFになった時刻

    is_cooldown = False # 強制クールダウン中か
    cooldown_start_time = 0

    print("自動広告システムを起動しました(終了はCtrl+C)")
    print("センサーの待機中です...")

    try:
        while True:
            current_time = time.time()

            # [1]夜間チェック
            if not work_time():
                if is_playing:
                    print("夜間モードの時間になりました。システムを停止します。")
                    total_run_time += (current_time - session_start_time) # 稼働時間を記録
                    last_off_time = current_time # 最後にプロジェクターをOFFにした時間
                    video_player.stop_video(video_process)
                    projector_off()
                    is_playing = False
                time.sleep(0.5)
                continue

            # [2]強制クールダウンの終了判定
            if is_cooldown:
                elapsed_cooldown = current_time - cooldown_start_time
                if elapsed_cooldown < REST_SECONDS:
                    time.sleep(1)
                    continue
                else:
                    print(f"{REST_SECONDS/60}分の強制クールダウン完了")
                    is_cooldown = False
                    total_run_time = 0

            # [3]累積稼働時間のチェック
            if is_playing:
                current_total_run = total_run_time + (current_time - session_start_time)

                if current_total_run > MAX_SECONDS:
                    print(f"実質的な稼働時間が{MAX_SECONDS/60}分を超えました！強制クールダウンに入ります。")
                    video_player.stop_video(video_process)
                    projector_off()
                    is_playing = False

                    is_cooldown = True
                    cooldown_start_time = current_time
                    total_run_time = current_total_run
                    last_off_time = current_time
                    continue
                     
            # 1.センサーの状態をチェック
            if pi.read(SENSER_PIN) == 1:
                # 人がいるからタイマーを現在時刻に更新
                last_time = current_time

                # もし待機中ならシステム起動
                if not is_playing:
                    if (current_time - last_off_time ) >= REST_SECONDS:
                        print(f"プロジェクターが{REST_SECONDS/60}分以上休んでいたので、稼働タイマーをリセットします")
                        total_run_time = 0
                    else:
                        print(f"プロジェクターが{REST_SECONDS/60}分以上休めていないので、稼働タイマーを引き継ぎます")
                
                    print("人を検知しました！動画再生を開始します！")

                    if first_on:
                        print("初回起動のため、プロジェクターON操作をスキップします")
                        video_process = video_player.start_video()
                        is_playing = True
                        first_on = False
                        session_start_time = current_time
                    else:
                        if projector_on(): # プロジェクターON
                            video_process = video_player.start_video()
                            is_playing = True
                            session_start_time = current_time

            # 2.再生中の「無人タイムアウト」チェック
            if is_playing:
                # もしラズパイ本体でCtrl+Cが押されたら
                if video_process is not None and video_process.poll() is not None:
                    print("\nラズパイ本体でCtrl+Cが押されました!")
                    raise KeyboardInterrupt
                    
                # 現在の時間 - 最後に検知した時間 = 無人だった時間
                if (current_time - last_time) > TIMEOUT_SECONDS:
                    print(f"\n{TIMEOUT_SECONDS}秒間誰も来なかったので、広告を終了します")
                    total_run_time += (current_time - session_start_time)
                    last_off_time = current_time
                    
                    video_player.stop_video(video_process)
                    projector_off()
                    is_playing = False
                    print("センサーの待機モードに入ります")
                    
            # 0.5秒ごとにループを回す(ラズパイの過労防止)
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nシステムを安全に終了します")
        if is_playing and video_process:
            video_player.stop_video(video_process)

        print("プロジェクターの電源を確認します。")
        if not projector_power:
            print("プロジェクターがOFFのため、起動して画面を映します。")
            projector_on()
        else:
            print("プロジェクターは既にONのため、電源ON操作を行いません。")

    finally:
        pi.stop()

# -----テスト-----
if __name__ == "__main__":
    run_system()
