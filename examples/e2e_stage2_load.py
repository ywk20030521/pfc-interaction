"""E2E 验收 Stage 2：压密/加载（依据用户在 Stage1 检查点的决策：进入压密加载）。

决策链：用户 ACCEPT「进入压密加载」→ Agent 结构化 → 执行。

阶段级检查点策略：本脚本运行到固定 cycle 数即结束并汇报，
不在脚本内部等待用户输入（符合 V3.1「阶段级检查点」而非任意位置暂停）。
"""
import itasca

# 设置上下墙相向速度进行单轴压缩（低速率，准静态）
itasca.command("wall attribute velocity (0,-0.02) range name 'top'")
itasca.command("wall attribute velocity (0,0.02) range name 'bottom'")

# 记录初始状态
ys0 = [b.pos().y() for b in list(itasca.ball.list())]
print("E2E_S2_START balls=%d y_min=%.3f y_max=%.3f" % (
    len(ys0), min(ys0), max(ys0)))

# 分 5 段循环，每段 100 cycle，段间查询状态（模拟周期汇报，不打扰用户）
for step in range(1, 6):
    itasca.command("model cycle 100")
    contacts = len(list(itasca.contact.list()))
    ys = [b.pos().y() for b in list(itasca.ball.list())]
    print("E2E_S2_STEP step=%d cycle=%d contacts=%d y_range=(%.3f,%.3f)" % (
        step, itasca.cycle(), contacts, min(ys), max(ys)))

ys_end = [b.pos().y() for b in list(itasca.ball.list())]
print("E2E_S2_DONE cycle=%d contacts=%d height=%.3f" % (
    itasca.cycle(), len(list(itasca.contact.list())), max(ys_end) - min(ys_end)))
