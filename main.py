from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

inventory = []   # ← MUST be here (global)

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "inventory": inventory
    })

@app.post("/add")
def add_item(
    sku: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...)
):
    inventory.append({
        "sku": sku,
        "description": description,
        "quantity": quantity
    })

    return RedirectResponse(url="/", status_code=303)
