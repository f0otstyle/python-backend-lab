import asyncpg


db_pool = None


async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        user="postgres",
        password="password",
        database="mydb",
        host="localhost",
        port=5432,
        min_size=1,
        max_size=10
    )
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR NOT NULL UNIQUE,
            name VARCHAR NOT NULL,
            password VARCHAR NOT NULL
        )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS drivers(
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            count INT DEFAULT 0,
            rating  FLOAT DEFAULT 0,
            active BOOLEAN DEFAULT TRUE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            driver_id INTEGER REFERENCES drivers(id) ON DELETE SET NULL,
            from_address TEXT NOT NULL,
            to_address TEXT NOT NULL,
            price NUMERIC NOT NULL CHECK (price > 0),
            status VARCHAR NOT NULL,
            order_details VARCHAR NOT NULL
            )
            """)
    return db_pool
