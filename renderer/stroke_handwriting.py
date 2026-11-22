#!/usr/bin/env python3
"""Stroke-based handwriting synthesis.

This renderer deliberately does not use an installed font. It composes words from
pen trajectories, then applies writer-level and sample-level variation so unseen
text is generated rather than pasted from glyph images.
"""
from __future__ import annotations
import json, math, random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFilter

Point = Tuple[float, float]
Stroke = List[Point]

# Compact single-line skeletons. Coordinates are normalized to a 1x1 em box.
# These are trajectories, not font outlines: each item is a pen movement.
S = {
'a': [[(0.05,.62),(.18,.35),(.42,.35),(.55,.62),(.42,.82),(.17,.82),(.05,.62)],[(.55,.35),(.55,.98)]],
'b': [[(.18,.02),(.18,.98)],[(.18,.42),(.42,.34),(.60,.50),(.60,.78),(.42,.91),(.18,.82)]],
'c': [[(.60,.40),(.48,.33),(.20,.36),(.06,.58),(.16,.82),(.43,.88),(.60,.77)]],
'd': [[(.58,.02),(.58,.98)],[(.58,.42),(.40,.34),(.15,.38),(.06,.60),(.16,.83),(.40,.90),(.58,.80)]],
'e': [[(.06,.62),(.58,.60),(.47,.37),(.20,.37),(.06,.58),(.17,.83),(.45,.88),(.60,.76)]],
'f': [[(.58,.20),(.48,.06),(.28,.10),(.22,.98)],[(.05,.38),(.58,.38)]],
'g': [[(.56,.39),(.42,.34),(.17,.38),(.07,.61),(.18,.82),(.43,.84),(.56,.70)],[(.56,.39),(.56,1.10),(.40,1.22),(.16,1.18),(.07,1.05)]],
'h': [[(.16,.02),(.16,.98)],[(.16,.56),(.35,.35),(.57,.39),(.57,.98)]],
'i': [[(.20,.37),(.20,.98)],[(.20,.14),(.20,.14)]],
'j': [[(.38,.37),(.38,1.08),(.26,1.20),(.08,1.13)],[(.38,.14),(.38,.14)]],
'k': [[(.16,.02),(.16,.98)],[(.58,.36),(.16,.66),(.58,.98)]],
'l': [[(.28,.02),(.18,.18),(.18,.98)],[(.18,.98),(.43,.98)]],
'm': [[(.05,.98),(.05,.38),(.21,.34),(.34,.54),(.34,.98)],[(.34,.54),(.49,.34),(.62,.40),(.62,.98)]],
'n': [[(.06,.98),(.06,.38),(.24,.34),(.48,.42),(.48,.98)]],
'o': [[(.18,.36),(.43,.34),(.59,.53),(.56,.78),(.38,.90),(.13,.83),(.06,.60),(.18,.36)]],
'p': [[(.12,.34),(.12,1.20)],[(.12,.45),(.32,.34),(.56,.42),(.58,.67),(.43,.86),(.12,.78)]],
'q': [[(.55,.40),(.42,.34),(.17,.38),(.07,.61),(.18,.82),(.43,.84),(.56,.70)],[(.43,.75),(.68,1.08)]],
'r': [[(.08,.98),(.08,.39),(.25,.34),(.48,.41)],[(.25,.54),(.48,.37),(.60,.44)]],
's': [[(.56,.40),(.40,.32),(.14,.38),(.07,.56),(.23,.68),(.48,.70),(.57,.82),(.40,.91),(.14,.86),(.05,.76)]],
't': [[(.28,.15),(.22,.94),(.34,1.02),(.52,.94)],[(.08,.39),(.54,.39)]],
'u': [[(.08,.38),(.08,.78),(.22,.88),(.42,.80),(.54,.60)],[(.54,.38),(.54,.98)]],
'v': [[(.06,.38),(.26,.98),(.50,.38)]],
'w': [[(.04,.38),(.18,.98),(.32,.57),(.46,.98),(.62,.38)]],
'x': [[(.06,.38),(.55,.98)],[(.55,.38),(.06,.98)]],
'y': [[(.06,.38),(.24,.86),(.45,.38)],[(.45,.38),(.42,1.08),(.27,1.18),(.08,1.12)]],
'z': [[(.06,.38),(.57,.38),(.08,.98),(.58,.98)]],
}
# Capitals are intentionally a separate scale/gesture set derived from strokes,
# not rendered with a font. A profile can replace any capital with real samples.
CAPITAL_SCALE = 1.18
DIGITS = {
'0': [[(.18,.18),(.42,.08),(.58,.28),(.55,.78),(.35,1.00),(.12,.80),(.08,.30),(.18,.18)]],
'1': [[(.18,.30),(.38,.08),(.38,1.00)],[(.18,1.00),(.58,1.00)]],
'2': [[(.10,.27),(.25,.08),(.50,.12),(.58,.34),(.10,1.00),(.60,1.00)]],
'3': [[(.10,.14),(.42,.08),(.58,.24),(.38,.50),(.56,.60),(.58,.82),(.40,1.00),(.10,.92)]],
'4': [[(.48,.06),(.08,.66),(.62,.66)],[(.48,.06),(.48,1.00)]],
'5': [[(.56,.10),(.16,.10),(.10,.52),(.38,.46),(.58,.61),(.48,.92),(.16,.98),(.06,.86)]],
'6': [[(.52,.12),(.28,.08),(.10,.32),(.08,.78),(.26,.98),(.52,.86),(.56,.60),(.34,.48),(.10,.58)]],
'7': [[(.08,.12),(.58,.12),(.26,1.00)]],
'8': [[(.30,.50),(.12,.34),(.16,.12),(.42,.08),(.56,.26),(.48,.48),(.22,.54),(.08,.72),(.16,.94),(.42,.98),(.56,.82),(.50,.60),(.30,.50)]],
'9': [[(.52,.58),(.32,.68),(.10,.52),(.12,.20),(.34,.08),(.56,.24),(.56,.72),(.38,1.00),(.16,.94)]],
}

@dataclass
class WriterProfile:
    name: str = "default-stroke-writer"
    scale: float = 1.0
    slant: float = 0.10
    stroke_width: float = 3.0
    baseline_jitter: float = 2.2
    size_jitter: float = 0.055
    spacing: float = 0.16
    pressure: float = 0.22
    connect: float = 0.82
    ink: Tuple[int,int,int] = (32, 45, 63)
    strokes: Dict[str, List[Stroke]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "WriterProfile":
        data = json.loads(Path(path).read_text())
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if 'ink' in fields: fields['ink'] = tuple(fields['ink'])
        if 'strokes' in fields:
            fields['strokes'] = {
                label: [[tuple(point) for point in stroke] for stroke in strokes]
                for label, strokes in fields['strokes'].items()
            }
        return cls(**fields)

    def save(self, path: str | Path) -> None:
        data = {k:v for k,v in self.__dict__.items() if k != 'strokes'}
        data['ink'] = list(self.ink)
        data['strokes'] = self.strokes
        Path(path).write_text(json.dumps(data, indent=2))

    def glyph(self, ch: str) -> List[Stroke]:
        if ch in self.strokes: return self.strokes[ch]
        if ch.lower() in self.strokes: return self.strokes[ch.lower()]
        if ch in DIGITS: return DIGITS[ch]
        base = S.get(ch.lower(), S['o'])
        factor = CAPITAL_SCALE if ch.isupper() else 1.0
        return [[(x, (y-.5)*factor+.5) for x,y in stroke] for stroke in base]

class HandwritingRenderer:
    def __init__(self, profile: WriterProfile | None = None, seed: int = 7):
        self.profile = profile or WriterProfile()
        self.rng = random.Random(seed)

    def _transform(self, p: Point, x0: float, y0: float, em: float, local_skew: float) -> Point:
        x,y = p
        # slant is applied around each glyph's baseline, preserving joins.
        return (x0 + x*em + (y-.75)*em*local_skew, y0 + y*em)

    def _resample(self, pts: Stroke, count: int = 18) -> Stroke:
        if len(pts) < 2: return pts
        out=[]
        lengths=[0.0]
        for a,b in zip(pts,pts[1:]): lengths.append(lengths[-1]+math.hypot(b[0]-a[0],b[1]-a[1]))
        total=lengths[-1]
        for i in range(count):
            target=total*i/(count-1)
            j=next((k for k in range(1,len(lengths)) if lengths[k]>=target),len(lengths)-1)
            span=max(1e-6,lengths[j]-lengths[j-1]); t=(target-lengths[j-1])/span
            out.append((pts[j-1][0]+t*(pts[j][0]-pts[j-1][0]), pts[j-1][1]+t*(pts[j][1]-pts[j-1][1])))
        return out

    def _draw_stroke(self, draw: ImageDraw.ImageDraw, pts: Stroke) -> None:
        if len(pts) < 2: return
        # Smoothly resample and apply pen-pressure width changes along the trajectory.
        pts=self._resample(pts, max(16, len(pts)*5))
        for a,b in zip(pts,pts[1:]):
            t=self.rng.random()
            width=max(1, int(self.profile.stroke_width*(1+self.profile.pressure*(t-.5))))
            draw.line([a,b], fill=self.profile.ink, width=width, joint='curve')
            if width > 2:
                r=width/2
                draw.ellipse([b[0]-r,b[1]-r,b[0]+r,b[1]+r], fill=self.profile.ink)

    def render(self, text: str, width: int = 1600, line_height: int = 110, margin: int = 90, ruled: bool = True) -> Image.Image:
        lines=text.splitlines() or ['']
        height=margin*2+line_height*len(lines)+40
        bg=(252,250,244)
        im=Image.new('RGB',(width,height),bg)
        draw=ImageDraw.Draw(im)
        if ruled:
            for y in range(margin+line_height, height-margin//2, line_height):
                draw.line((margin//2,y,width-margin//2,y), fill=(205,220,228), width=1)
            draw.line((margin-25,0,margin-25,height), fill=(235,170,170), width=2)
        for li,line in enumerate(lines):
            x=float(margin); baseline=float(margin+li*line_height+line_height*.68)
            em=58*self.profile.scale
            prev=None
            for ch in line:
                if ch==' ':
                    x += em*(0.55+self.profile.spacing); prev=None; continue
                if ch in ',.;:!?':
                    x += em*.18; yoff=self.rng.uniform(-2,2)
                    if ch in '.,': draw.ellipse((x,baseline-em*.12+yoff,x+5,baseline-em*.12+yoff+5),fill=self.profile.ink)
                    else: draw.line((x,baseline-em*.68+yoff,x+4,baseline-em*.42+yoff),fill=self.profile.ink,width=3)
                    prev=ch; x += em*.18; continue
                size=em*(1+self.rng.uniform(-self.profile.size_jitter,self.profile.size_jitter))
                y=baseline-self.rng.uniform(-self.profile.baseline_jitter,self.profile.baseline_jitter)
                skew=self.profile.slant+self.rng.uniform(-.035,.035)
                glyph=self.profile.glyph(ch)
                first=None; last=None
                for stroke in glyph:
                    transformed=[self._transform(p,x,y-size,size,skew) for p in stroke]
                    self._draw_stroke(draw,transformed)
                    if first is None: first=transformed[0]
                    last=transformed[-1]
                # Cursive ligature: a light, variable pen path between glyph endpoints.
                if prev not in (None,' ',',.;:!?') and self.rng.random() < self.profile.connect and first and last:
                    join_start=(x-em*.10, baseline-em*.05)
                    join_end=(first[0], first[1])
                    self._draw_stroke(draw,[join_start,((join_start[0]+join_end[0])/2,baseline-em*.20),join_end])
                advance=size*(.62+self.profile.spacing+self.rng.uniform(-.035,.04))
                x += advance
                prev=ch
                if x > width-margin: break
        return im.filter(ImageFilter.GaussianBlur(0.12))

def make_demo(out: str = 'demo_handwriting.png') -> None:
    profile=WriterProfile()
    renderer=HandwritingRenderer(profile, seed=41)
    image=renderer.render('Good morning, class!\nToday we learn about numbers and nature.\nWrite your answers carefully.', ruled=True)
    image.save(out, quality=95)

if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser(description='Generate unseen handwriting from stroke trajectories')
    ap.add_argument('text'); ap.add_argument('-o','--output',default='handwriting.png'); ap.add_argument('--profile')
    args=ap.parse_args()
    profile=WriterProfile.load(args.profile) if args.profile else WriterProfile()
    HandwritingRenderer(profile).render(args.text).save(args.output)
    print(args.output)
