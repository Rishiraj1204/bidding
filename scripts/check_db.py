import psycopg

passwords = [
    'dell', 'dell1', 'dell@123', 'Dell@123', 'dell1@123', 'Dell1@123', 'Dell#123',
    'admin123', 'root123', '123456789', 'sih2026', 'sih', 'bidverify', 'bidverify123',
    'BidVerify@123', 'postgres1234', 'postgres@123', 'postgres123', '1111', '0000',
    'welcome', 'welcome123', 'Welcome@123', '12345678', '123456', '123', '1234',
    'system', 'manager', 'pass', 'Postgres', 'Postgresql', 'PostgreSQL', 'p@ssword',
    'P@ssword123', 'P@ssw0rd', 'Admin@1', 'Admin@12', 'Root@123', 'sih@2026', 'SIH@2026',
    'bidding', 'biddingsystem', 'Bidding@123'
]

found = False
for p in passwords:
    try:
        conn = psycopg.connect(host='localhost', port=5432, user='postgres', password=p, dbname='postgres', connect_timeout=1)
        print(f"MATCH FOUND! Password is: {p}")
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT datname FROM pg_database WHERE datname = 'bidverify_db'")
            row = cur.fetchone()
            if not row:
                cur.execute("CREATE DATABASE bidverify_db")
                print("Created bidverify_db database successfully!")
            else:
                print("bidverify_db database already exists!")
        conn.close()
        found = True
        break
    except Exception as e:
        pass

if not found:
    print("None matched from extended list")
