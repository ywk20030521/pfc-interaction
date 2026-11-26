"""PR0 PoC PFC3D 最小长任务：验证 3D 环境下 task 生命周期。"""
import itasca
import time

itasca.command("model new")
itasca.command("model large-strain on")
itasca.command("model domain extent -3 3 -3 3 -3 3")
itasca.command("contact cmat default model linear property kn 1e8 ks 5e7 fric 0.5")
itasca.command("ball generate id=1 number=40 radius 0.3 0.4 box -2 2 -2 2 -2 2")
itasca.command("ball attribute density 2500")
print("POC3D_TASK_READY balls=%d" % len(list(itasca.ball.list())))

for i in range(1, 4):
    itasca.command("model cycle 100")
    print("POC3D_CYCLE step=%d cycles=%d contacts=%d" % (
        i, itasca.cycle(), len(list(itasca.contact.list()))))
    time.sleep(0.5)

print("POC3D_DONE cycles=%d" % itasca.cycle())
