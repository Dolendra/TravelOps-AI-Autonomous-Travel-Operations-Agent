import json
from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey, create_engine
from backend.database.db import Base

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="passenger", nullable=False)  # 'admin', 'operator', 'passenger'
    created_at = Column(DateTime, default=datetime.utcnow)


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowStateModel(Base):
    __tablename__ = "workflow_states"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    state = Column(String, nullable=False)  # e.g., 'NEW', 'INTENT_PARSED', 'SEARCHING', etc.
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskStateModel(Base):
    __tablename__ = "task_states"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    task_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False)  # 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    dependencies_raw = Column(Text, nullable=True)  # JSON list of task_ids
    input_raw = Column(Text, nullable=True)  # JSON formatted inputs
    output_raw = Column(Text, nullable=True)  # JSON formatted outputs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_dependencies(self, dependencies: List[str]):
        self.dependencies_raw = json.dumps(dependencies)

    def get_dependencies(self) -> List[str]:
        return json.loads(self.dependencies_raw) if self.dependencies_raw else []

    def set_input(self, input_data: Dict[str, Any]):
        self.input_raw = json.dumps(input_data)

    def get_input(self) -> Dict[str, Any]:
        return json.loads(self.input_raw) if self.input_raw else {}

    def set_output(self, output_data: Dict[str, Any]):
        self.output_raw = json.dumps(output_data)

    def get_output(self) -> Dict[str, Any]:
        return json.loads(self.output_raw) if self.output_raw else {}


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    agent_name = Column(String, nullable=False)
    action = Column(String, nullable=False)
    reasoning_summary = Column(Text, nullable=True)
    payload_raw = Column(Text, nullable=True)  # JSON formatted inputs/outputs/errors
    created_at = Column(DateTime, default=datetime.utcnow)

    def set_payload(self, payload: Dict[str, Any]):
        self.payload_raw = json.dumps(payload)

    def get_payload(self) -> Dict[str, Any]:
        return json.loads(self.payload_raw) if self.payload_raw else {}


class EventStoreModel(Base):
    __tablename__ = "event_store"

    id = Column(String, primary_key=True, index=True)  # UUID
    event_type = Column(String, nullable=False)
    session_id = Column(String, index=True, nullable=False)
    payload_raw = Column(Text, nullable=True)  # JSON formatted payload
    timestamp = Column(DateTime, default=datetime.utcnow)

    def set_payload(self, payload: Dict[str, Any]):
        self.payload_raw = json.dumps(payload)

    def get_payload(self) -> Dict[str, Any]:
        return json.loads(self.payload_raw) if self.payload_raw else {}


class CacheModel(Base):
    __tablename__ = "cache"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)  # JSON or text payload
    expires_at = Column(DateTime, nullable=True)


class BusInventoryModel(Base):
    __tablename__ = "bus_inventory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    operator_name = Column(String, nullable=False)
    bus_type = Column(String, nullable=False)
    departure_time = Column(String, nullable=False)  # HH:MM
    arrival_time = Column(String, nullable=False)    # HH:MM
    duration = Column(String, nullable=False)        # e.g., "8h 30m"
    origin = Column(String, nullable=False, index=True)
    destination = Column(String, nullable=False, index=True)
    fare = Column(Float, nullable=False)
    rating = Column(Float, nullable=False)
    available_seats = Column(Integer, nullable=False, default=20)
    seat_layout_raw = Column(Text, nullable=False)  # JSON list of seat strings

    def set_seat_layout(self, seats: List[str]):
        self.seat_layout_raw = json.dumps(seats)

    def get_seat_layout(self) -> List[str]:
        return json.loads(self.seat_layout_raw) if self.seat_layout_raw else []


class BookingModel(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    bus_id = Column(Integer, ForeignKey("bus_inventory.id"), nullable=False)
    pnr = Column(String, unique=True, index=True, nullable=True)
    seat_number = Column(String, nullable=False)
    status = Column(String, nullable=False)  # 'HELD', 'CONFIRMED', 'CANCELLED'
    passenger_name = Column(String, nullable=True)
    passenger_email = Column(String, nullable=True)
    price_paid = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeadLetterModel(Base):
    __tablename__ = "dead_letter_queue"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    session_id = Column(String, nullable=False)
    payload_raw = Column(Text, nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def set_payload(self, payload: Dict[str, Any]):
        self.payload_raw = json.dumps(payload)

    def get_payload(self) -> Dict[str, Any]:
        return json.loads(self.payload_raw) if self.payload_raw else {}

