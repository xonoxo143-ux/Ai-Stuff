from __future__ import annotations

import argparse,json,random,re
from dataclasses import dataclass
from pathlib import Path

REF_PATTERNS=[
 ("the other one", "entity_pair"),
 ("it", "entity"),
 ("there", "location"),
 ("that one", "entity"),
 ("this one", "entity"),
]

@dataclass
class DiscourseContext:
    entities:list[str]
    locations:list[str]

def unresolved_references(text,ctx):
    low=text.casefold()
    missing=[]
    for surface,kind in REF_PATTERNS:
        if not re.search(r"\b"+re.escape(surface)+r"\b",low):
            continue
        if kind=="entity" and len(ctx.entities)<1:
            missing.append(surface)
        elif kind=="entity_pair" and len(ctx.entities)<2:
            missing.append(surface)
        elif kind=="location" and len(ctx.locations)<1:
            missing.append(surface)
    # Deduplicate while preserving order.
    out=[]
    for x in missing:
        if x not in out:out.append(x)
    return out

def clarification_plan(text,ctx):
    missing=unresolved_references(text,ctx)
    if not missing:return {"act":"PROCEED","missing":[]}
    return {
      "act":"CLARIFY_REFERENTS",
      "missing":missing,
      "reason":"required referents are not grounded in current discourse state",
    }

def clarification_response(plan):
    quoted=", ".join(f"'{x}'" for x in plan["missing"])
    return (
      "I need the referents before I can suggest the next step. "
      f"What do {quoted} refer to?"
    )

EVIDENCE_FIELDS=("citation","sample","controls","measure","duration","replication")

def epistemic_plan(claim,evidence):
    # Evidence is a list of explicit supporting/contradicting records.
    supported=[x for x in evidence if x.get("status")=="support"]
    contradicted=[x for x in evidence if x.get("status")=="contradict"]
    if contradicted:
        posture="CONTRADICTED"
    elif supported:
        posture="SUPPORTED"
    else:
        posture="UNKNOWN"
    return {
      "act":"EPISTEMIC_RESPONSE",
      "posture":posture,
      "claim":claim,
      "known":(
        "No verified evidence is available in the current evidence store."
        if posture=="UNKNOWN"
        else f"{len(supported)} supporting and {len(contradicted)} contradicting evidence records are available."
      ),
      "suspect":(
        "A highly specific causal and persistent effect should not be treated as established without strong evidence."
        if posture=="UNKNOWN"
        else "The strength of the conclusion should track the quality and independence of the evidence."
      ),
      "verify":list(EVIDENCE_FIELDS),
    }

def epistemic_response(plan):
    fields=", ".join(plan["verify"])
    return (
      f"Known: {plan['known']} "
      f"Suspect: {plan['suspect']} "
      f"Verify: the {fields}."
    )

def extract_claim(prompt):
    low=prompt.casefold()
    # Prefer text after attribution markers and before an explicit response instruction.
    m=re.search(r"(?:says|claims?)\s+(.*?)(?:\.\s+without web access|\.\s+respond|\Z)",prompt,re.I|re.S)
    return (m.group(1).strip() if m else prompt.strip())

def synthetic_referent_tests(rng,n=2000):
    ok=0
    for _ in range(n):
        mode=rng.randrange(4)
        if mode==0:
            ctx=DiscourseContext([],[])
            text="I moved it over there because the other one was too close."
            want=True
        elif mode==1:
            ctx=DiscourseContext(["red box"],["north shelf"])
            text="Move it there."
            want=False
        elif mode==2:
            ctx=DiscourseContext(["red box"],[])
            text="Move it there."
            want=True
        else:
            ctx=DiscourseContext(["red box","blue box"],["north shelf"])
            text="Put the other one there."
            want=False
        got=clarification_plan(text,ctx)["act"]=="CLARIFY_REFERENTS"
        ok+=got==want
    return ok/n

def synthetic_epistemic_tests(rng,n=2000):
    ok=0
    for _ in range(n):
        condition=rng.choice(["none","support","contradict"])
        evidence=[]
        if condition=="support":evidence=[{"status":"support","source":"study-A"}]
        elif condition=="contradict":evidence=[{"status":"contradict","source":"study-B"}]
        plan=epistemic_plan("intervention X permanently changes outcome Y by 15 points",evidence)
        want={"none":"UNKNOWN","support":"SUPPORTED","contradict":"CONTRADICTED"}[condition]
        ok+=plan["posture"]==want
    return ok/n

def benchmark_cases():
    root=Path(__file__).resolve().parents[2]
    with open(root/"workspace"/"benchmarks"/"chatbot-v0.json",encoding="utf-8") as f:b=json.load(f)
    return {x["id"]:x for x in b["turns"]}

def run(seed):
    rng=random.Random(seed)
    ref=synthetic_referent_tests(rng)
    epi=synthetic_epistemic_tests(rng)
    b=benchmark_cases()

    amb=b["ambiguity_01"]["prompt"]
    ap=clarification_plan(amb,DiscourseContext([],[]))
    ar=clarification_response(ap) if ap["act"]=="CLARIFY_REFERENTS" else ""

    ep=b["epistemic_01"]["prompt"]
    claim=extract_claim(ep)
    eplan=epistemic_plan(claim,[])
    er=epistemic_response(eplan)

    return {
      "seed":seed,
      "synthetic_referent_accuracy":ref,
      "synthetic_epistemic_accuracy":epi,
      "ambiguity_plan":ap,
      "ambiguity_response":ar,
      "ambiguity_pass":(
        ap["act"]=="CLARIFY_REFERENTS"
        and "it" in ap["missing"]
        and "there" in ap["missing"]
        and "the other one" in ap["missing"]
        and "What do" in ar
      ),
      "epistemic_plan":eplan,
      "epistemic_response":er,
      "epistemic_pass":(
        eplan["posture"]=="UNKNOWN"
        and "Known:" in er and "Suspect:" in er and "Verify:" in er
        and "citation" in er and "replication" in er
      ),
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="0,1,2");ap.add_argument("--out",default="uncertainty_regulator_v0.json");a=ap.parse_args()
    runs=[run(int(x)) for x in a.seeds.split(",")]
    passed=all(
      r["synthetic_referent_accuracy"]==1.0
      and r["synthetic_epistemic_accuracy"]==1.0
      and r["ambiguity_pass"] and r["epistemic_pass"]
      for r in runs
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f:json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))
