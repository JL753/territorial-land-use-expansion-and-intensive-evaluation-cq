#!/usr/bin/env python3
"""Build annual CLCD statistics for 21 Chongqing districts using remote COG windows.

Only each district's raster window is read through GDAL HTTP Range requests;
the China-wide CLCD archive is not downloaded. Results are separate from the
socioeconomic panel and are never used to invent intensive-use scores.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from rasterio.warp import transform_geom
from shapely.geometry import shape

RECORD_ID="18180184"
RECORD_API=f"https://zenodo.org/api/records/{RECORD_ID}"
DOI="10.5281/zenodo.18180184"
CLASSES={1:"cropland",2:"forest",3:"shrub",4:"grassland",5:"water",6:"snow",7:"barren",8:"built",9:"wetland"}
UA="ShanchengDiyan/2.1 (research data processing)"

def fetch_json(url):
    req=Request(url,headers={"Accept":"application/json","User-Agent":UA})
    with urlopen(req,timeout=40) as response: return json.load(response)

def load_catalog(path):
    geo=json.loads(path.read_text(encoding="utf-8"))
    if geo.get("type")!="FeatureCollection" or len(geo.get("features",[]))!=21:
        raise ValueError("Expected validated 21-district GeoJSON.")
    result=[]; seen=set()
    for feature in geo["features"]:
        p=feature["properties"]; code=str(p["code"]); geom=feature["geometry"]
        if len(code)!=6 or code in seen or shape(geom).geom_type not in ("Polygon","MultiPolygon"):
            raise ValueError(f"Invalid or duplicate district geometry: {code}")
        seen.add(code); result.append({"code":code,"district":p["district"],"group":p["group"],"geometry":geom})
    return sorted(result,key=lambda x:x["code"])

def year_of(name):
    m=re.search(r"(?<!\d)((?:19|20)\d{2})(?=_albert\.tif$)",name)
    return int(m.group(1)) if m else None

def build_series(districts,output,requested_years=None):
    record=fetch_json(RECORD_API); candidates={}
    for item in record.get("files",[]):
        year=year_of(item.get("key",""))
        if year and item.get("key","").endswith("_albert.tif"): candidates[year]=item
    if not candidates: raise RuntimeError("Zenodo record did not expose annual *_albert.tif COG files.")
    years=sorted(candidates)
    if requested_years:
        missing=requested_years-set(years)
        if missing: raise ValueError("Requested years unavailable: "+", ".join(map(str,sorted(missing))))
        years=[y for y in years if y in requested_years]
    if not years: raise ValueError("No CLCD years selected.")
    output.parent.mkdir(parents=True,exist_ok=True)
    rows=[]; previous={}; previous_year=None
    projected=None; windows=None; masks=None; source_crs=None; source_transform=None; pixel_area=None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                      GDAL_HTTP_MAX_RETRY="3",GDAL_HTTP_RETRY_DELAY="2",GDAL_CACHEMAX="256"):
        for year in years:
            item=candidates[year]; key=item["key"]
            url=item.get("links",{}).get("download") or f"https://zenodo.org/records/{record['id']}/files/{key}?download=1"
            print(f"[{year}] opening remote COG: {key}",flush=True)
            with rasterio.open("/vsicurl/"+url) as src:
                if src.crs is None or src.count!=1: raise ValueError(f"{key}: expected one-band georeferenced raster.")
                if source_crs is None:
                    source_crs=src.crs; source_transform=src.transform
                    pixel_area=abs(src.transform.a*src.transform.e-src.transform.b*src.transform.d)/1_000_000
                    projected=[transform_geom("EPSG:4326",src.crs,d["geometry"],precision=3) for d in districts]
                    windows=[]; masks=[]
                    for geom in projected:
                        b=shape(geom).bounds
                        win=from_bounds(*b,transform=src.transform).round_offsets().round_lengths()
                        win=win.intersection(Window(0,0,src.width,src.height))
                        windows.append(win)
                        masks.append(geometry_mask([geom],out_shape=(int(win.height),int(win.width)),
                                                   transform=src.window_transform(win),invert=True))
                elif src.crs!=source_crs or src.transform!=source_transform:
                    raise ValueError(f"{key}: annual rasters do not share one grid.")
                for index,district in enumerate(districts):
                    current=src.read(1,window=windows[index])
                    inside=masks[index]; values=current[inside]
                    valid=values[(values>=1)&(values<=9)]
                    counts=np.bincount(valid.astype(np.int16),minlength=10)
                    admin=shape(projected[index]).area/1_000_000
                    row={"code":district["code"],"district":district["district"],"group":district["group"],
                         "year":year,"data_kind":"remote_sensing_only","source":"CLCD 30 m annual land cover",
                         "admin_km2":round(admin,4),"valid_area_km2":round(int(counts[1:].sum())*pixel_area,4),
                         "nodata_area_km2":round(max(0,int(inside.sum())-int(counts[1:].sum()))*pixel_area,4),
                         "built_km2":round(int(counts[8])*pixel_area,4),
                         "class_area_km2":{label:round(int(counts[c])*pixel_area,4) for c,label in CLASSES.items()},
                         **{f"{label}_km2":round(int(counts[c])*pixel_area,4) for c,label in CLASSES.items()},
                         "clcd_record_id":str(record.get("id",RECORD_ID)),"clcd_file":key,
                         "clcd_file_checksum":item.get("checksum")}
                    before=previous.get(district["code"])
                    if before is not None:
                        prior=before[inside]
                        pair=((prior>=1)&(prior<=9)&(values>=1)&(values<=9))
                        matrix=np.bincount(prior[pair].astype(np.int16)*10+values[pair].astype(np.int16),
                                           minlength=100).reshape(10,10)[1:10,1:10]
                        added=int(matrix[:,7].sum()-matrix[7,7]); lost=int(matrix[7,:].sum()-matrix[7,7])
                        net=added-lost; interval=year-previous_year
                        row.update({"previous_year":previous_year,"interval_years":interval,
                            "added_km2":round(added*pixel_area,4),"lost_km2":round(lost*pixel_area,4),
                            "expansion_km2":round(net*pixel_area,4),
                            "annual_expansion_intensity_pct":round(net*pixel_area/max(admin,1e-9)/interval*100,6),
                            "transition_km2":(matrix*pixel_area).round(6).tolist()})
                    rows.append(row)
                    previous[district["code"]]=current
            previous_year=year
            print(f"[{year}] processed 21 districts",flush=True)
    payload={"schema":1,"status":"ready","generated_at":datetime.now(timezone.utc).isoformat(),
      "source":{"name":"CLCD 30 m annual land-cover dataset","doi":DOI,"record_id":str(record.get("id",RECORD_ID)),
        "version":record.get("metadata",{}).get("version"),
        "license":record.get("metadata",{}).get("license",{}).get("id","CC-BY-4.0"),
        "crs":str(source_crs),"pixel_area_km2":pixel_area,"years":years,
        "processing":"Remote COG window read; 21 district polygon masks; equal-area pixel aggregation; class transition matrices.",
        "limitations":["CLCD is annual Landsat-derived land cover, not real-time imagery.",
          "CLCD class 8 impervious surface is an operational proxy, not statutory construction land.",
          "Only remote-sensing indicators are produced; population/GDP and intensive-use scores are not inferred.",
          "Area results depend on boundary version and classification accuracy."]},"rows":rows}
    tmp=output.with_suffix(output.suffix+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    os.replace(tmp,output); checksum=hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"Wrote {len(rows)} rows / {len(years)} years: {output} sha256={checksum}",flush=True)
    return payload

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--districts",type=Path,default=Path("results/socioeconomic/four-year-exploratory/districts.geojson"))
    p.add_argument("--output",type=Path,default=Path("state/clcd-district-series.json"))
    p.add_argument("--years",help="Comma-separated years; default processes every annual COG available in Zenodo.")
    a=p.parse_args(); selected={int(v) for v in a.years.split(",")} if a.years else None
    payload=build_series(load_catalog(a.districts),a.output,selected)
    print(f"CLCD {payload['source']['years'][0]}—{payload['source']['years'][-1]} ready.")

if __name__=="__main__":
    try: main()
    except Exception as error:
        print(f"ERROR: {type(error).__name__}: {error}",file=sys.stderr); raise
