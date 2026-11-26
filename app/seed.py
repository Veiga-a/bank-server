from app.database import Base, SessionLocal, engine
from app.models import Country, Currency

from sqlalchemy.orm import Session

countries = [
    {
    "iso2" : "AF",
    "iso3" : "AFG",
    "name" : "Afghanistan",
    "phone_code" : "+93",
    "is_active" : True
    },
    {
    "iso2" : "AL",
    "iso3" : "ALB",
    "name" : "Albania",
    "phone_code" : "+355",
    "is_active" : True   
    }
    ]

currencies = [
    {
    "code" : "USD",
    "name" : "United States dollar",
    "symbol" : "$",
    "minor_units" : 2,
    "is_active" : True
    },
    {
    "code" : "EUR",
    "name" : "Euro",
    "symbol" : "€",
    "minor_units" : 2,
    "is_active" : True
    }]

def seed_countries(db: Session):
    for country in countries:
        existing_country = db.get(Country, country["iso2"])

        if existing_country:
            print(f"Country: {country['name']} already in database")
        else:
            db.add(Country(**country))
            print(f"Country: {country['name']} added")

    db.commit()
    

def seed_currencies(db: Session):
    for currency in currencies:
        existing_currency = db.get(Currency, currency["code"])

        if existing_currency:
            print(f"Currency: {currency['code']} already in database")
        else:
            db.add(Currency(**currency))
            print(f"Currency: {currency['code']} added")

    db.commit()


def main():
    # Make sure the tables exist, even if the server has never been started
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_countries(db)
        seed_currencies(db)


if __name__ == "__main__":
    main()
