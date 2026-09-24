from __future__ import annotations

import math
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np
import pretty_midi
import soundfile as sf
from scipy.signal import butter, sosfiltfilt, fftconvolve

SR = 44100
OUT_DUR_PAD = 5.0

@dataclass
class Region:
    sample: str
    lokey: int = 0
    hikey: int = 127
    pitch_keycenter: int = 60
    lovel: int = 0
    hivel: int = 127
    volume: float = 0.0
    tune: float = 0.0
    seq_length: int = 1
    seq_position: int = 1
    ampeg_attack: float = 0.001
    ampeg_release: float = 0.5

@dataclass
class InstrumentDef:
    name: str
    sfz_path: Path
    default_path: str = ''
    regions: list[Region] = field(default_factory=list)

_num_re = re.compile(r'^-?\d+(?:\.\d+)?$')

def parse_value(v: str):
    v = v.strip().strip('"')
    if _num_re.match(v):
        return float(v) if '.' in v else int(v)
    return v

def parse_sfz(path: Path) -> InstrumentDef:
    text = path.read_text(errors='ignore').replace('\r', '\n')
    text = re.sub(r'//.*', '', text)
    tags = re.split(r'(<(?:control|global|group|region)>)', text, flags=re.I)
    control = {}
    global_ops = {}
    group_ops = {}
    regions = []

    def parse_ops(s: str):
        ops = {}
        for line in s.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('sample=') or line.startswith('default_path='):
                k, v = line.split('=', 1)
                ops[k.strip().lower()] = v.strip()
                continue
            for m in re.finditer(r'([A-Za-z0-9_]+)=([^\s]+)', line):
                ops[m.group(1).lower()] = parse_value(m.group(2))
        return ops

    i = 1
    while i < len(tags):
        tag = tags[i].lower()
        body = tags[i+1] if i+1 < len(tags) else ''
        ops = parse_ops(body)
        if tag == '<control>':
            control.update(ops)
        elif tag == '<global>':
            global_ops.update(ops)
        elif tag == '<group>':
            group_ops = dict(ops)
        elif tag == '<region>':
            merged = dict(global_ops)
            merged.update(group_ops)
            merged.update(ops)
            if 'sample' in merged:
                regions.append(Region(
                    sample=str(merged['sample']),
                    lokey=int(merged.get('lokey', 0)),
                    hikey=int(merged.get('hikey', 127)),
                    pitch_keycenter=int(merged.get('pitch_keycenter', 60)),
                    lovel=int(merged.get('lovel', 0)),
                    hivel=int(merged.get('hivel', 127)),
                    volume=float(merged.get('volume', 0.0)),
                    tune=float(merged.get('tune', 0.0)),
                    seq_length=int(merged.get('seq_length', 1)),
                    seq_position=int(merged.get('seq_position', 1)),
                    ampeg_attack=float(merged.get('ampeg_attack', global_ops.get('ampeg_attack', 0.001))),
                    ampeg_release=float(merged.get('ampeg_release', global_ops.get('ampeg_release', 0.5))),
                ))
        i += 2
    return InstrumentDef(path.stem, path, str(control.get('default_path', '')), regions)

def ci_resolve(root: Path, rel: str) -> Path:
    rel = rel.replace('\\', '/').strip('/')
    cur = root
    for part in [p for p in rel.split('/') if p and p != '.']:
        direct = cur / part
        if direct.exists():
            cur = direct
            continue
        if not cur.exists():
            return direct
        found = None
        pl = part.lower()
        for child in cur.iterdir():
            if child.name.lower() == pl:
                found = child
                break
        cur = found if found is not None else direct
    return cur

class SampleBank:
    def __init__(self, vsco_root: Path):
        self.root = vsco_root
        self.defs: dict[str, InstrumentDef] = {}
        self.audio_cache: dict[Path, tuple[np.ndarray, int]] = {}
        self.rr_counter = defaultdict(int)

    def load_def(self, sfz_name: str):
        if sfz_name not in self.defs:
            p = self.root / sfz_name
            if not p.exists():
                raise FileNotFoundError(p)
            self.defs[sfz_name] = parse_sfz(p)
        return self.defs[sfz_name]

    def choose_region(self, sfz_name: str, pitch: int, vel: int) -> Region:
        idef = self.load_def(sfz_name)
        matches = [r for r in idef.regions if r.lokey <= pitch <= r.hikey and r.lovel <= vel <= r.hivel]
        if not matches:
            def dist(r):
                kd = 0 if r.lokey <= pitch <= r.hikey else min(abs(pitch-r.lokey), abs(pitch-r.hikey))
                vd = 0 if r.lovel <= vel <= r.hivel else min(abs(vel-r.lovel), abs(vel-r.hivel))
                return kd*10 + vd
            matches = sorted(idef.regions, key=dist)[:1]
        if len(matches) > 1:
            key = (sfz_name, pitch, vel)
            idx = self.rr_counter[key]
            self.rr_counter[key] += 1
            seqs = sorted(matches, key=lambda r: (r.seq_position, r.sample))
            return seqs[idx % len(seqs)]
        return matches[0]

    def load_sample(self, sfz_name: str, region: Region) -> tuple[np.ndarray, int]:
        idef = self.load_def(sfz_name)
        base = ci_resolve(self.root, idef.default_path)
        p = ci_resolve(base, region.sample)
        if p not in self.audio_cache:
            if not p.exists():
                raise FileNotFoundError(f"sample not found: {p} (from {sfz_name})")
            audio, sr = sf.read(p, always_2d=True, dtype='float32')
            if audio.shape[1] > 2:
                audio = audio[:, :2]
            self.audio_cache[p] = (audio, sr)
        return self.audio_cache[p]

TRACK_PAN = {
    'piano': -0.10, 'strings_high': 0.30, 'strings_low': -0.20, 'cello': -0.10,
    'tremolo_strings': 0.15, 'Divisi Violins': 0.45, 'Inner Strings': -0.35,
    'Contrabass Foundation': -0.08, 'Horn Veil': -0.28, 'Trumpet I - Lead': 0.12,
    'Trumpet II - Harmony': -0.04, 'Trumpet III - Foundation': 0.28,
    'Sparse Timpani': -0.06, 'Opening String Halo': 0.25,
    'Opening Cello Answer': -0.18, 'High Violin Lift': 0.42, 'Horn Reply': -0.36,
}

TRACK_GAIN = defaultdict(lambda: 1.0, {
    'piano': 0.68, 'strings_high': 0.72, 'strings_low': 0.72, 'cello': 0.68,
    'tremolo_strings': 0.48, 'Divisi Violins': 0.62, 'Inner Strings': 0.62,
    'Contrabass Foundation': 0.58, 'Horn Veil': 0.58, 'Trumpet I - Lead': 0.54,
    'Trumpet II - Harmony': 0.43, 'Trumpet III - Foundation': 0.38,
    'Sparse Timpani': 0.48, 'Opening String Halo': 0.42,
    'Opening Cello Answer': 0.56, 'High Violin Lift': 0.56, 'Horn Reply': 0.48,
})

SUSTAIN_TRACKS = {
    'strings_high','strings_low','cello','tremolo_strings','Divisi Violins','Inner Strings',
    'Contrabass Foundation','Horn Veil','Trumpet I - Lead','Trumpet II - Harmony',
    'Trumpet III - Foundation','Opening String Halo','Opening Cello Answer','High Violin Lift','Horn Reply'
}

def sfz_for(track: str, pitch: int) -> str | None:
    if track == 'piano':
        return 'UprightPiano.sfz'
    if track in {'strings_high','Divisi Violins','High Violin Lift'}:
        return 'ViolinEnsSusVib.sfz' if track == 'strings_high' else 'SViolinVib.sfz'
    if track in {'Inner Strings','Opening String Halo'}:
        return 'ViolaEnsSusVib.sfz' if pitch >= 55 else 'CelloEnsSusVib.sfz'
    if track in {'cello','Opening Cello Answer'}:
        return 'CelloEnsSusVib.sfz'
    if track == 'strings_low':
        return 'CelloEnsSusVib.sfz' if pitch >= 43 else 'ContrabassSusVB.sfz'
    if track == 'tremolo_strings':
        return 'ViolinEnsTrem.sfz' if pitch >= 56 else 'CelloEnsTrem.sfz'
    if track == 'Contrabass Foundation':
        return 'ContrabassSusVB.sfz'
    if track in {'Horn Veil','Horn Reply'}:
        return 'FHornSus.sfz'
    if track == 'Trumpet I - Lead':
        return 'TrumpetSusVib.sfz'
    if track in {'Trumpet II - Harmony','Trumpet III - Foundation'}:
        return 'TrumpetSus.sfz'
    if track == 'Sparse Timpani':
        return 'Timpani.sfz'
    return None

def pan_stereo(x: np.ndarray, pan: float) -> np.ndarray:
    pan = float(np.clip(pan, -1, 1))
    l = math.cos((pan+1) * math.pi/4)
    r = math.sin((pan+1) * math.pi/4)
    mono = x if x.ndim == 1 else x.mean(axis=1)
    return np.column_stack([mono*l, mono*r]).astype(np.float32)

def pitch_resample(audio: np.ndarray, src_sr: int, semitones: float, out_sr: int = SR) -> np.ndarray:
    ratio = 2.0 ** (semitones / 12.0)
    step = src_sr * ratio / out_sr
    n_out = max(1, int(len(audio) / step))
    pos = np.arange(n_out, dtype=np.float64) * step
    xp = np.arange(len(audio), dtype=np.float64)
    chs = [np.interp(pos, xp, audio[:, c], left=0.0, right=0.0) for c in range(audio.shape[1])]
    return np.stack(chs, axis=1).astype(np.float32)

def extend_or_trim(x: np.ndarray, target_n: int, sustain: bool) -> np.ndarray:
    if target_n <= 0:
        return np.zeros((0, x.shape[1]), np.float32)
    if len(x) >= target_n:
        return x[:target_n].copy()
    if not sustain or len(x) < int(0.3*SR):
        y = np.zeros((target_n, x.shape[1]), np.float32)
        y[:len(x)] = x
        return y
    a = int(len(x)*0.32); b = int(len(x)*0.72)
    if b-a < int(0.12*SR):
        a = int(len(x)*0.2); b = int(len(x)*0.8)
    loop = x[a:b]
    xf = min(int(0.04*SR), max(64, len(loop)//8))
    y = x.copy()
    while len(y) < target_n:
        seg = loop.copy()
        if len(y) > 0 and xf > 0 and len(seg) > xf:
            fade = np.linspace(0,1,xf, dtype=np.float32)[:,None]
            y[-xf:] = y[-xf:]*(1-fade) + seg[:xf]*fade
            y = np.concatenate([y, seg[xf:]], axis=0)
        else:
            y = np.concatenate([y, seg], axis=0)
    return y[:target_n]

def note_audio(bank: SampleBank, sfz_name: str, pitch: int, vel: int, dur: float, sustain: bool, track: str) -> np.ndarray:
    reg = bank.choose_region(sfz_name, pitch, vel)
    src, src_sr = bank.load_sample(sfz_name, reg)
    semi = (pitch - reg.pitch_keycenter) + reg.tune/100.0
    x = pitch_resample(src, src_sr, semi)
    amp = 10**(reg.volume/20.0) * (0.22 + 0.78*(vel/127.0)**1.35)
    x *= amp * TRACK_GAIN[track]
    release = min(max(reg.ampeg_release, 0.08), 1.2)
    target_n = int((dur + release) * SR)
    x = extend_or_trim(x, target_n, sustain)
    attack = reg.ampeg_attack
    if track in SUSTAIN_TRACKS:
        attack = max(attack, 0.035 if 'Trumpet' in track else 0.055)
    elif track == 'piano':
        attack = 0.004
    elif track == 'Sparse Timpani':
        attack = 0.002
    na = min(len(x), int(attack*SR))
    if na > 1:
        x[:na] *= np.linspace(0,1,na, dtype=np.float32)[:,None]
    nr = min(len(x), int(release*SR))
    if nr > 1:
        x[-nr:] *= np.linspace(1,0,nr, dtype=np.float32)[:,None]
    return pan_stereo(x, TRACK_PAN.get(track,0.0))

def add_signal(mix, sig, start_s):
    s = int(start_s*SR)
    e = min(len(mix), s+len(sig))
    if e > s:
        mix[s:e] += sig[:e-s]

def synth_pad_note(pitch, start, dur, vel, total_n, pan=0.0):
    n = int((dur+1.8)*SR)
    tt = np.arange(n)/SR
    f = 440*2**((pitch-69)/12)
    y = np.zeros(n)
    for h,a in [(1,1.0),(2,0.23),(3,0.12),(4,0.06)]:
        y += a*np.sin(2*np.pi*f*h*tt + 0.13*h)
    env = np.ones(n)
    a = min(n, int(.7*SR)); r = min(n, int(1.5*SR))
    env[:a] *= np.linspace(0,1,a)
    env[-r:] *= np.linspace(1,0,r)
    y *= env * (0.015 + vel/127*0.018)
    return pan_stereo(y.astype(np.float32), pan)

def noise_swell(start, dur, amp=0.035):
    n = int(dur*SR)
    rng = np.random.default_rng(int(start*1000)+17)
    y = rng.normal(0,1,n).astype(np.float32)
    sos = butter(3, [350/(SR/2), 9000/(SR/2)], btype='bandpass', output='sos')
    y = sosfiltfilt(sos, y)
    env = np.sin(np.linspace(0, math.pi/2, n))**2
    y *= env*amp
    return pan_stereo(y,0)

def hall_ir(sr=SR, seconds=3.2):
    n = int(seconds*sr)
    rng = np.random.default_rng(20260924)
    t = np.arange(n)/sr
    ir_l = np.zeros(n); ir_r = np.zeros(n)
    for delay, gain, side in [(.029,.34,-1),(.043,.29,1),(.061,.22,-1),(.083,.18,1),(.117,.14,-1),(.151,.12,1)]:
        i=int(delay*sr)
        (ir_l if side<0 else ir_r)[i] += gain
        (ir_r if side<0 else ir_l)[i] += gain*.55
    tail = rng.normal(0,1,n) * np.exp(-t/0.82)
    sos = butter(2, 6500/(sr/2), btype='lowpass', output='sos')
    tail = sosfiltfilt(sos, tail)
    tail[:int(.09*sr)] *= np.linspace(0,1,int(.09*sr))
    ir_l += tail*0.018
    ir_r += np.roll(tail, 137)*0.018
    return np.column_stack([ir_l,ir_r]).astype(np.float32)

def main():
    midi_path = Path(os.environ.get('MIDI_PATH','music/vsco_pass05/pass05.mid'))
    vsco_root = Path(os.environ.get('VSCO_ROOT','vsco'))
    out_dir = Path(os.environ.get('OUT_DIR','rendered'))
    out_dir.mkdir(parents=True, exist_ok=True)

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    duration = pm.get_end_time()+OUT_DUR_PAD
    mix = np.zeros((int(duration*SR),2), np.float32)
    reverb_send = np.zeros_like(mix)
    bank = SampleBank(vsco_root)
    used = defaultdict(int)
    skipped = []

    for ins in pm.instruments:
        track = ins.name
        if track in {'Choir Arrival','Warm Atmospheric Bed'}:
            for n in ins.notes:
                sig = synth_pad_note(n.pitch,n.start,n.end-n.start,n.velocity,len(mix), pan=-.12 if track.startswith('Choir') else .08)
                add_signal(mix,sig,n.start)
                add_signal(reverb_send,sig*.65,n.start)
            continue
        if track in {'Transition Air','Final Transition Air'}:
            for n in ins.notes:
                sig=noise_swell(n.start,max(.7,n.end-n.start),.028)
                add_signal(mix,sig,n.start)
                add_signal(reverb_send,sig*.9,n.start)
            continue
        if track == 'Low Taiko Impacts':
            for n in ins.notes:
                p=max(36,min(43,n.pitch))
                sig=note_audio(bank,'Timpani.sfz',p,max(68,n.velocity),max(.5,n.end-n.start),False,'Sparse Timpani')*.85
                add_signal(mix,sig,n.start)
                add_signal(reverb_send,sig*.7,n.start)
            continue

        for n in ins.notes:
            sfz_name = sfz_for(track,n.pitch)
            if sfz_name is None:
                skipped.append((track,n.pitch))
                continue
            try:
                sig = note_audio(bank,sfz_name,n.pitch,n.velocity,n.end-n.start,track in SUSTAIN_TRACKS,track)
            except Exception as e:
                raise RuntimeError(f'Failed {track} note {n.pitch} with {sfz_name}: {e}') from e
            add_signal(mix,sig,n.start)
            send = 0.34
            if 'Trumpet' in track or 'Horn' in track: send=.42
            elif 'Timpani' in track: send=.29
            elif track=='piano': send=.25
            add_signal(reverb_send,sig*send,n.start)
            used[sfz_name]+=1

    ir = hall_ir()
    wet_l = fftconvolve(reverb_send[:,0],ir[:,0],mode='full')[:len(mix)]
    wet_r = fftconvolve(reverb_send[:,1],ir[:,1],mode='full')[:len(mix)]
    mix = mix + np.column_stack([wet_l,wet_r]).astype(np.float32)*0.52

    hp=butter(2,28/(SR/2),btype='highpass',output='sos')
    lp=butter(2,16500/(SR/2),btype='lowpass',output='sos')
    mix=sosfiltfilt(hp,mix,axis=0)
    mix=sosfiltfilt(lp,mix,axis=0)
    peak=np.max(np.abs(mix))+1e-9
    mix=mix/(peak/0.82) if peak>0.82 else mix
    mix=np.tanh(mix*1.06)/np.tanh(1.06)
    peak=np.max(np.abs(mix))+1e-9
    mix*= (10**(-1.0/20))/peak

    wav=out_dir/'pass05_vsco.wav'
    sf.write(wav,mix,SR,subtype='PCM_16')

    mono=mix.mean(axis=1)
    def rmsdb(a,b):
        x=mono[int(a*SR):min(len(mono),int(b*SR))]
        return 20*np.log10(np.sqrt(np.mean(x*x)+1e-12)+1e-12)
    report = [
        'VSCO Pass 05 render',
        f'duration_sec={len(mix)/SR:.2f}',
        f'peak={np.max(np.abs(mix)):.5f}',
        'used_sfz='+repr(dict(sorted(used.items()))),
        f'rms_0_20={rmsdb(0,20):.2f}',
        f'rms_20_45={rmsdb(20,45):.2f}',
        f'rms_45_60={rmsdb(45,60):.2f}',
        f'rms_60_78={rmsdb(60,78):.2f}',
        f'rms_78_end={rmsdb(78,len(mix)/SR):.2f}',
        'skipped='+repr(skipped[:20]),
    ]
    (out_dir/'render_report.txt').write_text('\n'.join(report)+'\n')
    print('\n'.join(report))

if __name__=='__main__':
    main()
