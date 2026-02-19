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

# City detail data
CITY_INFO = {
    "Tokyo": {
        "recommended_days": "5-6 days",
        "best_for": "Shopping, Tech, Anime, Nightlife",
        "daily_budget": "15,000-25,000",
        "attractions": [
            {"name": "Senso-ji Temple", "description": "Tokyo's oldest temple in Asakusa with iconic red lantern", "url": "https://www.senso-ji.jp/"},
            {"name": "Shibuya Crossing", "description": "World's busiest pedestrian crossing, iconic Tokyo experience", "url": ""},
            {"name": "teamLab Borderless", "description": "Immersive digital art museum - book in advance!", "url": "https://www.teamlab.art/"},
            {"name": "Meiji Shrine", "description": "Serene Shinto shrine in the heart of Harajuku", "url": "https://www.meijijingu.or.jp/en/"},
            {"name": "Tokyo Skytree", "description": "634m tower with observation decks and stunning views", "url": "https://www.tokyo-skytree.jp/en/"},
            {"name": "Akihabara", "description": "Electric Town - anime, manga, gaming paradise", "url": ""},
        ],
        "food": [
            {"name": "Ramen", "description": "Try Ichiran (solo booths) or Fuunji (tsukemen)"},
            {"name": "Sushi", "description": "Tsukiji Outer Market for fresh breakfast sushi"},
            {"name": "Yakitori", "description": "Memory Lane (Omoide Yokocho) in Shinjuku"},
            {"name": "Conveyor Belt Sushi", "description": "Genki Sushi or Sushiro for budget-friendly"},
        ],
        "tips": [
            "Get a Suica/Pasmo card for easy transport",
            "Book teamLab tickets 2-3 weeks in advance",
            "Shibuya Sky sunset views are incredible",
            "Convenience store food is surprisingly good",
            "Free WiFi is limited - consider pocket WiFi",
        ],
        "links": [
            {"name": "Tokyo Metro Map", "url": "https://www.tokyometro.jp/en/"},
            {"name": "Japan Rail Pass", "url": "https://japanrailpass.net/"},
            {"name": "Tokyo Tourism", "url": "https://www.gotokyo.org/en/"},
        ]
    },
    "Kyoto": {
        "recommended_days": "4-5 days",
        "best_for": "Temples, Traditional Culture, Gardens",
        "daily_budget": "12,000-20,000",
        "attractions": [
            {"name": "Fushimi Inari Shrine", "description": "Thousands of orange torii gates - go early morning!", "url": "https://inari.jp/en/"},
            {"name": "Kinkaku-ji (Golden Pavilion)", "description": "Iconic gold-leaf covered temple", "url": ""},
            {"name": "Arashiyama Bamboo Grove", "description": "Stunning bamboo forest - arrive at sunrise", "url": ""},
            {"name": "Gion District", "description": "Historic geisha district, traditional architecture", "url": ""},
            {"name": "Kiyomizu-dera", "description": "Hillside temple with wooden stage and city views", "url": "https://www.kiyomizudera.or.jp/en/"},
            {"name": "Nijo Castle", "description": "Shogun castle with nightingale floors", "url": ""},
        ],
        "food": [
            {"name": "Kaiseki", "description": "Traditional multi-course haute cuisine"},
            {"name": "Matcha", "description": "Green tea everything - Nishiki Market has great options"},
            {"name": "Yudofu", "description": "Hot tofu dishes, especially around Nanzen-ji"},
            {"name": "Obanzai", "description": "Kyoto-style home cooking"},
        ],
        "tips": [
            "Rent a bicycle - Kyoto is very bike-friendly",
            "Visit Fushimi Inari at 6am to avoid crowds",
            "Book geisha/maiko experiences in advance",
            "Many temples close by 5pm",
            "Gion corner has cultural shows",
        ],
        "links": [
            {"name": "Kyoto Tourism", "url": "https://kyoto.travel/en/"},
            {"name": "Kyoto Bus Info", "url": "https://www.city.kyoto.lg.jp/kotsu/"},
        ]
    },
    "Osaka": {
        "recommended_days": "2-3 days",
        "best_for": "Street Food, Nightlife, Entertainment",
        "daily_budget": "10,000-18,000",
        "attractions": [
            {"name": "Dotonbori", "description": "Neon-lit entertainment district, iconic Glico sign", "url": ""},
            {"name": "Osaka Castle", "description": "Historic castle with museum and park", "url": "https://www.osakacastle.net/english/"},
            {"name": "Shinsekai", "description": "Retro district with Tsutenkaku Tower", "url": ""},
            {"name": "Kuromon Market", "description": "Kitchen of Osaka - fresh seafood and street food", "url": ""},
            {"name": "Universal Studios Japan", "description": "Theme park with Nintendo World", "url": "https://www.usj.co.jp/web/en/us"},
        ],
        "food": [
            {"name": "Takoyaki", "description": "Octopus balls - try at Dotonbori stalls"},
            {"name": "Okonomiyaki", "description": "Savory pancakes - Osaka style"},
            {"name": "Kushikatsu", "description": "Deep-fried skewers in Shinsekai"},
            {"name": "Kani Doraku", "description": "Famous crab restaurant with moving crab sign"},
        ],
        "tips": [
            "Osaka people are known for being friendly and funny",
            "Food is generally cheaper than Tokyo/Kyoto",
            "Great base for day trips to Nara and Kobe",
            "Don't double-dip kushikatsu!",
            "Nightlife goes late in Dotonbori",
        ],
        "links": [
            {"name": "Osaka Tourism", "url": "https://osaka-info.jp/en/"},
        ]
    },
    "Nara": {
        "recommended_days": "1 day",
        "best_for": "Day trip, Deer, Ancient temples",
        "daily_budget": "5,000-10,000",
        "attractions": [
            {"name": "Nara Park", "description": "Home to 1,200+ friendly (hungry) deer", "url": ""},
            {"name": "Todai-ji Temple", "description": "World's largest wooden building with giant Buddha", "url": "https://www.todaiji.or.jp/en/"},
            {"name": "Kasuga Grand Shrine", "description": "Famous for thousands of stone and bronze lanterns", "url": ""},
            {"name": "Isuien Garden", "description": "Beautiful Japanese garden with Todai-ji views", "url": ""},
        ],
        "food": [
            {"name": "Kakinoha-zushi", "description": "Sushi wrapped in persimmon leaves"},
            {"name": "Deer crackers", "description": "Shika senbei - for the deer, not you!"},
            {"name": "Narazuke", "description": "Vegetables pickled in sake lees"},
        ],
        "tips": [
            "Day trip from Osaka or Kyoto (45 min)",
            "Buy deer crackers from official vendors (¥200)",
            "Deer can be pushy - watch your belongings",
            "Most sites walkable from station",
            "Less crowded on weekdays",
        ],
        "links": [
            {"name": "Nara Tourism", "url": "https://www.visitnara.jp/"},
        ]
    },
    "Hiroshima": {
        "recommended_days": "1-2 days",
        "best_for": "History, Peace, Miyajima island",
        "daily_budget": "10,000-15,000",
        "attractions": [
            {"name": "Peace Memorial Park", "description": "Moving memorial and museum about atomic bombing", "url": "https://hpmmuseum.jp/?lang=eng"},
            {"name": "Atomic Bomb Dome", "description": "UNESCO World Heritage Site, preserved as bombed", "url": ""},
            {"name": "Miyajima Island", "description": "Famous floating torii gate (ferry from Hiroshima)", "url": ""},
            {"name": "Itsukushima Shrine", "description": "Iconic shrine with gate in the sea", "url": ""},
            {"name": "Hiroshima Castle", "description": "Reconstructed castle with history museum", "url": ""},
        ],
        "food": [
            {"name": "Hiroshima-style Okonomiyaki", "description": "Layered style with noodles - different from Osaka!"},
            {"name": "Oysters", "description": "Miyajima is famous for grilled oysters"},
            {"name": "Momiji Manju", "description": "Maple leaf-shaped cakes"},
        ],
        "tips": [
            "Peace Museum is emotionally heavy - take your time",
            "Miyajima: check tide times for floating torii",
            "JR Pass covers ferry to Miyajima",
            "Okonomimura building has many okonomiyaki restaurants",
            "Stay overnight on Miyajima for sunset/sunrise",
        ],
        "links": [
            {"name": "Hiroshima Tourism", "url": "https://visithiroshima.net/"},
            {"name": "Miyajima Info", "url": "https://www.miyajima.or.jp/english/"},
        ]
    },
    "Hakone": {
        "recommended_days": "1-2 days",
        "best_for": "Mt. Fuji views, Onsen, Nature",
        "daily_budget": "15,000-25,000",
        "attractions": [
            {"name": "Hakone Open-Air Museum", "description": "Outdoor sculpture park with Picasso pavilion", "url": "https://www.hakone-oam.or.jp/en/"},
            {"name": "Lake Ashi", "description": "Scenic lake with pirate ship cruises and Fuji views", "url": ""},
            {"name": "Owakudani", "description": "Volcanic valley with black eggs and sulfur vents", "url": ""},
            {"name": "Hakone Shrine", "description": "Lakeside shrine with red torii gate in water", "url": ""},
            {"name": "Onsen", "description": "Many ryokans and hotels with natural hot springs", "url": ""},
        ],
        "food": [
            {"name": "Black Eggs", "description": "Eggs boiled in volcanic springs - adds 7 years to life!"},
            {"name": "Kaiseki", "description": "Traditional multi-course dinner at ryokan"},
            {"name": "Tofu", "description": "Local specialty, especially yuba (tofu skin)"},
        ],
        "tips": [
            "Get Hakone Free Pass for transport savings",
            "Mt. Fuji views depend on weather - mornings are best",
            "Book ryokan with private onsen for best experience",
            "Hakone Loop: train → cable car → ropeway → boat → bus",
            "2 days ideal: one for sightseeing, one for onsen relaxation",
        ],
        "links": [
            {"name": "Hakone Free Pass", "url": "https://www.hakonenavi.jp/international/en/"},
            {"name": "Hakone Tourism", "url": "https://www.hakone.or.jp/en/"},
        ]
    },
}

@app.get("/cities/{city_id}", response_class=HTMLResponse)
async def city_detail(request: Request, city_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    city = session.get(City, city_id)
    if not city:
        return RedirectResponse(url="/cities")
    
    city_info = CITY_INFO.get(city.name, {
        "recommended_days": "2-3 days",
        "best_for": "Explore",
        "daily_budget": "10,000-15,000",
        "attractions": [],
        "food": [],
        "tips": [],
        "links": []
    })
    
    return templates.TemplateResponse("city_detail.html", {
        "request": request,
        "user": current_user,
        "city": city,
        "city_info": city_info
    })

@app.get("/api/ai-analysis")
async def ai_analysis(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    cities = session.exec(select(City).order_by(City.order)).all()
    accommodations = session.exec(select(Accommodation)).all()
    expenses = session.exec(select(Expense)).all()
    
    city_names = [c.name for c in cities]
    total_budget = sum(e.amount for e in expenses)
    hotel_count = len(accommodations)
    
    # Generate analysis based on current data
    analysis = f"""📊 **Trip Analysis - Japan 2026**

🗓️ **Duration:** 22 days (May 7-28)
🏙️ **Cities planned:** {len(cities)} ({', '.join(city_names)})
🏨 **Accommodations booked:** {hotel_count}
💰 **Budget logged:** ¥{total_budget:,.0f}

---

📍 **Route Suggestion:**
Based on your cities, here's an optimal route:

1. **Tokyo** (5-6 days) - Start here, adjust to jet lag
2. **Hakone** (1-2 days) - Day trip or overnight for Mt. Fuji views
3. **Kyoto** (4-5 days) - Take shinkansen from Tokyo
4. **Nara** (1 day) - Easy day trip from Kyoto
5. **Osaka** (2-3 days) - Base for food and nightlife
6. **Hiroshima + Miyajima** (2 days) - Day trip or overnight

This follows a logical west-bound path using JR Pass efficiently.

---

💡 **Recommendations:**

✅ **Get a 21-day JR Pass** (~¥60,000) - Covers all shinkansen and most JR lines
✅ **Book teamLab Borderless** tickets NOW - They sell out weeks ahead
✅ **Consider ryokan in Hakone** - Onsen experience is a must
✅ **Pocket WiFi or eSIM** - Essential for navigation

⚠️ **Watch out for:**
- Golden Week crowds (late April-early May) - You're right after, good timing!
- Temple closing times (most close 5pm)
- Cash is still king in many places

---

🍜 **Food Budget Tip:**
- Convenience stores (7-11, Lawson): ¥500-800/meal
- Ramen/casual: ¥800-1,500
- Nice restaurant: ¥2,000-5,000
- Estimated daily food: ¥3,000-5,000

---

{'🏨 **Hotel Alert:** You have no accommodations booked yet! Book popular areas early.' if hotel_count == 0 else f'🏨 You have {hotel_count} accommodation(s) booked.'}

Need more specific advice? Add your itinerary details and ask again!
"""
    
    return {"analysis": analysis}

@app.post("/budget")
async def add_expense(request: Request, description: str = Form(...), amount: float = Form(...), date: date = Form(...), category: str = Form("Other"), split_with: str = Form(None), current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    expense = Expense(user_id=current_user.id, description=description, amount=amount, date=date, category=category, split_with=split_with)
    session.add(expense)
    session.commit()
    return RedirectResponse(url="/budget", status_code=status.HTTP_302_FOUND)