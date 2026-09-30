from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json

token = Path.home().joinpath(".kaggle/access_token").read_text().strip()

kernel_code = r"""import json
import pathlib
import subprocess
import torch

root = pathlib.Path("/kaggle/working")
repo = root / "Ai-Stuff"
if repo.exists():
    subprocess.run(["rm", "-rf", str(repo)], check=True)

subprocess.run([
    "git", "clone", "--depth", "1",
    "--branch", "experiment/v0-kaggle-t4",
    "https://github.com/xonoxo143-ux/Ai-Stuff.git",
    str(repo),
], check=True)

modeldir = repo / "agent-model"
for cmd in [
    ["python", "-m", "agent_language.fetch_v0_sources"],
    ["python", "-m", "agent_language.build_v0_corpus", "--train-mb", "16", "--valid-mb", "2"],
    ["python", "-m", "agent_language.preflight_v0"],
]:
    run = subprocess.run(cmd, cwd=modeldir, text=True, capture_output=True)
    print(run.stdout)
    if run.stderr:
        print(run.stderr)
    if run.returncode:
        raise SystemExit(run.returncode)

print(json.dumps({
    "cuda_available": torch.cuda.is_available(),
    "cuda_count": torch.cuda.device_count(),
    "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
}, sort_keys=True))
if torch.cuda.device_count() < 2:
    raise SystemExit("This experiment requires two visible CUDA devices.")

runs = root / "v0-phase1-ab-rung512"
runs.mkdir(parents=True, exist_ok=True)
common = [
    "python", "-m", "agent_language.train_v0",
    "--config", "configs/v0_first_run.json",
    "--max-step", "512", "--precision", "fp32",
]
specs = {
    "hybrid": common + [
        "--model", "hybrid", "--run-dir", str(runs / "hybrid"),
        "--device", "cuda:0", "--execution", "vectorized",
    ],
    "transformer": common + [
        "--model", "transformer", "--run-dir", str(runs / "transformer"),
        "--device", "cuda:1",
    ],
}
jobs = {}
handles = {}
for name, cmd in specs.items():
    handle = (runs / f"{name}.log").open("w")
    handles[name] = handle
    jobs[name] = subprocess.Popen(
        cmd, cwd=modeldir, stdout=handle, stderr=subprocess.STDOUT, text=True
    )

returncodes = {name: proc.wait() for name, proc in jobs.items()}
for handle in handles.values():
    handle.close()

summary = {
    "experiment_id": "v0-phase1-ab-rung512",
    "git_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip(),
    "returncodes": returncodes,
}
for name in specs:
    result_path = runs / name / f"{name}.json"
    if result_path.exists():
        summary[name] = json.loads(result_path.read_text())

summary_path = runs / "summary.json"
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
if any(returncodes.values()):
    raise SystemExit("One or more A/B lanes failed.")
"""

payload = {
    "slug": "selfroot/v0-phase1-ab-rung512",
    "newTitle": "V0 Phase1 A-B Rung 512",
    "text": kernel_code,
    "language": "python",
    "kernelType": "script",
    "isPrivate": True,
    "enableInternet": True,
    "enableGpu": True,
    "machineShape": "NvidiaTeslaT4",
}
req = Request(
    "https://www.kaggle.com/api/v1/kernels/push",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": "agent-v0-phase1-ab",
    },
    method="POST",
)
try:
    with urlopen(req, timeout=30) as response:
        print(json.dumps(json.load(response), sort_keys=True))
except HTTPError as error:
    print("HTTP", error.code)
    print(error.read().decode()[:4000])
    raise
