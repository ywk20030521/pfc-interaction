"""PR0 PoC PFC3D 长任务：用于验证 3D 环境下的中断能力。"""
import itasca
import time

itasca.command("model new")
itasca.command("model large-strain on")
itasca.command("model domain extent -3 3 -3 3 -3 3")
itasca.command("contact cmat default model linear property kn 1e8 ks 5e7 fric 0.5")
itasca.command("ball generate id=1 number=40 radius 0.3 0.4 box -2 2 -2 2 -2 2")
itasca.command("ball attribute density 2500")
print("POC3D_LONG_STARTED")

for i in range(1, 101):
    itasca.command("model cycle 100")
    if i % 10 == 0:
        print("POC3D_LONG_CYCLE step=%d cycles=%d" % (i, itasca.cycle()))
    time.sleep(0.2)

print("POC3D_LONG_DONE")
