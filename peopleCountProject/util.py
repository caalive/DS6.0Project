# 线与线的碰撞检测：叉乘的方法判断两条线是否相交
# 计算叉乘符号
def ccw(A, B, C):
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

# 检测AB和CD两条直线是否相交
def intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

# 获取tarcker坐标
def get_center_coord(trackerRectInfo):
    trackerRectInfo.border_color.set(0.0, 1.0, 1.0, 1.0)
    trackerRectInfo.border_width = 1
    return (int(trackerRectInfo.left), int(trackerRectInfo.top), int(trackerRectInfo.width), int(trackerRectInfo.height))

# frame 比对
def compareCoords(prev, curt, crossline):
    up = 0
    down = 0
    if len(prev):
        for k, v in prev.items():
            if k in curt:
                (x, y) = (int(curt[k][0]), int(curt[k][1]))
                (w, h) = (int(curt[k][0] + curt[k][2]), int(curt[k][1] + curt[k][3]))
                
                (x2, y2) = (int(v[0]), int(v[1]))
                (w2, h2) = (int(v[0] + v[2]), int( v[1] + v[3]))
                p1 = (int(x2 + (w2 - x2) / 2), int(y2 + (h2 - y2) / 2))
                p0 = (int(x + (w - x) / 2), int(y + (h - y) / 2))
                if intersect(p0, p1, crossline[0], crossline[1]):
                    if y2 < y:
                        down += 1
                    else:
                        up += 1
    return (up, down)