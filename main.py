from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import URL

import validators
from config import get_settings
import crud
import database
import models
import schemas


app = FastAPI()
models.Base.metadata.create_all(bind=database.engine)


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return "Welcome to the URL Shortener API!"


def raise_bad_request(message: str):
    raise HTTPException(status_code=400, detail=message)


def raise_not_found(request):
    message = f"URL with key {request.url} not found."
    raise HTTPException(status_code=404, detail=message)


@app.post("/url", response_model=schemas.URLInfo)
def create_url(url: schemas.URLBase, db: Session = Depends(get_db)):
    if not validators.url(url.target_url):
        raise_bad_request(message="Your provided URL is not valid.")

    db_url = crud.create_db_url(db, url)
    db_url.url = db_url.key
    db_url.admin_url = db_url.secret_key
    return get_admin_info(db_url)


@app.get("/{url_key}")
def forward_to_target_url(
    url_key: str, request: Request, db: Session = Depends(get_db)
):
    if db_url := crud.get_db_url_by_key(db, url_key):
        crud.update_db_clicks(db, db_url)
        return RedirectResponse(db_url.target_url)  # type: ignore
    else:
        raise_not_found(request)


@app.get(
    "/admin/{secret_key}", name="administration info", response_model=schemas.URLInfo
)
def get_url_info(secret_key: str, request: Request, db: Session = Depends(get_db)):
    if db_url := crud.get_db_url_by_secret_key(db, secret_key):
        db_url.url = db_url.key
        db_url.admin_url = db_url.secret_key
        return get_admin_info(db_url)
    else:
        raise_not_found(request)


def get_admin_info(db_url: models.URL) -> schemas.URLInfo:
    base_url = URL(get_settings().base_url)
    admin_endpoint = app.url_path_for(
        "administration info", secret_key=db_url.secret_key
    )
    db_url.url = str(base_url.replace(path=db_url.key))
    db_url.admin_url = str(base_url.replace(path=admin_endpoint))
    return db_url


@app.delete("/admin/{secret_key}")
def delete_url(secret_key: str, request: Request, db: Session = Depends(get_db)):
    if db_url := crud.deactivate_db_url_by_secret_key(db, secret_key):
        message = f"Successfully deleted shortened URL for {db_url.target_url}."
        return {"detail": message}
    else:
        raise_not_found(request)
