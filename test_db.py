import sqlalchemy
from sqlalchemy import text
try:
    url = "postgresql://neondb_owner:npg_1RrxksUmJup7@ep-fancy-cake-a1q6u9a9-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
    engine = sqlalchemy.create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        print("Successfully connected to the database!")
except Exception as e:
    print(f"Error connecting to database: {e}")
