"""跳一跳的图像识别：仅使用 Python 标准库，不增加第三方依赖。"""
import collections
import math
import pathlib
import statistics
import struct
import zlib


def read_png(path):
    raw = pathlib.Path(path).read_bytes()
    offset, compressed = 8, bytearray()
    while offset < len(raw):
        n = struct.unpack('>I', raw[offset:offset + 4])[0]
        kind, data = raw[offset + 4:offset + 8], raw[offset + 8:offset + 8 + n]
        if kind == b'IHDR':
            w, h, depth, color, _, _, interlace = struct.unpack('>IIBBBBB', data)
        elif kind == b'IDAT':
            compressed.extend(data)
        offset += n + 12
    if depth != 8 or color not in (2, 6) or interlace:
        raise ValueError('模板需要普通 RGB/RGBA PNG 图片。')
    channels = 4 if color == 6 else 3
    stride = w * channels
    rows, previous, stream = [], bytearray(stride), zlib.decompress(compressed)
    offset = 0
    for _ in range(h):
        mode = stream[offset]
        row = bytearray(stream[offset + 1:offset + 1 + stride])
        offset += stride + 1
        for i in range(stride):
            a = row[i - channels] if i >= channels else 0
            b = previous[i]
            c = previous[i - channels] if i >= channels else 0
            if mode == 1:
                predictor = a
            elif mode == 2:
                predictor = b
            elif mode == 3:
                predictor = (a + b) // 2
            elif mode == 4:
                p = a + b - c
                pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                predictor = a if pa <= pb and pa <= pc else b if pb <= pc else c
            else:
                predictor = 0
            row[i] = (row[i] + predictor) & 255
        rows.append(row)
        previous = row
    bgra = bytearray(w * h * 4)
    for y, row in enumerate(rows):
        for x in range(w):
            i, j = x * channels, (y*w+x)*4
            bgra[j:j+4] = bytes((row[i+2], row[i+1], row[i], 255))
    return bytes(bgra), w, h


def save_png(path, data, w, h):
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        for x in range(w):
            i = (y*w+x)*4
            rows.extend((data[i+2], data[i+1], data[i]))
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind+body))
    pathlib.Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' +
        chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
        chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def rgb(data, w, x, y):
    i = (y*w+x)*4
    return data[i+2], data[i+1], data[i]


def purple(color):
    r, g, b = color
    return 15 < r < 160 and 10 < g < 140 and 25 < b < 180 and b > r+4 and b > g+8


def row_background(data,w,y):
    # 平台可能伸到窗口边缘，不能把左右边缘的像素直接认作背景。
    # 同一行的背景颜色基本一致，分组后选覆盖最广的颜色。
    groups=collections.defaultdict(list)
    for x in range(6,w-6,4):
        color=rgb(data,w,x,y)
        groups[tuple(c//12 for c in color)].append(color)
    colors=max(groups.values(),key=len)
    return tuple(sorted(c[k] for c in colors)[len(colors)//2] for k in range(3))


def components(points, w):
    remaining = set(points)
    result = []
    while remaining:
        seed = remaining.pop()
        queue, group = [seed], [seed]
        while queue:
            p = queue.pop()
            x = p % w
            for q in (p-w, p+w, p-1 if x else -1, p+1 if x+1 < w else -1):
                if q in remaining:
                    remaining.remove(q)
                    queue.append(q)
                    group.append(q)
        result.append(group)
    return result


def find_piece(data, w, h, template_path):
    template, tw, th = read_png(template_path)
    foreground = [(x, y) for y in range(th) for x in range(tw)
                  if purple(rgb(template, tw, x, y))]
    xmin, xmax = min(x for x,y in foreground), max(x for x,y in foreground)
    ymin, ymax = min(y for x,y in foreground), max(y for x,y in foreground)
    fw, fh = xmax-xmin+1, ymax-ymin+1
    # 背景不同也能匹配：只比较模板中棋子自身的像素。
    sample = foreground[::max(1, len(foreground)//160)]
    points = [y*w+x for y in range(int(h*.25), int(h*.86))
              for x in range(8, w-8) if purple(rgb(data,w,x,y))]
    groups = [g for g in components(points,w) if len(g) >= 8]
    candidates = []
    # 紫色平台会与身体连成同一个色块。用独立的圆形头部推算完整模板位置，
    # 再核对模板像素，不能要求身体色块必须和平台分离。
    template_groups=components([y*tw+x for x,y in foreground],tw)
    template_head=min((g for g in template_groups if len(g)>8),
                      key=lambda g:min(p//tw for p in g))
    head_width=max(p%tw for p in template_head)-min(p%tw for p in template_head)+1
    head_height=max(p//tw for p in template_head)-min(p//tw for p in template_head)+1
    template_head_cx=(min(p%tw for p in template_head)+max(p%tw for p in template_head))/2
    head_top=min(p//tw for p in template_head)
    def match_heads(heads):
        for head in heads:
            hx0,hx1=min(p%w for p in head),max(p%w for p in head)
            hy0,hy1=min(p//w for p in head),max(p//w for p in head)
            hw,hh=hx1-hx0+1,hy1-hy0+1
            if not (w*.025<hw<w*.1 and .75<hw/hh<1.3 and .5<len(head)/(hw*hh)<.95):
                continue
            scale=(hw/head_width+hh/head_height)/2
            left=(hx0+hx1)/2-(template_head_cx-xmin)*scale
            upper=hy0-(head_top-ymin)*scale
            right,bottom=left+(fw-1)*scale,upper+(fh-1)*scale
            if left<0 or right>=w or upper<0 or bottom>=h:
                continue
            error=0
            for tx,ty in sample:
                sx,sy=round(left+(tx-xmin)*scale),round(upper+(ty-ymin)*scale)
                a,b=rgb(template,tw,tx,ty),rgb(data,w,sx,sy)
                error+=sum(abs(a[k]-b[k]) for k in range(3))/3
            foot=((left+right)/2,round(bottom))
            candidates.append((error/len(sample),foot,tuple(round(v) for v in (left,upper,right,bottom))))
    match_heads(groups)
    for body in groups:
        x0, x1 = min(p%w for p in body), max(p%w for p in body)
        y0, y1 = min(p//w for p in body), max(p//w for p in body)
        # 头和身体中间有缝：把正上方的头部连同身体一起匹配。
        for head in groups:
            hx = sum(p%w for p in head)/len(head)
            hy0, hy1 = min(p//w for p in head), max(p//w for p in head)
            if y0-fh < hy1 < y0 and abs(hx-(x0+x1)/2) < (x1-x0+1)*.65:
                left = min(x0, min(p%w for p in head))
                right = max(x1, max(p%w for p in head))
                bw, bh = right-left+1, y1-hy0+1
                if not .6 < (bw/bh)/(fw/fh) < 1.5:
                    continue
                error = 0
                for tx,ty in sample:
                    sx = min(w-1, left+round((tx-xmin)*(bw-1)/max(1,fw-1)))
                    sy = min(h-1, hy0+round((ty-ymin)*(bh-1)/max(1,fh-1)))
                    a,b = rgb(template,tw,tx,ty), rgb(data,w,sx,sy)
                    error += sum(abs(a[k]-b[k]) for k in range(3))/3
                candidates.append((error/len(sample), ((x0+x1)/2,y1), (left,hy0,right,y1)))
    if not candidates or min(candidates)[0] > 45:
        # 阴影也满足宽松的紫色条件，可能把头、身体和平台连成一块。
        # 只在常规匹配失败时，用更深的棋子颜色拆分头部；仍核验完整模板。
        dark_points = []
        for point in points:
            r, g, _ = rgb(data, w, point % w, point // w)
            if r < 110 and g < 100:
                dark_points.append(point)
        match_heads([g for g in components(dark_points, w) if len(g) >= 8])
    if not candidates:
        raise ValueError('未找到棋子模板，请让游戏窗口完整显示且不要被其他窗口挡住。')
    error, foot, box = min(candidates)
    if error > 45:
        raise ValueError('棋子模板匹配不足，请重新截取棋子图片。')
    return foot, box, round(error,2)


def find_center_mark(data,w,h,center,half_width):
    """只在目标顶面内寻找白点，或白色底面包围的灰色中心点。"""
    cx,cy=center
    half_height=half_width/math.sqrt(3)
    pools={'bright':[],'dark':[]}
    for y in range(max(0,int(cy-half_height*.7)),min(h,int(cy+half_height*.7)+1)):
        for x in range(max(0,int(cx-half_width*.7)),min(w,int(cx+half_width*.7)+1)):
            if abs(x-cx)/half_width+abs(y-cy)/half_height>.72:
                continue
            color=rgb(data,w,x,y)
            if min(color)>225 and max(color)-min(color)<25 and sum(color)/3>235:
                pools['bright'].append(y*w+x)
            elif min(color)>35 and max(color)<220 and max(color)-min(color)<22:
                pools['dark'].append(y*w+x)
    candidates=[]
    groups=[(kind,group) for kind,points in pools.items() for group in components(points,w)]
    for kind,group in groups:
        x0,x1=min(p%w for p in group),max(p%w for p in group)
        y0,y1=min(p//w for p in group),max(p//w for p in group)
        bw,bh=x1-x0+1,y1-y0+1
        # 排除整块白顶面、大图案和零碎高光，不把它们当作小标记。
        if not (max(5,half_width**2*.002)<len(group)<half_width**2*.13
                and 2<=bw<=half_width*.48 and 2<=bh<=half_height*.55
                and 1.1<=bw/bh<=3.5 and len(group)/(bw*bh)>.45):
            continue
        mx,my=sum(p%w for p in group)/len(group),sum(p//w for p in group)/len(group)
        if abs(mx-cx)>half_width*.3 or abs(my-cy)>half_height*.35:
            continue
        padding=max(3,round(half_width*.06))
        ring=[rgb(data,w,x,y) for x,y in
              ((x0-padding,y0-padding),(x1+padding,y0-padding),
               (x0-padding,y1+padding),(x1+padding,y1+padding),
               (round(mx),y0-padding),(round(mx),y1+padding))
              if 0<=x<w and 0<=y<h]
        brightness=sum(sum(rgb(data,w,p%w,p//w))/3 for p in group)/len(group)
        ring_brightness=sum(sum(c)/3 for c in ring)/len(ring)
        contrast=brightness-ring_brightness if kind=='bright' else ring_brightness-brightness
        if kind=='dark' and (ring_brightness<225 or sum(min(c)>220 and max(c)-min(c)<25 for c in ring)<len(ring)*.8):
            continue
        if contrast<18:
            continue
        distance=abs(mx-cx)/half_width+abs(my-cy)/half_height
        candidates.append((distance,(round(mx,1),round(my,1)),(x0,y0,x1,y1),kind))
    if candidates:
        _,point,box,kind=min(candidates)
        return point,box,kind
    return None


def precise_surface_center(platform,w,top,cx,fallback):
    """只使用顶面上半部的轮廓，避免阴影、侧面、相邻平台扩大半宽。"""
    edges={}
    for p in platform:
        x,y=p%w,p//w
        if cx<=x<cx+w*.31 and top<=y<top+w*.24:
            edges[y]=max(edges.get(y,cx),x)
    upper=[(y-top,x-cx) for y,x in edges.items() if 3<=y-top<=10 and x>cx]
    if len(upper)<5:
        return fallback,'width_fallback'
    slope=statistics.median(x/z for z,x in upper)
    if slope>2.6:
        # 等距投影下椭圆的纵横半轴比为 1/sqrt(3)，用上半边拟合半径。
        radii=[(x*x+3*z*z)/(2*math.sqrt(3)*z) for z,x in upper]
        radius=statistics.median(radii)
        height=(top+radius/math.sqrt(3)+fallback[1])/2
        return (float(cx),round(height)),'ellipse_upper_edge'
    previous=None
    stable=0
    beginning=None
    for y in sorted(edges):
        edge=edges[y]
        if previous is not None and edge-cx>6 and abs(edge-previous)<=1:
            if not stable:
                beginning=y-1
            stable+=1
            if stable>=4:
                return (float(cx),beginning+1),'diamond_corner'
        else:
            stable=0
        previous=edge
    return fallback,'width_fallback'


def find_target(data,w,h,piece,details=False):
    # 背景有轻微渐变，按行估计；边缘被平台覆盖时也不受影响。
    # 只排除棋子本身的宽度；近距离的小平台可能就在棋子旁边。
    x0,x1 = (int(piece[0]+w*.04),w-5) if piece[0]<w/2 else (5,int(piece[0]-w*.04))
    mask = []
    for y in range(int(h*.27),int(piece[1])):
        background=row_background(data,w,y)
        for x in range(x0,x1):
            color = rgb(data,w,x,y)
            difference = max(abs(color[k]-background[k]) for k in range(3))
            # 木凳等浅色顶面与背景只相差十几个色阶，不能使用过高阈值。
            if difference > 8:
                mask.append(y*w+x)
    groups = [g for g in components(mask,w) if len(g) > w*w*.0015]
    if not groups:
        raise ValueError('未找到下个平台。')
    # 平台和它的阴影连成一片，顶端仍然是平台顶面的上顶点。
    platform = min(groups,key=lambda g:min(p//w for p in g))
    top = min(p//w for p in platform)
    tip = [p%w for p in platform if p//w <= top+1]
    cx = round(sum(tip)/len(tip))
    # 用平台自身的半宽计算顶面中心，不要求它达到屏幕宽度的某个比例。
    # 当前游戏的等距投影：顶面的半高约为半宽 / sqrt(3)。
    # 菱形方块和圆柱顶面的椭圆都适用；右边缘也避开了左侧阴影。
    half_width=max(p%w for p in platform)-cx
    if half_width<=2:
        raise ValueError('平台顶面中心识别失败。')
    geometric=(float(cx),round(top+half_width/math.sqrt(3)))
    geometric,geometry_method=precise_surface_center(platform,w,top,cx,geometric)
    mark=find_center_mark(data,w,h,geometric,half_width)
    target=mark[0] if mark else geometric
    if details:
        return {'target':target,'target_method':'center_mark' if mark else 'surface_geometry',
                'geometric_center':geometric,'mark_box':mark[1] if mark else None,
                'mark_kind':mark[2] if mark else None,'geometry_method':geometry_method}
    return target
