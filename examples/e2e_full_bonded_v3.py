"""E2E 完整物理实验 v3：纯 Python 遍历接触力求稳定应力。

依据用户决策「改用测量圆重跑」——修正 v1/v2 中单点/ FISH 测量问题。
应力 = 上压板所有接触力 y 分量绝对值之和 / 试样宽度（参照 brazil-pfc br_measure）。
完整流程：成样 → 胶结 → 加载 → 稳定测量 → 峰值判定。
"""
import itasca

def wall_stress_y(top_wall, width=1.6):
    """遍历上压板接触，返回 (平均应力, 接触数)。"""
    fsum = 0.0
    nc = 0
    for ct in top_wall.contacts():
        fsum += abs(ct.force_global().y())
        nc += 1
    return fsum / width, nc

# ---------- 阶段1：成样 ----------
itasca.command("model new")
itasca.command("model random 20001")
itasca.command("model domain extent -2 2 -2 2 condition reflect")
itasca.command("model large-strain on")
itasca.command("wall generate circle position 0 0 radius 0.8")
itasca.command("ball distribute radius 0.01 0.02 porosity 0.16 range circle center 0 0 radius 0.8")
itasca.command("ball attribute density 3000 damp 0.7")
itasca.command("contact cmat default type ball-ball model linear property kn 1e7 ks 1e7 fric 0.5")
itasca.command("contact cmat default type ball-facet model linear property kn 1e7 ks 1e7 fric 0.5")
itasca.command("model cycle 2000 calm 20")
itasca.command("model solve")
print("EXP3_STAGE sample balls=%d contacts=%d" % (
    len(list(itasca.ball.list())), len(list(itasca.contact.list()))))

# ---------- 阶段2：胶结 ----------
itasca.command("contact cmat default type ball-facet model linear method deform emod 1e9 kratio 1.5 property fric 0.5")
itasca.command("""contact cmat default type ball-ball model linearpbond ...
        method deform emod 1e9 kratio 1.5 ...
        pb_deformability emod 1e9 kratio 1.5 ...
        property pb_coh 1e7 pb_ten 1e7 pb_fa 50 fric 0.5""")
itasca.command("contact cmat apply")
itasca.command("model clean")
itasca.command("model cycle 1")
itasca.command("model cycle 500 calm 20")
itasca.command("contact method bond gap 0.03")
itasca.command("model cycle 1")
itasca.command("model cycle 500 calm 20")
print("EXP3_STAGE bonded balls=%d contacts=%d" % (
    len(list(itasca.ball.list())), len(list(itasca.contact.list()))))

# ---------- 阶段3：换压板 ----------
itasca.command("wall delete")
itasca.command("wall generate name 'top' box -0.9 0.9 0.78 0.9 one-wall")
itasca.command("wall generate name 'bottom' box -0.9 0.9 -0.9 -0.78 one-wall")
top = [w for w in list(itasca.wall.list()) if w.name() == "top"][0]
bottom = [w for w in list(itasca.wall.list()) if w.name() == "bottom"][0]

# 让试样与上压板充分接触：静置若干步
itasca.command("model cycle 200 calm 10")
s0, nc0 = wall_stress_y(top)
print("EXP3_STAGE loading_start contacts=%d wall_contacts=%d stress0=%.1f" % (
    len(list(itasca.contact.list())), nc0, s0))

# ---------- 阶段4：加载 ----------
h0 = 1.56
itasca.command("wall attribute velocity (0,-0.01) range name 'top'")
itasca.command("wall attribute velocity (0,0.01) range name 'bottom'")

peak, peak_step, curve = 0.0, 0, []
for step in range(1, 201):
    itasca.command("model cycle 100")
    strain = (abs(top.disp_y()) + abs(bottom.disp_y())) / h0
    stress, nc = wall_stress_y(top)
    curve.append((step, strain, stress, nc))
    if step > 5 and stress > peak:
        peak, peak_step = stress, step
    if step % 20 == 0:
        print("EXP3_PT step=%d strain=%.5f stress=%.1f nc=%d" % (step, strain, stress, nc))
    if peak_step > 20 and step > peak_step + 10 and stress < peak * 0.7:
        print("EXP3_POSTPEAK step=%d peak=%.1f@%d" % (step, peak, peak_step))
        break

print("EXP3_RESULT peak=%.1f peak_step=%d peak_strain=%.5f samples=%d" % (
    peak, peak_step, curve[peak_step-1][1] if peak_step <= len(curve) else 0, len(curve)))
print("EXP3_DONE stage=complete")
