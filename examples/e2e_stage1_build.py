"""E2E 验收 Stage 1：单轴压缩试样建模（成样 + 接触 + 加载墙）。

对应 V3.1 单轴压缩场景步骤 1-3。产出可通过 execute_code 查询的真实模型状态。
"""
import itasca

itasca.command("model new")
itasca.command("model large-strain on")
itasca.command("model domain extent -4 4 -6 6")

# 成样：40 个球组成的颗粒柱
# 修正（依据 Stage2 异常的用户决策）：显式设置接触模型与检测距离
# 否则球间不建立接触，timestep 爆炸、加载无效
itasca.command("contact cmat default model linear property kn 1e8 ks 5e7 fric 0.5 dp_nratio 0.7")
itasca.command("ball generate id=1 number=60 radius 0.25 0.35 box -2 2 -4 4")
itasca.command("ball attribute density 2500")

# 四面墙，每面为独立单墙（one-wall 避免 box 默认拆成 4 面导致 ID 冲突）
itasca.command("wall generate name 'top' box -2.6 2.6 4.3 4.8 one-wall")
itasca.command("wall generate name 'bottom' box -2.6 2.6 -4.8 -4.3 one-wall")
itasca.command("wall generate name 'left' box -2.6 -2.2 -4 4 one-wall")
itasca.command("wall generate name 'right' box 2.2 2.6 -4 4 one-wall")

print("E2E_S1_BALLS", len(list(itasca.ball.list())))
print("E2E_S1_WALLS", len(list(itasca.wall.list())))
print("E2E_S1_CONTACTS", len(list(itasca.contact.list())))
print("E2E_S1_DONE stage=build")
