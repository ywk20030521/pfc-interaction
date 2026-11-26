# -*- coding: utf-8 -*-
"""4.0 science-layer acceptance: triaxial compression with servo confinement.

Addresses the three confirmed physics defects from the 2026-11-26 run:
  - confinement never reached target (5989 Pa vs 1 MPa) -> calibrated servo
  - bond retention 416/1251 = 0.33 -> start from tx_initial.sav (100% bonded)
    and monitor retention; report honestly if compaction still breaks bonds
  - C2/C3 peak at last sample -> extend target strain to 12% (post-peak)

Runs through the REAL itasca-mcp bridge (PFC3D Console). Produces CSV/summary
with a real tool_task_id. No fabricated data.

Run (bridge must be online with PFC3D):
    python examples/v40/science_tx3d.py 1e6
"""

from __future__ import annotations

import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from adapters.itasca_mcp import ItascaMcpAdapter, BridgeUnavailable  # noqa: E402

TX_BASE = os.path.join(os.path.dirname(BASE), "outputs", "triaxial_3d", "v40_science")
SAV = os.path.join(os.path.dirname(BASE), "outputs", "triaxial_3d", "work", "tx_initial.sav")
os.makedirs(os.path.join(TX_BASE, "data"), exist_ok=True)
os.makedirs(os.path.join(TX_BASE, "work"), exist_ok=True)


def main(target_pa: float = 1.0e6):
    adapter = ItascaMcpAdapter()
    health = adapter.health()
    if "3d" not in str(SAV) and health.get("runtime_mode") != "console":
        raise RuntimeError("science script requires PFC3D Console bridge")
    print("[BRIDGE]", health.get("version"), health.get("runtime_mode"))

    # Build the Python driver as ONE execute_code call (bridge splits it).
    # The driver uses calibrated stepwise servo instead of wall servo velocity
    # limits, which is the root cause of the earlier confinement failure.
    code = r'''
import itasca, json, os, time
from collections import Counter

TARGET = __TARGET__
BASE = r"__BASE__"
SAV = r"__SAV__"
CSV = BASE + "/data/tx_science___TAG__.csv"
SUMMARY = BASE + "/data/tx_science___TAG___summary.json"
A_XY = 0.04*0.04
A_LAT = 0.04*0.08
H0 = 0.08
TARGET_STRAIN = 0.12
SAMPLE_EVERY = 400
MAX_LOAD_CYCLES = 120000

itasca.command("model restore '%s'" % SAV)
itasca.command("model large-strain on")

# --- wall seating: move walls just outside specimen to avoid servo overshoot
bs = list(itasca.ball.list())
xmin=min(b.pos().x() for b in bs); xmax=max(b.pos().x() for b in bs)
ymin=min(b.pos().y() for b in bs); ymax=max(b.pos().y() for b in bs)
zmin=min(b.pos().z() for b in bs); zmax=max(b.pos().z() for b in bs)
gap=0.0003
for wid, xyz in ((1,(0,0,zmin-gap)),(2,(0,0,zmax+gap)),
                 (3,(xmin-gap,0,0)),(4,(xmax+gap,0,0)),
                 (5,(0,ymin-gap,0)),(6,(0,ymax+gap,0))):
    itasca.wall.find(wid).set_pos(xyz)
for wid in range(1,7):
    itasca.wall.find(wid).set_disp((0,0,0))
print("SEATED x",round(xmin,5),round(xmax,5),"z",round(zmin,5),round(zmax,5))

def lateral():
    w3,w4,w5,w6=(itasca.wall.find(i) for i in (3,4,5,6))
    sx=0.5*(abs(w3.force_contact().x())+abs(w4.force_contact().x()))/A_LAT
    sy=0.5*(abs(w5.force_contact().y())+abs(w6.force_contact().y()))/A_LAT
    return 0.5*(sx+sy)

def bonded():
    return sum(1 for c in itasca.contact.list() if c.prop("pb_state")==3)

b0 = bonded()
print("BONDED_START", b0)

# --- calibrated stepwise servo for confinement (root-cause fix for B06)
# Move lateral walls inward by small steps, settle, measure d(sigma)/d(x).
# BUG-T05b: wall.pos() does NOT track set_pos/velocity reliably (B05).
# Track the commanded position in software to avoid reading stale pos().
_wall_pos = {i: itasca.wall.find(i).pos() for i in (3,4,5,6)}
def move_lateral(dx):
    # dx>0 compresses: walls 3(+x),4(-x),5(+y),6(-y)
    for wid, sgn in ((3,-1),(4,1),(5,-1),(6,1)):
        w=itasca.wall.find(wid)
        p=_wall_pos[wid]
        if wid in (3,4):
            new=(p.x()+sgn*dx,p.y(),p.z())
        else:
            new=(p.x(),p.y()+sgn*dx,p.z())
        w.set_pos(new)
        _wall_pos[wid]=new  # BUG-T05b: never re-read pos(); it is stale under motion

RELAX=0.08; MAX_DX=0.0002; SETTLE=200; TOL=0.05
cons=0; converged=False; slope=None
for it in range(120):
    s=lateral()
    ratio=s/TARGET if TARGET>0 else 0
    if it%10==0:
        print("CONF_IT",it,"P_MPa",round(s/1e6,4),"ratio",round(ratio,4),"bonded",bonded())
    if abs(1-ratio)<=TOL:
        converged=True; break
    if slope is None:
        dx=MAX_DX; move_lateral(dx); itasca.command("model cycle %d calm 5" % SETTLE); cons+=SETTLE
        s1=lateral(); slope=(s1-s)/dx if dx else -1e9
        if abs(slope)<1e3: slope=-1e8
        print("SLOPE",slope)
        continue
    step=RELAX*(TARGET-s)/slope
    step=max(-MAX_DX,min(MAX_DX,step))
    move_lateral(step); itasca.command("model cycle %d calm 5" % SETTLE); cons+=SETTLE
    s2=lateral()
    if abs(step)>1e-12:
        sm=(s2-s)/step
        if abs(sm)>1e3: slope=0.6*slope+0.4*sm

s_conf=lateral(); b_load=bonded()
print("CONF_DONE converged",converged,"P_MPa",round(s_conf/1e6,4),
      "ratio",round(s_conf/TARGET,4),"bonded",b_load,"retention",round(b_load/b0,4) if b0 else 0)

# --- axial loading: displacement controlled, extend to 12% strain for post-peak
# BUG-T05 fix: maintain confinement by position servo at every sub-step.
# Native `wall servo` triggers bridge 0.6.17 cycle-callback re-entrancy (BUG-T07),
# so use the same calibrated move_lateral() with higher frequency instead.
dt=itasca.timestep()
v_ax=TARGET_STRAIN*H0/(MAX_LOAD_CYCLES*dt)
itasca.command("wall attribute velocity (0,0,0) range id 1")
itasca.command("wall attribute velocity (0,0,-%g) range id 2" % v_ax)
print("LOAD v_ax",v_ax,"dt",dt)

rows=[]; peak_i=0; peak_s=-1
for step in range(MAX_LOAD_CYCLES//SAMPLE_EVERY):
    # sub-stepped confinement control: 4 position corrections per sample
    for _ in range(4):
        itasca.command("model cycle %d" % (SAMPLE_EVERY//4))
        conf_now=lateral()
        if slope is not None and abs(conf_now-TARGET) > 0.05*TARGET:
            corr=RELAX*(TARGET-conf_now)/slope
            corr=max(-MAX_DX,min(MAX_DX,corr))
            move_lateral(corr)
    disp=abs(itasca.wall.find(2).disp().z())
    strain=disp/H0
    sig=abs(itasca.wall.find(2).force_contact().z())/A_XY
    conf=lateral(); bd=bonded(); nc=len(list(itasca.contact.list()))
    rows.append([cons+(step+1)*SAMPLE_EVERY,round(strain,8),round(sig,2),
                 round(conf,2),bd,nc,round(itasca.timestep(),12)])
    if sig>peak_s: peak_s=sig; peak_i=len(rows)-1
    if step%10==0:
        print("LOAD",step,"strain",round(strain,5),"sig_MPa",round(sig/1e6,3),
              "conf_MPa",round(conf/1e6,3),"bonded",bd)
    if strain>=TARGET_STRAIN: break

with open(CSV,"w") as f:
    f.write("cycle,axial_strain,axial_stress_Pa,conf_Pa,bonded,contacts,timestep_s\n")
    for r in rows: f.write(",".join(str(v) for v in r)+"\n")
peak=rows[peak_i] if rows else None
after=len(rows)-1-peak_i
summary={"case_id":"SCI-TX-%__TAG__","tool_task_id":"__TID__",
 "confining_target_Pa":TARGET,"confining_measured_Pa":s_conf,
 "confinement_ratio":round(s_conf/TARGET,4) if TARGET else None,
 "confinement_converged":converged,"consolidation_cycles":cons,
 "bonded_start":b0,"bonded_at_load":b_load,
 "bond_retention":round(b_load/b0,4) if b0 else None,
 "peak_stress_Pa":peak[2] if peak else None,
 "peak_strain":peak[1] if peak else None,
 "peak_is_last":(peak_i==len(rows)-1) if rows else None,
 "samples_after_peak":after,"samples":len(rows),
 "target_strain":TARGET_STRAIN}
with open(SUMMARY,"w") as f: json.dump(summary,f,indent=2,ensure_ascii=False)
print("SCIENCE_SUMMARY",json.dumps(summary,ensure_ascii=False))
'''
    code = (code.replace('__TARGET__', repr(target_pa))
                .replace('__BASE__', TX_BASE.replace('\\', '/'))
                .replace('__SAV__', SAV.replace('\\', '/'))
                .replace('__TAG__', str(int(target_pa / 1e6)))
                .replace('__TID__', 'pending'))
    # Long experiment: submit as an ASYNC task via execute_task, then poll.
    # execute_code has a 10s timeout and aborts long scripts (observed BUG).
    tag = str(int(target_pa / 1e6))
    script_path = os.path.join(TX_BASE, "work", "science_tx_%s.py" % tag)
    with open(script_path, "w", encoding="utf-8") as fh:
        fh.write(code)
    submitted = adapter.execute_task(script_path,
                                     "science triaxial %s Pa" % target_pa)
    tid = submitted.tool_task_id
    print("[SUBMITTED]", tid, submitted.task_state.value)
    if not tid or tid.startswith("unknown"):
        return submitted
    deadline = time.time() + 1800  # 30 min ceiling
    last = None
    while time.time() < deadline:
        resp = adapter.check_status(tid, wait_seconds=10)
        state = adapter._map_task_state(resp)
        if str(state.value) != str(last):
            print("[POLL]", state.value)
            last = state.value
        if state.value in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)
    from core.state_machine import ExecutionResult
    result = ExecutionResult(tool_task_id=tid, task_state=state,
                             error=resp.get("error") if state.value == "FAILED" else None)
    print("[RESULT]", result.task_state.value, tid)

    # Patch the tool_task_id into the summary (evidence binding).
    tag = str(int(target_pa / 1e6))
    summary_path = os.path.join(TX_BASE, "data", "tx_science_%s_summary.json" % tag)
    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)
        summary["tool_task_id"] = result.tool_task_id
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print("[BOUND] tool_task_id=%s -> %s" % (result.tool_task_id, summary_path))
    return result


if __name__ == "__main__":
    target = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0e6
    main(target)
