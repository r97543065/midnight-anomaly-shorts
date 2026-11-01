#!/usr/bin/env python3
"""Display approved source panels fully, letterboxed in 9:16 without cropping story content."""
import json
from pathlib import Path
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"stories/bonus/20261101-umbrella-bus-reviewed.json"

def stage():
    story=json.loads(SOURCE.read_text(encoding="utf-8"))
    folder=ROOT/"assets/episodes/20261101-umbrella-bus-reviewed/vertical"
    folder.mkdir(parents=True,exist_ok=True)
    for i,scene in enumerate(story["assets"]["images"],1):
        source=ROOT/scene["file"]
        with Image.open(source) as im:
            assert im.format=="WEBP" and getattr(im,"n_frames",1)==1
            image=ImageOps.contain(im.convert("RGB"),(1060,1880),Image.Resampling.LANCZOS)
        canvas=Image.new("RGB",(1080,1920),(10,17,23))
        canvas.paste(image,((1080-image.width)//2,(1920-image.height)//2))
        target=folder/f"scene{i:02d}.png"
        canvas.save(target,format="PNG")
        scene["file"]=str(target.relative_to(ROOT))
    (ROOT/"stories/today.json").write_text(json.dumps(story,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    job={"schema_version":1,"story_id":story["story_id"],"publication_approved":False,
         "scene_images":[{"file":x["file"],"effect":x.get("effect","slow_zoom")} for x in story["assets"]["images"]],
         "product_ad":{"enabled":False}}
    (ROOT/"jobs/daily-ad-job.json").write_text(json.dumps(job,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Staged seven approved storyboard stills into full-content 1080x1920 letterboxes")

if __name__=="__main__":
    stage()
