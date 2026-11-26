"""E2E 完整物理过程 Stage2：单轴加载并采集应力-应变曲线。

前置：Stage1 已生成密实试样，本脚本在同一引擎状态上继续（删圆墙+压板已完成）。
依据用户决策「进入加载并采曲线」。

应变 = 上下压板相向位移 / 初始高度；应力 = 上压板竖向接触力 / 试样宽度。
采样到应力越过峰值并明显下降（峰后）即停止。
"""
import itasca

walls = {w.name(): w for w in list(itasca.wall.list())}
top = walls["top"]
bottom = walls["bottom"]

# 初始几何：压板初始间距（0.78 - (-0.78) = 1.56），用板的 disp_y 累计位移算应变
h0 = 1.56
width = 1.6  # 试样直径

itasca.command("wall attribute velocity (0,-0.01) range name 'top'")
itasca.command("wall attribute velocity (0,0.01) range name 'bottom'")

print("FULL_S2_START h0=%.4f width=%.2f balls=%d contacts=%d" % (
    h0, width, len(list(itasca.ball.list())), len(list(itasca.contact.list()))))

peak_stress = 0.0
peak_step = 0
curve = []

for step in range(1, 101):
    itasca.command("model cycle 100")
    # 两板相向位移之和 / 初始高度
    disp = abs(top.disp_y()) + abs(bottom.disp_y())
    strain = disp / h0
    fy = abs(top.force_contact_y())
    stress = fy / width
    curve.append((step, strain, stress))
    if stress > peak_stress:
        peak_stress = stress
        peak_step = step
    if step % 10 == 0:
        print("FULL_S2_PT step=%d strain=%.5f stress=%.2f" % (step, strain, stress))
    if peak_step > 0 and step > peak_step + 3 and stress < peak_stress * 0.8:
        print("FULL_S2_POSTPEAK step=%d peak=%.2f@%d" % (step, peak_stress, peak_step))
        break

print("FULL_S2_RESULT peak_stress=%.2f peak_step=%d samples=%d" % (peak_stress, peak_step, len(curve)))
print("FULL_S2_DONE stage=loading")
