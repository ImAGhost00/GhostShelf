"""
Initialize default admin user in Wizarr database.

This script creates a default admin user if one doesn't already exist.
Run this after the Wizarr database is available.

Usage:
    python -m app.init_admin
"""
import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.wizarr_models import Base, WizarrUser


def init_admin():
    """Create default admin user in Wizarr database if it doesn't exist."""
    
    wizarr_db_path = os.getenv("WIZARR_DB_PATH", "/data/wizarr.db")
    engine = create_engine(
        f"sqlite:///{wizarr_db_path}",
        connect_args={"check_same_thread": False},
    )
    
    # Create tables if they don't exist
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Check if admin user already exists
        admin = session.query(WizarrUser).filter_by(username="admin").first()
        
        if admin:
            print(f"✓ Admin user already exists: {admin.username}")
            print(f"  Token: {admin.token}")
            print(f"  Email: {admin.email}")
            return admin
        
        # Create new admin user
        admin_token = str(uuid.uuid4())
        admin_user = WizarrUser(
            token=admin_token,
            username="admin",
            email="admin@ghostshelf.local",
            code="ADMIN_INIT",
            photo=None,
            expires=None,
            server_id=None,
            is_disabled=False,
        )
        
        session.add(admin_user)
        session.commit()
        
        print(f"✓ Created default admin user")
        print(f"  Username: admin")
        print(f"  Token: {admin_token}")
        print(f"  Email: admin@ghostshelf.local")
        print(f"\nUse this token to login in GhostShelf")
        
        return admin_user


if __name__ == "__main__":
    init_admin()
