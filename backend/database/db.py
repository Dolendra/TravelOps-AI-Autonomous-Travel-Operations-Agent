import os
from sqlalchemy.orm import declarative_base
from backend.database.manager import DatabaseManager

db_manager = DatabaseManager()
engine = db_manager.get_engine()
SessionLocal = db_manager.session_factory
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes the database schema if tables do not exist and seeds initial inventory."""
    import backend.database.models as models  # Import models to register with Base.metadata
    db_manager.init_db(Base)

    session = SessionLocal()
    try:
        # Check if inventory is empty
        if session.query(models.BusInventoryModel).first() is None:
            import json
            # Create a layout of 40 seats (1A to 10D)
            seats = [f"{row}{col}" for row in range(1, 11) for col in ["A", "B", "C", "D"]]
            
            buses = [
                # Bangalore -> Hyderabad
                {
                    "operator_name": "VRL Travels",
                    "bus_type": "A/C Sleeper (2+1)",
                    "departure_time": "21:30",
                    "arrival_time": "06:30",
                    "duration": "9h 00m",
                    "origin": "Bangalore",
                    "destination": "Hyderabad",
                    "fare": 950.0,
                    "rating": 4.5,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                {
                    "operator_name": "IntrCity SmartBus",
                    "bus_type": "A/C Sleeper (2+1) Premium",
                    "departure_time": "22:00",
                    "arrival_time": "06:45",
                    "duration": "8h 45m",
                    "origin": "Bangalore",
                    "destination": "Hyderabad",
                    "fare": 1100.0,
                    "rating": 4.7,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                # Hyderabad -> Bangalore
                {
                    "operator_name": "Orange Tours & Travels",
                    "bus_type": "A/C Sleeper (2+1)",
                    "departure_time": "22:15",
                    "arrival_time": "07:00",
                    "duration": "8h 45m",
                    "origin": "Hyderabad",
                    "destination": "Bangalore",
                    "fare": 980.0,
                    "rating": 4.4,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                {
                    "operator_name": "SRS Travels",
                    "bus_type": "Non-AC Sleeper (2+1)",
                    "departure_time": "20:30",
                    "arrival_time": "06:00",
                    "duration": "9h 30m",
                    "origin": "Hyderabad",
                    "destination": "Bangalore",
                    "fare": 650.0,
                    "rating": 3.8,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                # Delhi -> Jaipur
                {
                    "operator_name": "Zingbus",
                    "bus_type": "A/C Seater (2+2)",
                    "departure_time": "07:00",
                    "arrival_time": "12:30",
                    "duration": "5h 30m",
                    "origin": "Delhi",
                    "destination": "Jaipur",
                    "fare": 350.0,
                    "rating": 4.2,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                {
                    "operator_name": "Gujarat Travels",
                    "bus_type": "A/C Sleeper (2+1)",
                    "departure_time": "23:00",
                    "arrival_time": "04:30",
                    "duration": "5h 30m",
                    "origin": "Delhi",
                    "destination": "Jaipur",
                    "fare": 600.0,
                    "rating": 4.1,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                # Jaipur -> Delhi
                {
                    "operator_name": "Zingbus",
                    "bus_type": "A/C Seater (2+2)",
                    "departure_time": "14:00",
                    "arrival_time": "19:30",
                    "duration": "5h 30m",
                    "origin": "Jaipur",
                    "destination": "Delhi",
                    "fare": 370.0,
                    "rating": 4.3,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                # Mumbai -> Pune
                {
                    "operator_name": "Neeta Tours and Travels",
                    "bus_type": "A/C Multi-Axle Semi-Sleeper (2+2)",
                    "departure_time": "08:00",
                    "arrival_time": "11:30",
                    "duration": "3h 30m",
                    "origin": "Mumbai",
                    "destination": "Pune",
                    "fare": 450.0,
                    "rating": 4.0,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                },
                {
                    "operator_name": "MSRTC Shivneri",
                    "bus_type": "Volvo A/C Semi-Sleeper (2+2)",
                    "departure_time": "09:00",
                    "arrival_time": "12:30",
                    "duration": "3h 30m",
                    "origin": "Mumbai",
                    "destination": "Pune",
                    "fare": 520.0,
                    "rating": 4.6,
                    "available_seats": 40,
                    "seat_layout_raw": json.dumps(seats)
                }
            ]
            for bus_data in buses:
                bus = models.BusInventoryModel(**bus_data)
                session.add(bus)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
