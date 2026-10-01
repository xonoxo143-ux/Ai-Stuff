from __future__ import annotations

"""Naturalistic Evidence Relational Synthesis Gate v0.

This gate deliberately does NOT ask a language model to invent an analogy.
It feeds source-tagged retrieved evidence records into the already-tested
relational synthesis operation and checks whether support, limits, ambiguity,
and causal deletion remain evidence-controlled.

Naturalistic here means human-readable evidence records with distractors and
source provenance rather than opaque synthetic node names. The relation
ontology remains typed so this is a bridge gate, not open-web extraction.
"""

from dataclasses import dataclass
import argparse, json, random

from relational_synthesis_gate_v1 import Domain, Edge, synthesize

@dataclass(frozen=True)
class Evidence:
    source: str
    subject: str
    relation: str
    object: str
    text: str

def domain(rows):
    nodes=sorted({r.subject for r in rows}|{r.object for r in rows})
    return Domain(nodes,{Edge(r.relation,r.subject,r.object) for r in rows},{n:n for n in nodes})

def fixtures():
    # Human-readable domains with matched causal organization but different nouns.
    # No factual claim about the real world is implied; these are controlled
    # natural-language evidence records for testing the evidence->reasoning bridge.
    a=[
      Evidence("A1","thermostat","observes","temperature","The thermostat observes room temperature."),
      Evidence("A2","thermostat","controls","heater","The thermostat controls the heater."),
      Evidence("A3","heater","changes","temperature","The heater changes room temperature."),
      Evidence("A4","temperature","constrains","comfort","Temperature constrains comfort."),
    ]
    b=[
      Evidence("B1","controller","observes","queue_depth","The controller observes queue depth."),
      Evidence("B2","controller","controls","worker_pool","The controller controls the worker pool."),
      Evidence("B3","worker_pool","changes","queue_depth","The worker pool changes queue depth."),
      Evidence("B4","queue_depth","constrains","latency","Queue depth constrains latency."),
    ]
    distract=[
      Evidence("D1","blue_label","resembles","controller","A blue label resembles the controller."),
      Evidence("D2","heater","near","window","The heater is near a window."),
    ]
    return a,b,distract

def run(seed):
    rng=random.Random(seed)
    a,b,d=fixtures()
    base=domain(a); target=domain(b)
    clean=synthesize(base,target)

    # Relation-incompatible surface distractors must not strengthen the alignment.
    noisy=synthesize(base,domain(b+d))

    # Delete one supporting record with model/reasoner fixed.
    deleted=b[:]
    removed=deleted.pop(rng.randrange(len(deleted)))
    after_delete=synthesize(base,domain(deleted))

    # Mutate a required relation while preserving readable entities.
    mutated=b[:]
    j=rng.randrange(len(mutated)); old=mutated[j]
    mutated[j]=Evidence(old.source,old.subject,"opposes",old.object,
                        f"{old.subject} opposes {old.object}.")
    after_mutation=synthesize(base,domain(mutated))

    return {
      "seed":seed,
      "clean_classification":clean["classification"],
      "clean_useful":clean["useful_connection"],
      "clean_ambiguity":clean["ambiguous_alignment"],
      "noisy_classification":noisy["classification"],
      "deleted_source":removed.source,
      "deletion_classification":after_delete["classification"],
      "mutation_source":old.source,
      "mutation_classification":after_mutation["classification"],
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",default="0,1,2")
    ap.add_argument("--out",default="naturalistic_relational_synthesis_v0.json")
    a=ap.parse_args()
    runs=[run(int(s)) for s in a.seeds.split(",")]
    passed=all(
      r["clean_classification"]=="STRONG"
      and r["clean_useful"]
      and r["noisy_classification"]=="STRONG"
      and r["deletion_classification"] in ("PARTIAL","WEAK")
      and r["mutation_classification"] in ("PARTIAL","WEAK")
      for r in runs
    )
    out={"passed":passed,"runs":runs}
    with open(a.out,"w") as f: json.dump(out,f,indent=2)
    print(json.dumps(out,indent=2))

if __name__=="__main__": main()
