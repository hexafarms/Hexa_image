from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
import boto3
import os
from pathlib import Path
from openHexa.utils.helpers import getNewVersion
from tools.process import compute_raw_area_api
from configs.aws import prepare_configs, getFiles
import glob
from typing import Union

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hexafarms": "openHexa V1"}


@app.get("/instantseg")
async def sync_instantSeg(location: str, version: Union[str, None] = None):

    if location is None:
        return {"Warning": "Location is not provided!"}

    mode = "mmdet"

    weightDir = os.path.join("/openHexa/weights", mode)

    # Download config, weight, meta file, and return S3 client.
    
    s3_client=prepare_configs(mode, weightDir)
    
    newVersion = getNewVersion(weightDir, version)

    imgDir = os.path.join("/openHexa/images", location)
    Path(imgDir).mkdir(parents=True, exist_ok=True)

    bucketName = 'blink-'+location
    imgsS3 = set([i['Key'] for i in s3_client.list_objects(Bucket=bucketName)['Contents'] if "ir" not in i['Key']]) # exclude ir images.
    imgsDB = set(getFiles(
        sql= f"SELECT top_view.file_name, img_format.format FROM top_view \
            JOIN img_format \
            ON img_format.img_format_id = top_view.img_format \
            WHERE top_view.location = \
            (SELECT location_id from locations WHERE location='{location}');"
        ) )
    imgsLocal = set(glob.glob(os.path.join(imgDir, '*.jpg'))) | set(glob.glob(os.path.join(imgDir, '*.png')))

    imgs2Download = list(imgsS3 - imgsDB - imgsLocal)

    for file in imgs2Download:
        s3_client.download_file(bucketName, file, os.path.join(imgDir, location, file))

    imgs2Update = list(imgsLocal - imgsDB)

    areas = compute_raw_area_api(
        imgs2Update, newVersion, IMGFILE_DIR= imgDir, mode= mode)
    
    return ORJSONResponse(areas)
    