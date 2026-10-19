"""Centre-scoped cockpit facts, abstaining when camera or source is untrusted."""
from __future__ import annotations
from typing import Any
from app.models import ComplianceCase

OPEN={"open","under_review","virtual_verification"}

def natural(value:object)->int|None:
    return value if type(value) is int and 0<=value<=100000 else None

def snapshot(*,centre_id:str, camera_state:str, cases:list[ComplianceCase],
             history:list[dict[str,Any]], engine_states:dict[str,str])->dict[str,Any]:
    # Callers must scope before use; enforce again at the trust boundary.
    cases=[c for c in cases if c.centre_id==centre_id]
    history=[h for h in history if h.get("centre_id")==centre_id]
    def latest(kind:str):
        values=[h for h in history if h.get("analysis_type")==kind]
        return max(values,key=lambda x:str(x.get("created_at") or "")) if values else None
    def pair(key:str,case_type:str,case_keys:tuple[str,str],history_keys:tuple[tuple[str,...],tuple[str,...]]):
        result={"status":engine_states[key],"reported":None,"observed":None,
                "source":"unavailable","source_id":None,"simulated":False}
        if camera_state!="verified" or result["status"] not in ("verified","review"):
            return result
        ordered=sorted((c for c in cases if c.case_type==case_type and c.status.value in OPEN|{"confirmed"}),
                       key=lambda c:str(c.created_at or ""),reverse=True)
        for case in ordered:
            if case.camera_trust is not None and not case.camera_trust.trusted:continue
            data=case.details if key=="infrastructure" else {
                "reported_attendance":case.reported_attendance,"visual_occupancy":case.visual_occupancy}
            a,b=natural(data.get(case_keys[0])),natural(data.get(case_keys[1]))
            if a is not None and b is not None:
                result.update(reported=a,observed=b,source="case",source_id=case.case_id,
                              simulated=bool(case.details.get("simulated")))
                return result
        row=latest("attendance" if key=="attendance" else "infrastructure")
        if row and row.get("outcome")!="blocked":
            data=row.get("details") or {}
            if isinstance(data,dict):
                vals=[]
                for aliases in history_keys:
                    vals.append(next((natural(data.get(k)) for k in aliases
                                      if natural(data.get(k)) is not None),None))
                if all(x is not None for x in vals):
                    result.update(reported=vals[0],observed=vals[1],source="analysis",
                                  source_id=row.get("analysis_id"),
                                  simulated=bool(data.get("simulated")))
        return result
    attendance=pair("attendance","attendance_discrepancy",
                    ("reported_attendance","visual_occupancy"),
                    (("reported_attendance","reported"),("estimated_occupancy","observed")))
    equipment=pair("infrastructure","infrastructure_compliance",
                   ("reported_quantity","observed_quantity"),
                   (("reported_quantity","reported"),("observed_quantity","observed")))
    activity={"status":engine_states["practical_activity"],"active_work_cells":None,
              "peak_workers":None,"source":"unavailable","source_id":None,"simulated":False}
    row=latest("practical_work")
    if camera_state=="verified" and activity["status"] in ("verified","review") and row and row.get("outcome")!="blocked":
        data=row.get("details") or {}
        if isinstance(data,dict):
            cells=natural(data.get("active_work_cells"))
            if cells is not None:
                activity.update(active_work_cells=cells,peak_workers=natural(data.get("peak_stable_workers")),
                                source="analysis",source_id=row.get("analysis_id"),
                                simulated=bool(data.get("simulated")))
    return {
        "attendance":attendance,"infrastructure":equipment,"practical_activity":activity,
        "camera":{"status":camera_state},
        "evidence":{"retained_count":sum(len(c.evidence) for c in cases),
                    "cases_requiring_review":sum(c.status.value in OPEN for c in cases)},
    }
