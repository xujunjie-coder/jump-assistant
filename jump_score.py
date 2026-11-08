"""读取游戏分数，用本地已有截图生成的小型数字模板，不新增依赖。"""
import json
from jump_vision import rgb, read_png
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def glyphs(data,w,h):
    x0,x1=int(w*.085),int(w*.75)
    y0,y1=int(h*.155),int(h*.225)
    points={(x,y) for y in range(y0,y1) for x in range(x0,x1)
            if max(rgb(data,w,x,y))<135}
    columns=sorted({x for x,y in points})
    runs=[]
    for x in columns:
        if not runs or x>runs[-1][-1]+1:
            runs.append([x])
        else:
            runs[-1].append(x)
    result=[]
    for run in runs:
        part={(x,y) for x,y in points if run[0]<=x<=run[-1]}
        top,bottom=min(y for x,y in part),max(y for x,y in part)
        left,right=run[0],run[-1]
        if bottom-top<12:
            continue
        scale=28/(bottom-top+1)
        width=(right-left+1)*scale
        output=[]
        for y in range(32):
            for x in range(26):
                xx=round((x-(26-width)/2)/scale+left)
                yy=round((y-2)/scale+top)
                output.append(int((xx,yy) in part))
        result.append(output)
    return result


def read_score(data,w,h):
    templates=json.loads((ROOT/'jump_score_templates.json').read_text())
    output=[]
    for glyph in glyphs(data,w,h):
        error,digit=min((sum(a!=b for a,b in zip(glyph,t)),digit)
                        for digit,examples in templates.items() for t in examples)
        if error>100:
            return None
        output.append(digit)
    return int(''.join(output)) if output else None


def build_templates():
    sources=[('jump_measurements/trial_040/before.png','0'),
             ('jump_measurements/trial_055/after_5.png','1'),
             ('jump_measurements/validation_left/after_5.png','2'),
             ('jump_measurements/validation_right/after_5.png','3'),
             ('jump_measurements/validation_short/after_5.png','4'),
             ('jump_measurements/validation_pattern/after_5.png','5'),
             ('jump_runs/20261103_111755/031_before.png','689'),
             ('jump_runs/20261103_111755/032_before.png','721')]
    templates={str(i):[] for i in range(10)}
    for path,score in sources:
        g=glyphs(*read_png(ROOT/path))
        if len(g)!=len(score):
            raise ValueError(f'分数模板分割失败：{path}')
        for digit,shape in zip(score,g):
            templates[digit].append(shape)
    (ROOT/'jump_score_templates.json').write_text(json.dumps(templates))
    for path,expected in sources:
        actual=read_score(*read_png(ROOT/path))
        print(path,actual)
        assert actual==int(expected)


if __name__=='__main__':
    build_templates()
