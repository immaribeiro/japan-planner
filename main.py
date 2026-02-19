import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, Depends, HTTPException, status, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional

from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import User, SessionData, City, ItineraryDay, Activity, Accommodation, Flight, Expense
from auth import (
    get_password_hash, verify_password,
    UserLogin, create_user_session, invalidate_user_session,
    get_current_user, get_current_user_optional, get_current_admin_user,
    SESSION_COOKIE_NAME
)
from config import settings
import crud

# --- FastAPI App Setup ---
app = FastAPI(root_path=settings.ROOT_PATH)

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Configure Jinja2Templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Seed initial users and cities
    with next(get_session()) as session:
        # Create admin user 'imma' if not exists
        admin_user = session.exec(select(User).where(User.username == "imma")).first()
        if not admin_user:
            hashed_password = get_password_hash("admin") # Use a strong password
            imma_user = User(username="imma", password_hash=hashed_password, is_admin=True)
            crud.create_object(session, imma_user)
            print("Created admin user: imma")

        # Create regular user 'pedro.rodrigues' if not exists
        pedro_user = session.exec(select(User).where(User.username == "pedro.rodrigues")).first()
        if not pedro_user:
            hashed_password = get_password_hash("pedro") # Use a strong password
            pedro_rodrigues = User(username="pedro.rodrigues", password_hash=hashed_password, is_admin=False)
            crud.create_object(session, pedro_rodrigues)
            print("Created user: pedro.rodrigues")

        # Seed initial cities if not exist
        cities_to_seed = [
            {"name": "Tokyo", "country": "Japan", "lat": 35.6895, "lon": 139.6917, "description": "Capital of Japan", "order": 1},
            {"name": "Kyoto", "country": "Japan", "lat": 35.0116, "lon": 135.7681, "description": "Ancient capital with temples and gardens", "order": 2},
            {"name": "Osaka", "country": "Japan", "lat": 34.6937, "lon": 135.5023, "description": "Foodie paradise", "order": 3},
            {"name": "Nara", "country": "Japan", "lat": 34.6851, "lon": 135.8048, "description": "Home to friendly deer", "order": 4},
            {"name": "Hiroshima", "country": "Japan", "lat": 34.3853, "lon": 132.4553, "description": "City of peace", "order": 5},
            {"name": "Hakone", "country": "Japan", "lat": 35.2333, "lon": 139.0333, "description": "Mountain town with views of Mt. Fuji", "order": 6},
        ]
        for city_data in cities_to_seed:
            existing_city = session.exec(select(City).where(City.name == city_data["name"])).first()
            if not existing_city:
                city = City(**city_data)
                crud.create_object(session, city)
                print(f"Created city: {city.name}")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    user_data = UserLogin(username=username, password=password)
    user = session.exec(select(User).where(User.username == user_data.username)).first()

    if not user or not verify_password(user_data.password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Incorrect username or password"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    redirect_response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    await create_user_session(redirect_response, user.id, session)
    return redirect_response

@app.post("/logout")
async def logout(request: Request, response: Response, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    await invalidate_user_session(response, request, session)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_user(request: Request, response: Response, username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == username)).first()
    if user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username already registered"},
            status_code=status.HTTP_409_CONFLICT
        )

    hashed_password = get_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password, is_admin=False)
    crud.create_object(session, new_user)
    await create_user_session(response, new_user.id, session)
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@app.get("/me")
async def read_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "is_admin": current_user.is_admin}

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, current_user: User = Depends(get_current_admin_user)):
    return templates.TemplateResponse("admin.html", {"request": request, "user": current_user})

# ==================== PAGES ====================

from datetime import date, timedelta

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: Optional[User] = Depends(get_current_user_optional), session: Session = Depends(get_session)):
    if not current_user:
        return RedirectResponse(url="/login")
    
    cities = session.exec(select(City).order_by(City.order)).all()
    trip_start = date(2026, 5, 7)
    days_until = (trip_start - date.today()).days
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": current_user,
        "cities": cities,
        "days_until": days_until
    })

@app.get("/cities", response_class=HTMLResponse)
async def cities_page(request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    cities = session.exec(select(City).order_by(City.order)).all()
    return templates.TemplateResponse("cities.html", {"request": request, "user": current_user, "cities": cities})

@app.post("/cities")
async def add_city(request: Request, name: str = Form(...), description: str = Form(""), lat: float = Form(...), lon: float = Form(...), current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    city = City(name=name, description=description, lat=lat, lon=lon, country="Japan", order=99)
    session.add(city)
    session.commit()
    return RedirectResponse(url="/cities", status_code=status.HTTP_302_FOUND)

@app.get("/itinerary", response_class=HTMLResponse)
async def itinerary_page(request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    trip_start = date(2026, 5, 7)
    trip_end = date(2026, 5, 28)
    
    days = []
    current_date = trip_start
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    while current_date <= trip_end:
        days.append({
            'date': current_date.isoformat(),
            'day': current_date.day,
            'weekday': weekdays[current_date.weekday()],
            'city': None,
            'title': None,
            'activities': []
        })
        current_date += timedelta(days=1)
    
    return templates.TemplateResponse("itinerary.html", {"request": request, "user": current_user, "days": days})

@app.get("/accommodations", response_class=HTMLResponse)
async def accommodations_page(request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    accommodations = session.exec(select(Accommodation)).all()
    cities = session.exec(select(City).order_by(City.order)).all()
    return templates.TemplateResponse("accommodations.html", {
        "request": request, 
        "user": current_user, 
        "accommodations": accommodations,
        "cities": cities
    })

@app.post("/accommodations")
async def add_accommodation(request: Request, name: str = Form(...), address: str = Form(...), city_id: int = Form(...), check_in: date = Form(...), check_out: date = Form(...), cost: float = Form(None), booking_url: str = Form(None), current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    acc = Accommodation(name=name, address=address, city_id=city_id, check_in=check_in, check_out=check_out, cost=cost, booking_url=booking_url)
    session.add(acc)
    session.commit()
    return RedirectResponse(url="/accommodations", status_code=status.HTTP_302_FOUND)

@app.get("/budget", response_class=HTMLResponse)
async def budget_page(request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    expenses = session.exec(select(Expense).where(Expense.user_id == current_user.id)).all()
    total = sum(e.amount for e in expenses)
    return templates.TemplateResponse("budget.html", {
        "request": request, 
        "user": current_user, 
        "expenses": expenses,
        "total_expenses": total,
        "user_share": total,
        "per_day": round(total / 22, 2) if total > 0 else 0
    })

@app.post("/budget")
async def add_expense(request: Request, description: str = Form(...), amount: float = Form(...), date: date = Form(...), category: str = Form("Other"), split_with: str = Form(None), current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    expense = Expense(user_id=current_user.id, description=description, amount=amount, date=date, category=category, split_with=split_with)
    session.add(expense)
    session.commit()
    return RedirectResponse(url="/budget", status_code=status.HTTP_302_FOUND)