"""PR0 PoC 最小长任务：建模 + 循环，用于验证 task 生命周期。"""
import itasca
import time

itasca.command("model new")
itasca.command("model large-strain on")
itasca.command("model domain extent -2 2 -2 2")
itasca.command("ball create id=1 position=(0,0) radius=0.5")
itasca.command("ball create id=2 position=(1.2,0) radius=0.5")
itasca.command("ball attribute density 2500 range id 1 2")
print("POC_TASK_MODEL_READY balls=2")

for i in range(1, 6):
    itasca.command("model cycle 100")
    print("POC_TASK_CYCLE step=%d cycles=%d" % (i, itasca.cycle()))
    time.sleep(0.5)

print("POC_TASK_DONE cycles=%d" % itasca.cycle())
