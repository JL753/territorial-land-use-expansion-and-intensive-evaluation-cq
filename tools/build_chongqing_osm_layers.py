#!/usr/bin/env python3
"""Download the Geofabrik Chongqing OSM snapshot and split 3D-ready layers by 21 districts.

Requires pyosmium, Shapely 2 and the repository's validated district GeoJSON.
Buildings without measured height are marked as estimated, never as surveyed.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import osmium
from shapely.geometry import Point, shape, mapping
from shapely.strtree import STRtree
from shapely import wkb

URL="https://download.geofabrik.de/asia/china/chongqing-latest.osm.pbf"
UA="ShanchengDiyan/2.1 (OSM regional extract)"
POI_KEYS=("amenity","shop","tourism","leisure","office","healthcare","public_transport")
LAYERS=("buildings","roads","poi")

def download(url,dest):
    req=Request(url,headers={"User-Agent":UA})
    temporary=dest.with_suffix(dest.suffix+".part")
    try:
        with urlopen(req,timeout=60) as response:
            length=int(response.headers.get("Content-Length") or 0)
            if length>250*1024*1024: raise ValueError("Unexpectedly large regional PBF; refusing download.")
            with temporary.open("wb") as out:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk: break
                    out.write(chunk)
            os.replace(temporary,dest)
            return response.headers.get("Last-Modified")
    finally:
        if temporary.exists(): temporary.unlink()

def load_districts(path):
    geo=json.loads(path.read_text(encoding="utf-8"))
    features=geo.get("features",[])
    if geo.get("type")!="FeatureCollection" or len(features)!=21:
        raise ValueError("Expected exactly 21 validated district polygons.")
    items=[]
    for f in features:
        p=f["properties"]; geom=shape(f["geometry"])
        code=str(p["code"])
        if not re.fullmatch(r"\d{6}",code) or geom.is_empty or not geom.is_valid:
            raise ValueError("Invalid district geometry: "+code)
        items.append({"code":code,"name":p["district"],"group":p["group"],"geometry":geom})
    return items

def tags_dict(tags):
    return {str(t.k):str(t.v) for t in tags}

def number(value):
    if not value: return None
    match=re.match(r"^\s*(\d+(?:\.\d+)?)\s*(?:m|meter|metre|meters|metres)?\s*$",str(value),re.I)
    return float(match.group(1)) if match else None

def building_properties(tags):
    height=number(tags.get("height") or tags.get("building:height"))
    levels=number(tags.get("building:levels"))
    if height is not None:
        source="OSM height tag"
    elif levels is not None:
        height=levels*3.0; source="OSM levels × 3 m estimate"
    else:
        height=6.0; source="generic 6 m visualization estimate"
    return {"height_m":round(height,2),"height_source":source,
            "building_levels":levels,"building":tags.get("building","yes")}

class Extractor(osmium.SimpleHandler):
    def __init__(self,outputs,polygons,tree,manifest):
        super().__init__()
        self.outputs=outputs; self.polygons=polygons; self.tree=tree; self.manifest=manifest
        self.factory=osmium.geom.WKBFactory()
    def emit(self,layer,osm_id,geom,tags):
        if geom is None or geom.is_empty: return
        if not geom.is_valid:
            geom=geom.buffer(0)
            if geom.is_empty or not geom.is_valid: return
        for raw_index in self.tree.query(geom):
            i=int(raw_index); district=self.polygons[i]
            if not geom.intersects(district): continue
            clipped=geom.intersection(district)
            if clipped.is_empty: continue
            props={"osm_id":str(osm_id),"district_code":self.manifest["districts"][i]["code"],
                   "district":self.manifest["districts"][i]["name"]}
            for key in ("name","building","building:levels","height","building:height","highway",
                        "amenity","shop","tourism","leisure","office","healthcare","surface","oneway"):
                if tags.get(key): props[key]=tags[key]
            if layer=="buildings": props.update(building_properties(tags))
            stream=self.outputs[(layer,props["district_code"])]
            stream.write(json.dumps({"type":"Feature","geometry":mapping(clipped),"properties":props},
                                    ensure_ascii=False,separators=(",",":")))
            stream.write(",")
            self.manifest["counts"][layer][props["district_code"]]+=1
    def area(self,a):
        tags=tags_dict(a.tags)
        is_building=bool(tags.get("building"))
        is_poi=any(tags.get(k) for k in POI_KEYS)
        if not (is_building or is_poi): return
        try: geom=wkb.loads(self.factory.create_multipolygon(a),hex=True)
        except Exception: return
        if is_building: self.emit("buildings",a.id,geom,tags)
        if is_poi: self.emit("poi",a.id,geom,tags)
    def way(self,w):
        tags=tags_dict(w.tags)
        if not tags.get("highway"): return
        try: geom=wkb.loads(self.factory.create_linestring(w),hex=True)
        except Exception: return
        self.emit("roads",w.id,geom,tags)
    def node(self,n):
        tags=tags_dict(n.tags)
        if not any(tags.get(k) for k in POI_KEYS): return
        try: geom=Point(n.location.lon,n.location.lat)
        except Exception: return
        self.emit("poi",n.id,geom,tags)

def build(pbf,output_dir,district_path,snapshot_date=None):
    districts=load_districts(district_path)
    polygons=[d["geometry"] for d in districts]
    tree=STRtree(polygons)
    output_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="osm21-",dir=output_dir) as tmp:
        temp=Path(tmp); streams={}; manifest={
            "schema":1,"source_url":URL,"license":"Open Database License 1.0 (ODbL)",
            "attribution":"© OpenStreetMap contributors","snapshot_date":None,
            "pbf_sha256":hashlib.sha256(pbf.read_bytes()).hexdigest(),
            "generated_at":datetime.now(timezone.utc).isoformat(),"snapshot_date":snapshot_date,
            "districts":[{"code":d["code"],"name":d["name"],"group":d["group"]} for d in districts],
            "counts":{layer:{d["code"]:0 for d in districts} for layer in LAYERS}}
        for layer in LAYERS:
            for d in districts:
                path=temp/f"{layer}_{d['code']}.geojson"
                stream=path.open("w",encoding="utf-8")
                stream.write('{"type":"FeatureCollection","features":[')
                streams[(layer,d["code"])]=(stream,path)
        handler=Extractor({k:v[0] for k,v in streams.items()},polygons,tree,manifest)
        handler.apply_file(str(pbf),locations=True,idx="flex_mem")
        for (layer,code),(stream,path) in streams.items():
            if manifest["counts"][layer][code]: stream.seek(stream.tell()-1)
            stream.write("]}")
            stream.close()
        manifest["files"]={f"{layer}_{d['code']}.geojson":{
            "features":manifest["counts"][layer][d["code"]]} for layer in LAYERS for d in districts}
        (temp/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        for path in temp.iterdir():
            target=output_dir/path.name
            os.replace(path,target)
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf",type=Path,default=Path("state/chongqing-latest.osm.pbf"))
    parser.add_argument("--output-dir",type=Path,default=Path("state/osm-21"))
    parser.add_argument("--districts",type=Path,default=Path("results/socioeconomic/four-year-exploratory/districts.geojson"))
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    if args.force and args.pbf.exists(): args.pbf.unlink()
    if not args.pbf.exists():
        args.pbf.parent.mkdir(parents=True,exist_ok=True)
        print("Downloading Geofabrik Chongqing regional snapshot…",flush=True)
        modified=download(URL,args.pbf)
        print("Snapshot Last-Modified: "+str(modified),flush=True)
    else:
        modified=datetime.fromtimestamp(args.pbf.stat().st_mtime,timezone.utc).isoformat()
    result=build(args.pbf,args.output_dir,args.districts,modified)
    print(json.dumps({"counts":result["counts"],"pbf_sha256":result["pbf_sha256"]},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
