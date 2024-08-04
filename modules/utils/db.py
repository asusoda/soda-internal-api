# Creating a new engine for the database
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


class DBConnect :
    
        #Creating a new engine for the database
        def __init__(self) -> None:
            self.SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
            self.engine = create_engine(
                self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.Base = declarative_base()
            self.Base.metadata.create_all(bind=self.engine)

        #Creating a new session for the database
        def get_db(self):
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()


        ### Functions for the database


        ## From models.py (modules/points/models.py) functions for user and point models
        from modules.points.models import User, Points

        #creating a new user : uuid ,name ,email , academic_standing, points
        def create_user(db, user: User):
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

        #creating a new point : id , points , event , timestamp , awarder_by_officer, user_id
        def create_point(db, point: Points):
            db.add(point)
            db.commit()
            db.refresh(point)
            return point


                
              