"""PR0 PoC 长任务：用于验证 interrupt_task 中断能力。"""
import itasca
import time

itasca.command("model new")
itasca.command("model large-strain on")
itasca.command("model domain extent -2 2 -2 2")
itasca.command("ball create id=1 position=(0,0) radius=0.5")
itasca.command("ball create id=2 position=(1.2,0) radius=0.5")
itasca.command("ball attribute density 2500 range id 1 2")
print("POC_LONG_STARTED")

for i in range(1, 101):
    itasca.command("model cycle 100")
    if i % 10 == 0:
        print("POC_LONG_CYCLE step=%d cycles=%d" % (i, itasca.cycle()))
    time.sleep(0.2)

print("POC_LONG_DONE")
