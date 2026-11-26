from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session


from app.schemas import UserCreate, UserRead
from app.database import Base, engine, get_db
from app.models import User
from app.security import hash_password

app = FastAPI(title="bank-server")

# Create database tables if they don't exist
Base.metadata.create_all(bind=engine)

@app.get("/")
def get_home():
    return {"message" : "Server Running"}

@app.post("/auth/register", response_model=UserRead)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registred")

    new_user = User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        password_hash=hash_password(user.password),
        date_of_birth=user.date_of_birth,
        phone_number=user.phone_number,
        country_code=user.country_code,
        address_line=user.address_line,
        city=user.city,
        postal_code=user.postal_code
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user
