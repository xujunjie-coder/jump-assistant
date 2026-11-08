"""自动找棋子、找下个平台中心，按实测公式蓄力跳跃。"""
import argparse
import json
import math
import time
from jump_game import ROOT, observe, press, user32, landing_state


# 当前电脑实测：窗口宽 406 像素时，横向速度约 239 像素/秒。
# 窗口大小变化时，按宽度比例换算。
REFERENCE_WIDTH = 406
SECONDS_PER_PIXEL = 0.00419208
LONG_PRESS_THRESHOLD = 0.65
LONG_PRESS_CORRECTION = 0.09321
LONG_PRESS_CALIBRATED_MAX = 1.0
LONG_PRESS_FADE_END = 1.1


def calculate_press_time(piece, target, window_width):
    horizontal_distance = abs(target[0] - piece[0])
    upward_distance = piece[1] - target[1]
    # 游戏中左右两条跳跃轴均向上倾斜约 30 度。
    # 将目标相对棋子的二维位移投影到跳跃轴，避免只算横向而积累纵向偏差。
    equivalent_horizontal_distance = (horizontal_distance + upward_distance / math.sqrt(3)) * .75
    normalized_distance = equivalent_horizontal_distance * REFERENCE_WIDTH / window_width
    base_seconds = normalized_distance * SECONDS_PER_PIXEL
    # 最近的真实落点表明，较长按压会逐渐偏远；只修正长按区间。
    # 校准数据止于约 1 秒，不能把这个修正无限外推到超长跳。
    weight=max(0,min(1,(LONG_PRESS_FADE_END-base_seconds)/
                     (LONG_PRESS_FADE_END-LONG_PRESS_CALIBRATED_MAX)))
    return base_seconds - weight*LONG_PRESS_CORRECTION*max(0,base_seconds-LONG_PRESS_THRESHOLD)


def main(steps=0):
    print('请先进入游戏，保持游戏窗口完整可见。3 秒后开始。',flush=True)
    print('按 F8 停止；在终端中也可用 Ctrl+C 停止。',flush=True)
    time.sleep(3)
    window=user32.FindWindowW(None,'跳一跳')
    user32.SetForegroundWindow(window)
    time.sleep(.4)
    index=0
    folder=ROOT/'jump_runs'/time.strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True,exist_ok=True)

    while not user32.GetAsyncKeyState(0x77) & 0x8000:
        before=observe(str(folder/f'{index+1:03d}_before.png'))
        seconds=calculate_press_time(before['piece'],before['target'],before['region'][2])
        method='中心标记' if before['target_method']=='center_mark' else '顶面轮廓'
        print(f"第 {index+1} 跳：棋子 {before['piece']}，目标中心 {before['target']}（{method}），按住 {seconds:.3f} 秒",flush=True)
        actual=press(seconds)
        time.sleep(2.2)
        index+=1
        after=landing_state(str(folder/f'{index:03d}_after.png'))
        gain=after['score']-before['score'] if after['score'] is not None and before['score'] is not None else None
        print(f"落地分数：{after['score']}，本跳得分：{gain}，计时偏差：{(actual-seconds)*1000:.2f} 毫秒",flush=True)
        record={'jump':index,'before':before,'requested_seconds':seconds,'actual_seconds':actual,
                'after':after,'score_gain':gain,'timing_model':'bounded_long_press_20261103',
                'long_press_threshold':LONG_PRESS_THRESHOLD,'long_press_correction':LONG_PRESS_CORRECTION}
        with (folder/'run.jsonl').open('a',encoding='utf-8') as output:
            output.write(json.dumps(record,ensure_ascii=False)+'\n')
        if steps and index>=steps:
            break
    print('已停止。',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps',type=int,default=0,help='只测试指定跳数；默认持续跳跃')
    args=parser.parse_args()
    try:
        main(args.steps)
    except KeyboardInterrupt:
        print('\n已停止。')
    except ValueError as error:
        print('已停止：',error)
