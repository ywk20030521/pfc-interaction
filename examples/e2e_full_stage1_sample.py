"""E2E 完整物理过程 Stage1：密实试样成样（参照 brazil-pfc 方法）。

用 ball distribute + porosity + 圆墙围限 + 静力平衡，生成真正有接触的密实试样。
参数取自 brazil-pfc/br_geom.py（书稿第九章方法）。
"""
import itasca

itasca.command("model new")
itasca.command("model random 20001")
itasca.command("model domain extent -2 2 -2 2 condition reflect")
itasca.command("model large-strain on")

# 圆墙围限（半径 0.8）
itasca.command("wall generate circle position 0 0 radius 0.8")

# 密实颗粒：r=0.01~0.02, porosity=0.16, 限定在圆内
itasca.command("ball distribute radius 0.01 0.02 porosity 0.16 range circle center 0 0 radius 0.8")
itasca.command("ball attribute density 3000 damp 0.7")

# 接触模型：linear（成样 + 加载通用）
itasca.command("contact cmat default type ball-ball model linear property kn 1e7 ks 1e7 fric 0.5")
itasca.command("contact cmat default type ball-facet model linear property kn 1e7 ks 1e7 fric 0.5")

# 消除重叠 + 静力平衡
itasca.command("model cycle 2000 calm 20")
itasca.command("model solve")

bl = list(itasca.ball.list())
print("FULL_S1_BALLS", len(bl))
print("FULL_S1_CONTACTS", len(list(itasca.contact.list())))
print("FULL_S1_CYCLE", itasca.cycle())
print("FULL_S1_DONE stage=sample")
