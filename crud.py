from typing import List, Type, TypeVar, Optional, Dict, Any
from sqlmodel import Session, select, SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)

def create_object(session: Session, obj_in: ModelType) -> ModelType:
    session.add(obj_in)
    session.commit()
    session.refresh(obj_in)
    return obj_in

def get_object(session: Session, model: Type[ModelType], obj_id: int) -> Optional[ModelType]:
    return session.get(model, obj_id)

def get_objects(session: Session, model: Type[ModelType], skip: int = 0, limit: int = 100) -> List[ModelType]:
    statement = select(model).offset(skip).limit(limit)
    return session.exec(statement).all()

def update_object(session: Session, obj_db: ModelType, obj_in: Dict[str, Any]) -> ModelType:
    for key, value in obj_in.items():
        if hasattr(obj_db, key):
            setattr(obj_db, key, value)
    session.add(obj_db)
    session.commit()
    session.refresh(obj_db)
    return obj_db

def delete_object(session: Session, model: Type[ModelType], obj_id: int) -> bool:
    obj = session.get(model, obj_id)
    if not obj:
        return False
    session.delete(obj)
    session.commit()
    return True

